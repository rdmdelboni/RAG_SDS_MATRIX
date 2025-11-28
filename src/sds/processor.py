"""Main SDS processing pipeline orchestration."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..config.settings import get_settings
from ..database import get_db_manager
from ..rag import RAGRetriever
from ..utils.logger import get_logger
from .extractor import SDSExtractor
from .heuristics import HeuristicExtractor
from .llm_extractor import LLMExtractor
from .validator import FieldValidator, validate_extraction_result

logger = get_logger(__name__)


@dataclass
class ProcessingResult:
    """Result of processing an SDS document."""

    document_id: int
    filename: str
    status: str
    extractions: dict[str, dict[str, Any]]
    is_dangerous: bool
    completeness: float
    avg_confidence: float
    processing_time: float
    error_message: str | None = None


class SDSProcessor:
    """Orchestrate SDS document processing pipeline."""

    def __init__(self) -> None:
        """Initialize processor with required components."""
        self.settings = get_settings()
        self.db = get_db_manager()
        self.extractor = SDSExtractor()
        self.heuristics = HeuristicExtractor()
        self.llm = LLMExtractor()
        self.validator = FieldValidator()
        self.rag = RAGRetriever()

    def process(self, file_path: Path, use_rag: bool = True) -> ProcessingResult:
        """Process a single SDS document.

        Args:
            file_path: Path to SDS file
            use_rag: Whether to use RAG enrichment for dangerous chemicals

        Returns:
            ProcessingResult with extracted data
        """
        file_path = Path(file_path)
        start_time = time.time()

        logger.info("Processing SDS: %s", file_path.name)

        # Register document
        try:
            doc_id = self.db.register_document(
                filename=file_path.name,
                file_path=file_path,
                file_size=file_path.stat().st_size,
                file_type=file_path.suffix.lower(),
            )
        except Exception as e:
            logger.error("Failed to register document: %s", e)
            raise

        try:
            # === PHASE 1: LOCAL EXTRACTION ===
            logger.debug("Phase 1: Local extraction starting")

            # Extract text and sections
            extracted = self.extractor.extract_document(file_path)
            text = extracted["text"]
            sections = extracted.get("sections", {})

            # Run heuristics
            heuristic_results = self.heuristics.extract_all_fields(text, sections)

            # Refine with LLM if heuristics are uncertain
            extractions = {}
            for field_name, heur_result in heuristic_results.items():
                if (
                    heur_result["confidence"]
                    < self.settings.processing.heuristic_confidence_threshold
                ):
                    refined = self.llm.refine_heuristic(field_name, heur_result, text)
                    extractions[field_name] = refined
                else:
                    extractions[field_name] = heur_result

            # Also try LLM on missing fields
            from ..config.constants import EXTRACTION_FIELDS

            missing_fields = [
                f.name
                for f in EXTRACTION_FIELDS
                if f.name not in extractions and f.required
            ]

            if missing_fields:
                logger.debug(
                    "Attempting LLM extraction for %d missing fields",
                    len(missing_fields),
                )
                llm_results = self.llm.extract_multiple_fields(missing_fields, text)
                extractions.update(llm_results)

            # Validate all fields
            for field_name, result in extractions.items():
                extractions[field_name] = validate_extraction_result(field_name, result)

            # Calculate metrics
            completeness = self.validator.calculate_completeness(extractions)
            avg_confidence = self.validator.get_overall_confidence(extractions)

            # Determine if dangerous
            hazard_class = extractions.get("hazard_class", {}).get("value")
            is_dangerous = self.validator.is_dangerous(hazard_class)

            # Store Phase 1 results
            for field_name, result in extractions.items():
                self.db.store_extraction(
                    document_id=doc_id,
                    field_name=field_name,
                    value=result.get("value", ""),
                    confidence=result.get("confidence", 0.0),
                    context=result.get("context", ""),
                    validation_status=result.get("validation_status", "pending"),
                    validation_message=result.get("validation_message"),
                    source=result.get("source", "heuristic"),
                )

            # === PHASE 2: RAG ENRICHMENT (if needed) ===
            if use_rag and is_dangerous:
                kb_stats = {}
                try:
                    kb_stats = self.rag.get_knowledge_base_stats()
                except Exception as exc:  # pragma: no cover - defensive logging
                    logger.warning("Failed to get knowledge base stats: %s", exc)

                doc_count = (
                    kb_stats.get("document_count", 0)
                    if isinstance(kb_stats, dict)
                    else 0
                )

                if doc_count == 0 and isinstance(kb_stats, dict) and kb_stats.get("error"):
                    # Attempt self-healing reinit
                    try:
                        if self.rag.vector_store.ensure_ready():
                            kb_stats = self.rag.get_knowledge_base_stats()
                            doc_count = (
                                kb_stats.get("document_count", 0)
                                if isinstance(kb_stats, dict)
                                else 0
                            )
                    except Exception:
                        pass

                if doc_count > 0:
                    logger.debug("Phase 2: RAG enrichment for dangerous chemical")
                    extractions = self._enrich_with_rag(doc_id, extractions, text)
                elif kb_stats and isinstance(kb_stats, dict) and kb_stats.get("error"):
                    logger.warning(
                        "Skipping RAG enrichment due to vector store error: %s",
                        kb_stats.get("error"),
                    )

            # Update document status
            processing_time = time.time() - start_time
            self.db.update_document_status(
                doc_id,
                status="success",
                processing_time=processing_time,
                is_dangerous=is_dangerous,
            )

            logger.info(
                "Processed %s in %.2fs (completeness: %.0f%%, confidence: %.0f%%)",
                file_path.name,
                processing_time,
                completeness * 100,
                avg_confidence * 100,
            )

            return ProcessingResult(
                document_id=doc_id,
                filename=file_path.name,
                status="success",
                extractions=extractions,
                is_dangerous=is_dangerous,
                completeness=completeness,
                avg_confidence=avg_confidence,
                processing_time=processing_time,
            )

        except Exception as e:
            processing_time = time.time() - start_time
            logger.error("Processing failed: %s", e)

            self.db.update_document_status(
                doc_id,
                status="failed",
                processing_time=processing_time,
                error_message=str(e),
            )

            return ProcessingResult(
                document_id=doc_id,
                filename=file_path.name,
                status="failed",
                extractions={},
                is_dangerous=False,
                completeness=0.0,
                avg_confidence=0.0,
                processing_time=processing_time,
                error_message=str(e),
            )

    def _enrich_with_rag(
        self,
        doc_id: int,
        extractions: dict[str, dict[str, Any]],
        text: str,
    ) -> dict[str, dict[str, Any]]:
        """Enrich extraction with RAG knowledge base.

        Args:
            doc_id: Document ID
            extractions: Current extractions
            text: Document text

        Returns:
            Updated extractions
        """
        try:
            product_name = extractions.get("product_name", {}).get("value")
            cas_number = extractions.get("cas_number", {}).get("value")
            un_number = extractions.get("un_number", {}).get("value")

            # Build search query
            query_parts = []
            if product_name and product_name != "NOT_FOUND":
                query_parts.append(product_name)
            if cas_number and cas_number != "NOT_FOUND":
                query_parts.append(f"CAS {cas_number}")
            if un_number and un_number != "NOT_FOUND":
                query_parts.append(f"UN {un_number}")

            if not query_parts:
                return extractions

            query = " ".join(query_parts)

            # Search knowledge base
            context = self.rag.vector_store.search_with_context(query, k=3)
            if not context:
                return extractions

            # Use RAG context to refine incompatibilities
            incomp_prompt = f"""Based on this context, what chemicals is {product_name} incompatible with?

