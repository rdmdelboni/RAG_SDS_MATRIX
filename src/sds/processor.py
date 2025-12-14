"""Main SDS processing pipeline orchestration."""

from __future__ import annotations

import time
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any
import hashlib

from ..config.settings import get_settings
from ..database import get_db_manager
from ..rag import RAGRetriever, TextChunker
from ..utils.logger import get_logger
from .confidence_scorer import ConfidenceScorer, FieldSource
from .extractor import SDSExtractor
from .external_validator import ExternalValidator
from .heuristics import HeuristicExtractor
from .ingredient_extractor import IngredientExtractor
from .llm_extractor import LLMExtractor
from .pubchem_enrichment import PubChemEnricher
from .validator import FieldValidator, validate_extraction_result, validate_full_consistency
from .profile_router import ProfileRouter, ManufacturerProfile

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
        self.ingredient_extractor = IngredientExtractor()
        # LLMExtractor now uses few-shot learning by default for better accuracy
        self.llm = LLMExtractor(use_few_shot=True, use_consensus=False)
        self.validator = FieldValidator()
        self.rag = RAGRetriever()
        self.external_validator = ExternalValidator()
        self.pubchem_enricher = PubChemEnricher()
        self.confidence_scorer = ConfidenceScorer()
        self.chunker = TextChunker()
        self.router = ProfileRouter()

        # Thread pool for background operations
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="SDS_Background")

    def process(self, file_path: Path, use_rag: bool = True, force_reprocess: bool = False, progress_callback=None) -> ProcessingResult:
        """Process a single SDS document.

        Args:
            file_path: Path to SDS file
            use_rag: Whether to use RAG enrichment for dangerous chemicals
            force_reprocess: If True, reprocess even if already processed. If False, use cache.
            progress_callback: Optional callback(current, total, message) for OCR progress

        Returns:
            ProcessingResult with extracted data
        """
        file_path = Path(file_path)
        start_time = time.time()

        logger.info("Processing SDS: %s", file_path.name)

        # === EARLY DEDUPLICATION CHECK (OPTIMIZED) ===
        # Step 1: Fast check by name+size (no I/O needed)
        if not force_reprocess:
            existing_doc_id = self.db.check_file_by_name_and_size(
                file_path.name, file_path.stat().st_size
            )
            if existing_doc_id:
                logger.info(
                    "⚡ Skipping already processed file (by name+size): %s (id=%d) - using cached results",
                    file_path.name,
                    existing_doc_id,
                )
                existing_extractions = self.db.get_extractions_by_document(existing_doc_id)
                existing_status = self.db.get_document_status(existing_doc_id)

                return ProcessingResult(
                    document_id=existing_doc_id,
                    filename=file_path.name,
                    status=existing_status.get("status", "completed"),
                    extractions=existing_extractions,
                    is_dangerous=existing_status.get("is_dangerous", False),
                    completeness=existing_status.get("completeness", 0.0),
                    avg_confidence=existing_status.get("avg_confidence", 0.0),
                    processing_time=0.0,
                    error_message=None,
                )

        # Step 2: Check by path (for files that may have been moved)
        existing_doc = self.db.get_document_by_path(file_path)
        if existing_doc and existing_doc.status in ("completed", "success") and not force_reprocess:
            # Check if it has extractions
            if self.db.is_document_already_processed(existing_doc.id):
                logger.info(
                    "⚡ Skipping already processed file (by path): %s (id=%d) - using cached results",
                    file_path.name,
                    existing_doc.id,
                )
                existing_extractions = self.db.get_extractions_by_document(existing_doc.id)
                existing_status = self.db.get_document_status(existing_doc.id)

                return ProcessingResult(
                    document_id=existing_doc.id,
                    filename=file_path.name,
                    status=existing_status.get("status", "completed"),
                    extractions=existing_extractions,
                    is_dangerous=existing_status.get("is_dangerous", False),
                    completeness=existing_status.get("completeness", 0.0),
                    avg_confidence=existing_status.get("avg_confidence", 0.0),
                    processing_time=0.0,
                    error_message=None,
                )

        # Register document (will check hash as final deduplication if needed)
        try:
            doc_id = self.db.register_document(
                filename=file_path.name,
                file_path=file_path,
                file_size=file_path.stat().st_size,
                file_type=file_path.suffix.lower(),
            )
            
            # If register_document found a duplicate by hash and we didn't catch it earlier,
            # verify it's actually processed before skipping
            if doc_id and not force_reprocess:
                # Check if this doc_id is different from what we found by path
                # (meaning register_document found it by hash)
                if existing_doc is None or doc_id != existing_doc.id:
                    if self.db.is_document_already_processed(doc_id):
                        logger.info(
                            "⚡ Skipping duplicate by hash: %s (id=%d) - using cached results",
                            file_path.name,
                            doc_id,
                        )
                        existing_extractions = self.db.get_extractions_by_document(doc_id)
                        existing_status = self.db.get_document_status(doc_id)

                        return ProcessingResult(
                            document_id=doc_id,
                            filename=file_path.name,
                            status=existing_status.get("status", "completed"),
                            extractions=existing_extractions,
                            is_dangerous=existing_status.get("is_dangerous", False),
                            completeness=existing_status.get("completeness", 0.0),
                            avg_confidence=existing_status.get("avg_confidence", 0.0),
                            processing_time=0.0,
                            error_message=None,
                        )
                
        except Exception as e:
            logger.error("Failed to register document: %s", e)
            raise

        try:
            # === PHASE 1: MULTI-PASS LOCAL EXTRACTION ===
            phase1_start = time.time()
            logger.debug("Phase 1: Multi-pass local extraction starting")

            # Extract text and sections (with OCR progress callback)
            ocr_start = time.time()
            extracted = self.extractor.extract_document(file_path, progress_callback=progress_callback)
            ocr_time = time.time() - ocr_start
            logger.info(f"⏱️ OCR extraction completed in {ocr_time:.2f}s")

            text = extracted["text"]
            sections = extracted.get("sections", {})

            # Extract full ingredient list from Section 3 (composition)
            try:
                ingredients = self.ingredient_extractor.extract(text, sections)
                self.db.replace_document_ingredients(
                    doc_id,
                    [
                        {
                            "cas_number": ing.cas_number,
                            "chemical_name": ing.chemical_name,
                            "concentration_text": ing.concentration_text,
                            "concentration_min": ing.concentration_min,
                            "concentration_max": ing.concentration_max,
                            "concentration_unit": ing.concentration_unit,
                            "confidence": ing.confidence,
                            "evidence": ing.evidence,
                            "source": "heuristic",
                        }
                        for ing in ingredients
                    ],
                )
                logger.info("Extracted %d ingredients from Section 3", len(ingredients))
            except Exception as exc:  # pragma: no cover - best effort
                logger.warning("Ingredient extraction failed: %s", exc)

            # Detect Manufacturer Profile
            profile = self.router.identify_profile(text)

            # PASS 1: Heuristics (fast, high-precision fields)
            logger.info("Phase 1a: Running heuristics extraction")
            extractions = self._extraction_pass_heuristics(text, sections, profile)

            # PASS 2: LLM for uncertain/missing fields
            llm_start = time.time()
            logger.info("Phase 1b: Running LLM extraction (may take 10-30 seconds)...")
            extractions = self._extraction_pass_llm(extractions, text, sections)
            llm_time = time.time() - llm_start
            logger.info(f"⏱️ LLM extraction completed in {llm_time:.2f}s")

            # PASS 2.5: Defensive normalization of field entries
            extractions = self._defensive_normalize_extractions(extractions)

            # PASS 3: Cross-field validation and normalization
            extractions = self._validate_and_normalize_fields(extractions)

            # Calculate metrics
            completeness = self.validator.calculate_completeness(extractions)
            avg_confidence = self.validator.get_overall_confidence(extractions)

            # Determine if dangerous
            hazard_class = extractions.get("hazard_class", {}).get("value")
            is_dangerous = self.validator.is_dangerous(hazard_class)

            # Store Phase 1 results using batch insert (faster than individual stores)
            extraction_batch = [
                (
                    field_name,
                    result.get("value", ""),
                    result.get("confidence", 0.0),
                    result.get("context", ""),
                    result.get("validation_status", "pending"),
                    result.get("validation_message"),
                    result.get("source", "heuristic"),
                )
                for field_name, result in extractions.items()
            ]
            self.db.store_extractions_batch(doc_id, extraction_batch)

            # === PHASE 2: PUBCHEM ENRICHMENT ===
            pubchem_start = time.time()
            logger.info("Phase 2: PubChem enrichment and validation (may take 5-10 seconds)...")
            pubchem_enrichments = self.pubchem_enricher.enrich_extraction(
                extractions,
                aggressive=False  # Conservative by default
            )
            pubchem_time = time.time() - pubchem_start
            logger.info(f"⏱️ PubChem enrichment completed in {pubchem_time:.2f}s")
            
            # Apply enrichments to extractions
            if pubchem_enrichments:
                logger.info(f"Applied {len(pubchem_enrichments)} PubChem enrichments")
                enrichment_report = self.pubchem_enricher.generate_enrichment_report(pubchem_enrichments)
                logger.debug(f"\n{enrichment_report}")
                
                # Update extractions with enriched data
                for field_name, enrichment in pubchem_enrichments.items():
                    if enrichment.enriched_value and enrichment.validation_status == "enriched":
                        # Add enriched field or update existing
                        if field_name not in extractions:
                            extractions[field_name] = {
                                "value": enrichment.enriched_value,
                                "confidence": enrichment.confidence,
                                "source": "pubchem_enrichment",
                                "context": "Enriched from PubChem API",
                                "validation_status": "valid"
                            }
                        elif enrichment.confidence > extractions[field_name].get("confidence", 0):
                            # Boost confidence for validated fields
                            extractions[field_name]["confidence"] = min(
                                extractions[field_name]["confidence"] + 0.10,
                                0.95
                            )
                            extractions[field_name]["pubchem_validated"] = True
                    
                    elif enrichment.validation_status == "warning":
                        # Flag warnings in the extraction
                        if field_name in extractions:
                            extractions[field_name]["validation_status"] = "warning"
                            extractions[field_name]["pubchem_issues"] = enrichment.issues
                
                # Store enrichment metadata using batch insert
                enrichment_batch = [
                    (
                        field_name,
                        enrichment.enriched_value,
                        enrichment.confidence,
                        "PubChem enrichment",
                        enrichment.validation_status,
                        "; ".join(enrichment.issues) if enrichment.issues else None,
                        "pubchem",
                    )
                    for field_name, enrichment in pubchem_enrichments.items()
                    if enrichment.enriched_value
                ]
                if enrichment_batch:
                    self.db.store_extractions_batch(doc_id, enrichment_batch)

            # === PHASE 3: RAG FIELD COMPLETION (if needed) ===
            rag_start = time.time()
            if use_rag and (is_dangerous or completeness < 0.8):
                kb_stats = {}
                logger.info("Phase 3: RAG field completion (may take 10-20 seconds)...")
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
                    logger.debug("Phase 2: RAG field completion (completeness: %.0f%%)", completeness * 100)
                    extractions = self._enrich_with_rag(doc_id, extractions, text)
                    # Recalculate metrics after RAG enrichment
                    completeness = self.validator.calculate_completeness(extractions)
                    avg_confidence = self.validator.get_overall_confidence(extractions)
                elif kb_stats and isinstance(kb_stats, dict) and kb_stats.get("error"):
                    logger.warning(
                        "Skipping RAG enrichment due to vector store error: %s",
                        kb_stats.get("error"),
                    )
                rag_time = time.time() - rag_start
                logger.info(f"⏱️ RAG enrichment completed in {rag_time:.2f}s")
            else:
                # RAG not used - still log the skipped phase
                logger.debug("Phase 3: Skipping RAG enrichment (not dangerous and completeness >= 0.8)")

            # Update document status
            processing_time = time.time() - start_time

            # Index raw SDS text + metadata into the RAG vector store
            # Run in background to not block response.
            # We use a ThreadPoolExecutor (not daemon) to ensure tasks complete on shutdown if needed,
            # but we don't wait for it here.
            self._executor.submit(
                self._index_document_in_rag,
                doc_id,
                file_path,
                text,
                extractions
            )

            self.db.update_document_status(
                doc_id,
                status="success",
                processing_time=processing_time,
                is_dangerous=is_dangerous,
                completeness=completeness,
                avg_confidence=avg_confidence,
            )

            # Log LLM metrics if available
            self._log_llm_metrics(file_path.name)

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
            # Log full traceback for better diagnostics
            import traceback
            tb = traceback.format_exc()
            logger.error("Processing failed: %s\n%s", e, tb)

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

    def _defensive_normalize_extractions(
        self, extractions: dict[str, dict[str, Any]]
    ) -> dict[str, dict[str, Any]]:
        """Ensure all field entries are dicts with expected keys.

        Some upstream extractors (heuristics/LLM) may occasionally return raw
        strings or other types. This function coerces any non-dict entries into
        the standard schema to prevent attribute errors when accessing with
        `.get` later in the pipeline.

        Returns the updated `extractions` mapping.
        """
        normalized: dict[str, dict[str, Any]] = {}
        for field_name, result in extractions.items():
            if isinstance(result, dict):
                # Ensure minimal keys
                result.setdefault("confidence", result.get("confidence", 0.70))
                result.setdefault("method", result.get("method", "heuristic"))
                normalized[field_name] = result
                continue

            # For non-dict types, reuse LLM normalizer to wrap/coerce
            wrapped = self._normalize_llm_result(result)
            # Mark as heuristic if coming from first pass but not explicit
            if wrapped.get("method") == "llm" and field_name in normalized:
                pass
            normalized[field_name] = wrapped

        return normalized

    def _extraction_pass_heuristics(
        self, text: str, sections: dict[int, str], profile: ManufacturerProfile
    ) -> dict[str, dict[str, Any]]:
        """Pass 1: Fast heuristic extraction with regex patterns.

        Args:
            text: Full document text
            sections: Extracted sections
            profile: Manufacturer Profile

        Returns:
            Dictionary of extracted fields
        """
        return self.heuristics.extract_all_fields(text, sections, profile)

    def _extraction_pass_llm(
        self,
        extractions: dict[str, dict[str, Any]],
        text: str,
        sections: dict[int, str],
    ) -> dict[str, dict[str, Any]]:
        """Pass 2: LLM extraction for uncertain or missing fields.

        Args:
            extractions: Results from heuristic pass
            text: Full document text
            sections: Extracted sections

        Returns:
            Updated extractions with LLM refinements
        """
        from ..config.constants import EXTRACTION_FIELDS

        # Fields that need LLM help
        uncertain_fields = [
            name
            for name, result in extractions.items()
            if result["confidence"] < self.settings.processing.heuristic_confidence_threshold
        ]

        missing_fields = [
            f.name
            for f in EXTRACTION_FIELDS
            if f.name not in extractions and f.required
        ]

        fields_for_llm = list(set(uncertain_fields + missing_fields))

        if not fields_for_llm:
            return extractions

        logger.debug("LLM extracting %d fields", len(fields_for_llm))

        # Refine uncertain fields
        for field_name in uncertain_fields:
            heur_result = extractions[field_name]
            refined = self.llm.refine_heuristic(field_name, heur_result, text)
            # Normalize LLM output to dict schema
            normalized = self._normalize_llm_result(refined)
            if normalized["confidence"] > heur_result.get("confidence", 0.0):
                extractions[field_name] = normalized

        # Extract missing fields
        if missing_fields:
            llm_results = self.llm.extract_multiple_fields(missing_fields, text)
            for field_name, result in llm_results.items():
                if field_name not in extractions:
                    extractions[field_name] = self._normalize_llm_result(result)

        return extractions

    def _normalize_llm_result(self, result: Any) -> dict[str, Any]:
        """Normalize LLM extraction outputs into the expected dict schema.

        The pipeline expects each field value as a dict with keys like
        "value", "confidence", "source"/"method", and optional context.
        Some LLM implementations may return a plain string or a JSON string.

        This function safely converts those to the expected dict to prevent
        attribute errors such as `'str' object has no attribute get`.
        """
        # If already a dict with a value, pass through
        if isinstance(result, dict):
            # If the dict appears to be a plain mapping without required keys,
            # try to lift a reasonable value
            if "value" not in result:
                # prefer common keys
                for candidate in ("text", "answer", "result"):
                    if candidate in result:
                        logger.debug(
                            "Normalized LLM dict: lifted key '%s' to 'value'",
                            candidate,
                        )
                        result = {"value": result[candidate], "confidence": result.get("confidence", 0.70), "method": result.get("method", "llm")}
                        break
                else:
                    # fallback: store stringified dict as value
                    logger.debug(
                        "Normalized LLM dict: no value key found, stringifying dict"
                    )
                    result = {
                        "value": str(result),
                        "confidence": 0.70,
                        "method": "llm",
                    }
            # Ensure minimum keys exist
            result.setdefault("confidence", 0.70)
            result.setdefault("method", "llm")
            return result

        # If it's a string, attempt JSON parse first
        if isinstance(result, str):
            import json
            s = result.strip()
            if (s.startswith("{") and s.endswith("}")) or (s.startswith("[") and s.endswith("]")):
                try:
                    parsed = json.loads(s)
                    logger.debug(
                        "Normalized LLM string: parsed JSON string to dict"
                    )
                    return self._normalize_llm_result(parsed)
                except Exception:
                    # fall through to wrapping
                    pass
            # Wrap raw string as value
            logger.debug("Normalized LLM string: wrapped plain string as value")
            return {"value": s, "confidence": 0.70, "method": "llm"}

        # Any other type: coerce to string value
        logger.debug(
            "Normalized LLM result: coerced %s to string", type(result).__name__
        )
        return {"value": str(result), "confidence": 0.70, "method": "llm"}

    def _validate_and_normalize_fields(
        self, extractions: dict[str, dict[str, Any]]
    ) -> dict[str, dict[str, Any]]:
        """Pass 3: Validate and normalize extracted fields.

        Args:
            extractions: Raw extraction results

        Returns:
            Validated and normalized extractions
        """
        # Validate each field
        for field_name, result in extractions.items():
            extractions[field_name] = validate_extraction_result(field_name, result)

        # Cross-field validation
        extractions = self._cross_validate_fields(extractions)

        # Internal Hazard Consistency Check
        consistency_report = validate_full_consistency(extractions)
        if consistency_report and consistency_report["status"] == "inconsistent":
            logger.warning("Internal hazard inconsistency found: %s", consistency_report)
            # We can attach this to a specific field or a global metadata field.
            # Let's attach it to 'h_statements' or 'hazard_class' as a warning.
            target_field = "h_statements" if "h_statements" in extractions else "hazard_class"
            if target_field in extractions:
                extractions[target_field].setdefault("validation_message", "")
                msg = f"Inconsistent with composition: Missing {len(consistency_report['missing_hazards'])} calculated hazards."
                extractions[target_field]["validation_message"] += (" | " if extractions[target_field]["validation_message"] else "") + msg
                extractions[target_field]["validation_status"] = "warning"
            
            # Store full report in a special meta-field
            extractions["_hazard_consistency"] = consistency_report

        # Product name normalization (non-destructive)
        if "product_name" in extractions and "value" in extractions["product_name"]:
            from .normalizer import normalize_product_name

            original_val = extractions["product_name"].get("value", "")
            normalized, changed = normalize_product_name(original_val)
            if changed and normalized != original_val:
                # Preserve original but add normalized_value field
                extractions["product_name"]["normalized_value"] = normalized
                # Slightly boost confidence if normalization yields cleaner canonical form
                conf = extractions["product_name"].get("confidence", 0.0)
                extractions["product_name"]["confidence"] = min(0.99, conf + 0.05)
                extractions["product_name"].setdefault(
                    "validation_message",
                    "Normalized chemical name variant generated",
                )
        
        # External validation and confidence scoring
        extractions = self._apply_external_validation(extractions)
        extractions = self._apply_confidence_scoring(extractions)

        return extractions

    def _cross_validate_fields(
        self, extractions: dict[str, dict[str, Any]]
    ) -> dict[str, dict[str, Any]]:
        """Validate consistency between related fields.

        Args:
            extractions: Extracted fields

        Returns:
            Updated extractions with adjusted confidence
        """
        # UN number should match hazard class
        un_num = extractions.get("un_number", {}).get("value")
        hazard = extractions.get("hazard_class", {}).get("value")

        if un_num and hazard and un_num != "NOT_FOUND" and hazard != "NOT_FOUND":
            expected_class = self._lookup_un_hazard_class(un_num)
            if expected_class and expected_class != hazard:
                logger.warning(
                    "UN %s expects class %s, found %s - adjusting confidence",
                    un_num,
                    expected_class,
                    hazard,
                )
                # Lower confidence on hazard class
                if "hazard_class" in extractions:
                    extractions["hazard_class"]["confidence"] *= 0.7
                # Suggest correction
                extractions["hazard_class"]["validation_message"] = (
                    f"Expected class {expected_class} for UN {un_num}"
                )

        # Product name should not be a code or ID
        product = extractions.get("product_name", {}).get("value", "")
        if product and len(product) < 5 and product.isupper():
            logger.debug("Product name looks like a code: %s", product)
            if "product_name" in extractions:
                extractions["product_name"]["confidence"] *= 0.6
                extractions["product_name"]["validation_message"] = "Might be a product code, not a name"

        return extractions

    def _lookup_un_hazard_class(self, un_number: str) -> str | None:
        """Look up expected hazard class for UN number.

        Args:
            un_number: UN number (4 digits)

        Returns:
            Expected hazard class or None
        """
        # Common UN number mappings (partial list for validation)
        un_hazard_map = {
            "1170": "3",  # Ethanol
            "1203": "3",  # Gasoline
            "1230": "3",  # Methanol
            "1263": "3",  # Paint
            "1789": "8",  # Hydrochloric acid
            "1791": "8",  # Hypochlorite solution
            "1824": "8",  # Sodium hydroxide
            "1830": "8",  # Sulfuric acid
            "1866": "3",  # Resin solution
            "2031": "8",  # Nitric acid
            "2789": "8",  # Acetic acid
        }

        return un_hazard_map.get(un_number)

    def _rag_complete_missing_fields(
        self,
        doc_id: int,
        extractions: dict[str, dict[str, Any]],
        text: str,
    ) -> dict[str, dict[str, Any]]:
        """Use RAG to complete missing or low-confidence fields.

        Args:
            doc_id: Document ID
            extractions: Current extractions
            text: Document text

        Returns:
            Updated extractions with RAG-enriched fields
        """
        try:
            # Get chemical identifier
            chemical_id = self._get_chemical_identifier(extractions)
            if not chemical_id:
                return extractions

            # Query knowledge base
            query = f"Chemical: {chemical_id}. Provide UN number, hazard class, incompatibilities, H-statements"
            rag_docs = self.rag.retrieve(query, k=5)

            if not rag_docs:
                return extractions

            # Combine RAG context
            context = "\n\n".join([doc.content for doc in rag_docs[:3]])

            # Complete missing/weak fields
            fields_to_enrich = ["un_number", "hazard_class", "incompatibilities", "h_statements"]

            for field_name in fields_to_enrich:
                if self._should_enrich_field(field_name, extractions):
                    enriched = self._extract_field_from_rag(field_name, chemical_id, context)
                    if enriched:
                        extractions[field_name] = validate_extraction_result(
                            field_name,
                            {
                                "value": enriched,
                                "confidence": 0.78,
                                "source": "rag",
                                "context": "Knowledge base enrichment",
                            },
                        )
                        logger.debug("RAG enriched %s: %s", field_name, enriched)

                        # Store enrichment
                        self.db.store_extraction(
                            document_id=doc_id,
                            field_name=field_name,
                            value=enriched,
                            confidence=0.78,
                            context="RAG knowledge base",
                            validation_status="valid",
                            source="rag",
                        )

        except Exception as e:
            logger.warning("RAG field completion failed: %s", e)

        return extractions

    def _get_chemical_identifier(self, extractions: dict[str, dict[str, Any]]) -> str | None:
        """Get best chemical identifier for RAG query.

        Args:
            extractions: Extracted fields

        Returns:
            Chemical identifier or None
        """
        # Priority: CAS > Product Name > UN Number
        cas = extractions.get("cas_number", {}).get("value")
        if cas and cas != "NOT_FOUND":
            return f"CAS {cas}"

        product = extractions.get("product_name", {}).get("value")
        if product and product != "NOT_FOUND" and len(product) > 5:
            return product

        un = extractions.get("un_number", {}).get("value")
        if un and un != "NOT_FOUND":
            return f"UN {un}"

        return None

    def _index_document_in_rag(
        self,
        doc_id: int,
        file_path: Path,
        text: str,
        extractions: dict[str, dict[str, Any]],
    ) -> None:
        """Send processed SDS text + metadata into the RAG vector store."""
        try:
            vector_store = getattr(self.rag, "vector_store", None)
            if not vector_store or not hasattr(vector_store, "add_documents"):
                return

            if not text or len(text.strip()) < 40:
                return

            content_hash = hashlib.sha256(
                text.encode("utf-8", errors="ignore")
            ).hexdigest()
            if hasattr(self.db, "rag_document_exists") and self.db.rag_document_exists(
                content_hash
            ):
                return

            metadata = {
                "source": "sds",
                "type": "sds",
                "document_id": doc_id,
                "filename": file_path.name,
                "path": str(file_path),
                "title": extractions.get("product_name", {}).get("value")
                or file_path.stem,
                "cas_number": extractions.get("cas_number", {}).get("value"),
                "hazard_class": extractions.get("hazard_class", {}).get("value"),
                "un_number": extractions.get("un_number", {}).get("value"),
                "packing_group": extractions.get("packing_group", {}).get("value"),
                "incompatibilities": extractions.get("incompatibilities", {}).get(
                    "value"
                ),
            }

            chunks = self.chunker.chunk_text(text, metadata=metadata)
            if not chunks:
                return

            if hasattr(vector_store, "ensure_ready") and not vector_store.ensure_ready():
                return

            vector_store.add_documents(chunks)
            if hasattr(self.db, "register_rag_document"):
                self.db.register_rag_document(
                    source_type="sds",
                    source_path=str(file_path),
                    title=metadata.get("title"),
                    chunk_count=len(chunks),
                    content_hash=content_hash,
                    metadata=metadata,
                )

            logger.info(
                "Indexed SDS '%s' into RAG (chunks=%d)", file_path.name, len(chunks)
            )
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.warning("Failed to index SDS %s into RAG: %s", file_path.name, exc)

    def _should_enrich_field(
        self, field_name: str, extractions: dict[str, dict[str, Any]]
    ) -> bool:
        """Check if field should be enriched with RAG.

        Args:
            field_name: Field to check
            extractions: Current extractions

        Returns:
            True if field needs enrichment
        """
        if field_name not in extractions:
            return True

        result = extractions[field_name]
        value = result.get("value", "")
        confidence = result.get("confidence", 0.0)

        # Enrich if missing, low confidence, or placeholder
        return (
            not value
            or value == "NOT_FOUND"
            or confidence < 0.70
            or len(str(value).strip()) < 3
        )

    def _extract_field_from_rag(
        self, field_name: str, chemical_id: str, context: str
    ) -> str | None:
        """Extract a specific field from RAG context.

        Args:
            field_name: Field to extract
            chemical_id: Chemical identifier
            context: RAG retrieved context

        Returns:
            Extracted value or None
        """
        # Field-specific prompts
        prompts = {
            "un_number": f"What is the UN number for {chemical_id}? Reply with only the 4-digit number or NOT_FOUND.",
            "hazard_class": f"What is the hazard class for {chemical_id}? Reply with only the class number (e.g., 3, 8, 6.1) or NOT_FOUND.",
            "incompatibilities": f"What materials is {chemical_id} incompatible with? List them separated by commas.",
            "h_statements": f"What are the H-statements (hazard codes) for {chemical_id}? List them separated by commas (e.g., H301, H315).",
        }

        prompt = prompts.get(field_name)
        if not prompt:
            return None

        full_prompt = f"{prompt}\n\nContext:\n{context[:2000]}\n\nAnswer:"

        try:
            answer = self.rag.ollama.chat(message=full_prompt, context=context[:2000])
            if answer and "NOT_FOUND" not in answer.upper() and len(answer.strip()) > 2:
                return answer.strip()
        except Exception as e:
            logger.debug("RAG extraction failed for %s: %s", field_name, e)

        return None

    def _enrich_with_rag(
        self,
        doc_id: int,
        extractions: dict[str, dict[str, Any]],
        text: str,
    ) -> dict[str, dict[str, Any]]:
        """Legacy RAG enrichment method (kept for compatibility).

        Args:
            doc_id: Document ID
            extractions: Current extractions
            text: Document text

        Returns:
            Updated extractions
        """
        # Redirect to new implementation
        return self._rag_complete_missing_fields(doc_id, extractions, text)
    
    def _apply_external_validation(
        self, extractions: dict[str, dict[str, Any]]
    ) -> dict[str, dict[str, Any]]:
        """
        Apply external validation (PubChem) to extracted fields.
        
        Args:
            extractions: Current field extractions
        
        Returns:
            Updated extractions with validation results
        """
        logger.debug("Applying external validation via PubChem")
        
        # Get key fields for validation
        product_name = extractions.get("product_name", {}).get("value")
        cas_number = extractions.get("cas_number", {}).get("value")
        formula = extractions.get("formula", {}).get("value")
        
        # Validate product name
        if product_name and product_name != "NOT_FOUND":
            validation = self.external_validator.validate_product_name(
                product_name, cas_number
            )
            
            extractions["product_name"]["external_validation"] = {
                "source": validation.source,
                "is_valid": validation.is_valid,
                "confidence_boost": validation.confidence_boost,
            }
            
            if validation.is_valid:
                old_conf = extractions["product_name"].get("confidence", 0.0)
                new_conf = min(0.99, old_conf + validation.confidence_boost)
                extractions["product_name"]["confidence"] = new_conf
                logger.debug(
                    f"Product name validated (conf: {old_conf:.2f} → {new_conf:.2f})"
                )
        
        # Validate CAS number
        if cas_number and cas_number != "NOT_FOUND":
            validation = self.external_validator.validate_cas_number(cas_number)
            
            extractions["cas_number"]["external_validation"] = {
                "source": validation.source,
                "is_valid": validation.is_valid,
                "confidence_boost": validation.confidence_boost,
            }
            
            if validation.is_valid:
                old_conf = extractions["cas_number"].get("confidence", 0.0)
                new_conf = min(0.99, old_conf + validation.confidence_boost)
                extractions["cas_number"]["confidence"] = new_conf
                logger.debug(
                    f"CAS number validated (conf: {old_conf:.2f} → {new_conf:.2f})"
                )
        
        # Validate chemical formula
        if formula and formula != "NOT_FOUND" and product_name:
            validation = self.external_validator.validate_chemical_formula(
                formula, product_name
            )
            
            if "formula" not in extractions:
                extractions["formula"] = {}
            
            extractions["formula"]["external_validation"] = {
                "source": validation.source,
                "is_valid": validation.is_valid,
                "confidence_boost": validation.confidence_boost,
            }
            
            if validation.is_valid:
                old_conf = extractions.get("formula", {}).get("confidence", 0.0)
                new_conf = min(0.99, old_conf + validation.confidence_boost)
                extractions["formula"]["confidence"] = new_conf
                logger.debug(
                    f"Formula validated (conf: {old_conf:.2f} → {new_conf:.2f})"
                )
        
        return extractions
    
    def _apply_confidence_scoring(
        self, extractions: dict[str, dict[str, Any]]
    ) -> dict[str, dict[str, Any]]:
        """
        Apply comprehensive confidence scoring model to all fields.
        
        Args:
            extractions: Current field extractions
        
        Returns:
            Updated extractions with confidence scores and quality tiers
        """
        logger.debug("Applying confidence scoring model")
        
        field_scores = {}
        
        for field_name, field_data in extractions.items():
            if "value" not in field_data:
                continue
            
            # Determine extraction source
            source = FieldSource.HEURISTIC  # Default
            if field_data.get("method") == "llm":
                source = FieldSource.LLM
            elif field_data.get("method") == "rag":
                source = FieldSource.RAG
            elif field_data.get("normalized_value"):
                source = FieldSource.NORMALIZED
            
            # Get validation results
            validation_result = field_data.get("external_validation")
            cross_validated = field_data.get("cross_validated", False)
            
            # Score the field
            score_result = self.confidence_scorer.score_field(
                field_name=field_name,
                value=field_data["value"],
                source=source,
                base_confidence=field_data.get("confidence", 0.70),
                validation_result=validation_result if validation_result and validation_result.get("is_valid") else None,
                cross_validation_passed=cross_validated,
                pattern_match_strength=field_data.get("pattern_strength", 0.80),
                context_indicators=field_data.get("context", []),
            )
            
            # Update field with scoring results
            extractions[field_name]["confidence_score"] = score_result
            extractions[field_name]["quality_tier"] = score_result["quality_tier"]
            extractions[field_name]["passes_threshold"] = score_result["passes_threshold"]
            
            field_scores[field_name] = score_result
        
        # Calculate document-level confidence
        doc_confidence = self.confidence_scorer.aggregate_document_confidence(field_scores)
        
        # Store document-level metrics (for later retrieval if needed)
        extractions["_document_confidence"] = doc_confidence
        
        logger.info(
            f"Document confidence: {doc_confidence['overall_confidence']:.2f} "
            f"({doc_confidence['quality_tier']}) - "
            f"{doc_confidence['fields_above_threshold']}/{doc_confidence['total_fields']} fields pass"
        )
        
        return extractions

    def _log_llm_metrics(self, filename: str) -> None:
        """Log LLM performance metrics for a processed document.

        Args:
            filename: Name of the file being processed
        """
        try:
            # Get metrics from the OllamaClient
            ollama_client = self.llm.ollama
            if not hasattr(ollama_client, "get_metrics_stats"):
                return

            metrics_stats = ollama_client.get_metrics_stats()
            if not metrics_stats:
                return

            # Log cache performance
            cache_stats = ollama_client.get_cache_stats() if hasattr(ollama_client, "get_cache_stats") else {}

            logger.info(
                "LLM Metrics for %s: "
                "Calls=%d Success=%.1f%% AvgLatency=%.2fs Cache_hits=%d Hit_rate=%.1f%%",
                filename,
                metrics_stats.get("total_calls", 0),
                metrics_stats.get("success_rate", 0) * 100,
                metrics_stats.get("latency", {}).get("avg", 0),
                cache_stats.get("hits", 0),
                cache_stats.get("hit_rate", 0) * 100 if cache_stats else 0,
            )
        except Exception as e:
            logger.debug("Failed to log LLM metrics: %s", e)

    def get_llm_metrics_summary(self) -> dict[str, Any] | None:
        """Get current LLM metrics summary for UI display.

        Returns:
            Dictionary with metrics summary or None if not available
        """
        try:
            ollama_client = self.llm.ollama
            if not hasattr(ollama_client, "get_metrics_stats"):
                return None

            metrics_stats = ollama_client.get_metrics_stats()
            cache_stats = ollama_client.get_cache_stats() if hasattr(ollama_client, "get_cache_stats") else {}

            return {
                "total_calls": metrics_stats.get("total_calls", 0),
                "successful_calls": metrics_stats.get("successful_calls", 0),
                "failed_calls": metrics_stats.get("failed_calls", 0),
                "success_rate": metrics_stats.get("success_rate", 0),
                "avg_latency": metrics_stats.get("latency", {}).get("avg", 0),
                "median_latency": metrics_stats.get("latency", {}).get("median", 0),
                "cache_hits": cache_stats.get("hits", 0),
                "cache_misses": cache_stats.get("misses", 0),
                "cache_hit_rate": cache_stats.get("hit_rate", 0),
            }
        except Exception as e:
            logger.debug("Failed to get LLM metrics summary: %s", e)
            return None

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

        # Log final LLM metrics for the batch
        self._log_llm_metrics(f"batch of {len(results)} files")

        logger.info(
            "Batch processing complete: %d successful, %d failed",
            sum(1 for r in results if r.status == "success"),
            sum(1 for r in results if r.status == "failed"),
        )

        return results
