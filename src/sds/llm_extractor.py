"""LLM-based field extraction for SDS processing with advanced features."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from ..config.constants import EXTRACTION_FIELDS
from ..models import get_ollama_client
from ..models.few_shot_examples import FewShotExamples
from ..utils.logger import get_logger

logger = get_logger(__name__)


class LLMExtractor:
    """Extract fields using LLM (with prompt templates and advanced features)."""

    # Critical fields that benefit from consensus validation
    CRITICAL_FIELDS = {"product_name", "cas_number", "un_number", "hazard_class"}

    def __init__(self, ollama_client=None, use_few_shot: bool = True, use_consensus: bool = False) -> None:
        """Initialize extractor with optional advanced features.

        Args:
            ollama_client: OllamaClient instance (uses default if None)
            use_few_shot: Enable few-shot learning (default: True for better accuracy)
            use_consensus: Enable consensus validation for critical fields (default: False)
        """
        self.ollama = ollama_client or get_ollama_client()
        self.few_shot = FewShotExamples()
        self.use_few_shot = use_few_shot
        self.use_consensus = use_consensus

    def extract_field(
        self,
        field_name: str,
        text: str,
        section_num: int | None = None,
    ) -> dict[str, Any] | None:
        """Extract a field using LLM with optional advanced features.

        Args:
            field_name: Field to extract
            text: Document text to analyze
            section_num: Relevant SDS section number

        Returns:
            Dictionary with value, confidence, context
        """
        # Find field definition
        field_def = next(
            (f for f in EXTRACTION_FIELDS if f.name == field_name),
            None,
        )

        if not field_def:
            return None

        # Use field's prompt template
        prompt = field_def.prompt_template.format(text=text[:3000])

        try:
            # Use few-shot learning by default for better accuracy
            if self.use_few_shot:
                result = self.ollama.extract_field_with_few_shot(
                    text=text[:3000],
                    field_name=field_name,
                    prompt_template=prompt,
                )
                logger.debug("Extracted %s with few-shot learning", field_name)
            # Use consensus for critical fields if enabled
            elif self.use_consensus and field_name in self.CRITICAL_FIELDS:
                result = self.ollama.extract_field_with_consensus(
                    text=text[:3000],
                    field_name=field_name,
                    prompt_template=prompt,
                    models=["qwen2.5", "llama3.1"],  # Use available models
                )
                logger.debug("Extracted %s with consensus validation", field_name)
            # Standard extraction as fallback
            else:
                result = self.ollama.extract_field(
                    text=text[:3000],
                    field_name=field_name,
                    prompt_template=prompt,
                    system_prompt=(
                        "You are an expert at extracting information from Safety Data Sheets. "
                        "Respond ONLY in JSON format with keys: 'value', 'confidence' (0.0-1.0), 'context'. "
                        "If not found, use value='NOT_FOUND' and confidence=0.0."
                    ),
                )

            # Convert to dict
            return {
                "value": result.value,
                "confidence": result.confidence,
                "context": result.context,
                "source": "llm",
            }

        except Exception as e:
            logger.error("LLM extraction failed for %s: %s", field_name, e)
            return None

    def extract_multiple_fields(
        self,
        fields: list[str],
        text: str,
    ) -> dict[str, dict[str, Any]]:
        """Extract multiple fields in parallel with few-shot learning.

        Uses ThreadPoolExecutor to parallelize field extraction (typically 4-6 concurrent threads).
        This reduces total extraction time from sequential 10-20s to ~3-5s for typical documents.

        Args:
            fields: List of field names
            text: Document text

        Returns:
            Dictionary mapping field names to results
        """
        logger.info("LLM extracting %d fields (few_shot=%s, parallel=True)", len(fields), self.use_few_shot)

        final_results = {}
        
        # Use parallel extraction with reasonable concurrency (4-6 workers)
        # Ollama can handle multiple concurrent requests from different fields
        max_workers = min(6, max(1, len(fields) // 5 + 1))  # ~1 worker per 5 fields, min 1, max 6
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all field extraction tasks
            future_to_field = {}
            for field_name in fields:
                future = executor.submit(self._extract_single_field, field_name, text)
                future_to_field[future] = field_name
            
            # Collect results as they complete
            for future in as_completed(future_to_field):
                field_name = future_to_field[future]
                try:
                    result = future.result()
                    if result:
                        final_results[field_name] = result
                except Exception as e:
                    logger.error("Failed to extract field %s: %s", field_name, e)
                    continue

        logger.debug("Parallel extraction completed for %d/%d fields", len(final_results), len(fields))
        return final_results

    def _extract_single_field(
        self,
        field_name: str,
        text: str,
    ) -> dict[str, Any] | None:
        """Extract a single field (internal helper for parallel extraction).

        Args:
            field_name: Field to extract
            text: Document text

        Returns:
            Dictionary with value, confidence, context, or None on error
        """
        try:
            # Find field definition
            field_def = next(
                (f for f in EXTRACTION_FIELDS if f.name == field_name),
                None,
            )

            if not field_def:
                logger.warning("Field definition not found: %s", field_name)
                return None

            # Use field's prompt template
            prompt = field_def.prompt_template.format(text=text[:3000])

            # Use few-shot learning by default
            if self.use_few_shot:
                result = self.ollama.extract_field_with_few_shot(
                    text=text[:3000],
                    field_name=field_name,
                    prompt_template=prompt,
                )
            else:
                result = self.ollama.extract_field(
                    text=text[:3000],
                    field_name=field_name,
                    prompt_template=prompt,
                )

            return {
                "value": result.value,
                "confidence": result.confidence,
                "context": result.context,
                "source": "llm",
            }
        except Exception as e:
            logger.error("Failed to extract field %s: %s", field_name, e)
            return None

    def refine_heuristic(
        self,
        field_name: str,
        heuristic_result: dict[str, Any],
        text: str,
    ) -> dict[str, Any]:
        """Refine a heuristic extraction with LLM using few-shot learning.

        Args:
            field_name: Field name
            heuristic_result: Result from heuristic extraction
            text: Document text

        Returns:
            Refined result (or original if LLM confidence is lower)
        """
        # For critical fields, try consensus-based refinement if enabled
        if self.use_consensus and field_name in self.CRITICAL_FIELDS:
            return self._refine_heuristic_with_consensus(field_name, heuristic_result, text)

        # Standard refinement with few-shot learning
        llm_result = self.extract_field(field_name, text)

        if not llm_result:
            return heuristic_result

        # Use LLM result if confidence is higher
        llm_conf = llm_result.get("confidence", 0.0)
        heur_conf = heuristic_result.get("confidence", 0.0)

        if llm_conf > heur_conf:
            logger.debug(
                "LLM refined %s with few-shot (%.2f -> %.2f)",
                field_name,
                heur_conf,
                llm_conf,
            )
            return llm_result

        return heuristic_result

    def _refine_heuristic_with_consensus(
        self,
        field_name: str,
        heuristic_result: dict[str, Any],
        text: str,
    ) -> dict[str, Any]:
        """Refine a heuristic extraction using consensus from multiple models.

        Args:
            field_name: Field name
            heuristic_result: Result from heuristic extraction
            text: Document text

        Returns:
            Consensus result or original if consensus is lower confidence
        """
        try:
            # Find field definition
            field_def = next(
                (f for f in EXTRACTION_FIELDS if f.name == field_name),
                None,
            )

            if not field_def:
                return heuristic_result

            prompt = field_def.prompt_template.format(text=text[:3000])

            consensus_result = self.ollama.extract_field_with_consensus(
                text=text[:3000],
                field_name=field_name,
                prompt_template=prompt,
                models=["qwen2.5", "llama3.1"],
            )

            llm_conf = consensus_result.confidence
            heur_conf = heuristic_result.get("confidence", 0.0)

            if llm_conf > heur_conf:
                logger.debug(
                    "Consensus refined %s (%.2f -> %.2f)",
                    field_name,
                    heur_conf,
                    llm_conf,
                )
                return {
                    "value": consensus_result.value,
                    "confidence": consensus_result.confidence,
                    "context": consensus_result.context,
                    "source": "llm_consensus",
                }

        except Exception as e:
            logger.debug("Consensus refinement failed for %s: %s", field_name, e)

        return heuristic_result