Context:
{context}

List incompatible materials separated by commas:"""

            answer = self.rag.ollama.chat(
                message=incomp_prompt,
                context=context,
            )

            if answer and "NOT_FOUND" not in answer:
                extractions["incompatibilities"] = validate_extraction_result(
                    "incompatibilities",
                    {
                        "value": answer.strip(),
                        "confidence": 0.75,
                        "context": "RAG enrichment",
                        "source": "rag",
                    },
                )

                # Store RAG enrichment
                self.db.store_extraction(
                    document_id=doc_id,
                    field_name="incompatibilities",
                    value=answer.strip(),
                    confidence=0.75,
                    context="RAG enrichment",
                    validation_status=extractions["incompatibilities"].get(
                        "validation_status"
                    ),
                    source="rag",
                )

        except Exception as e:
            logger.warning("RAG enrichment failed: %s", e)

        return extractions

    def process_batch(
        self, file_paths: list[Path], use_rag: bool = True
    ) -> list[ProcessingResult]:
        """Process multiple SDS files.

        Args:
            file_paths: List of file paths
            use_rag: Whether to use RAG enrichment

        Returns:
            List of ProcessingResult objects
        """
        results = []

        for i, file_path in enumerate(file_paths, 1):
            logger.info("Processing file %d/%d", i, len(file_paths))

            try:
                result = self.process(file_path, use_rag=use_rag)
                results.append(result)
            except Exception as e:
                logger.error("Failed to process %s: %s", file_path, e)
                results.append(
                    ProcessingResult(
                        document_id=-1,
                        filename=file_path.name,
                        status="failed",
                        extractions={},
                        is_dangerous=False,
                        completeness=0.0,
                        avg_confidence=0.0,
                        processing_time=0.0,
                        error_message=str(e),
                    )
                )

        logger.info(
            "Batch processing complete: %d successful, %d failed",
            sum(1 for r in results if r.status == "success"),
            sum(1 for r in results if r.status == "failed"),
        )

        return results
