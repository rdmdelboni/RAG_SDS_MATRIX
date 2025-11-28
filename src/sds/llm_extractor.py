"""LLM-based field extraction for SDS processing."""

from __future__ import annotations

from typing import Any

from ..config.constants import EXTRACTION_FIELDS
from ..models import get_ollama_client
from ..utils.logger import get_logger

logger = get_logger(__name__)


class LLMExtractor:
    """Extract fields using LLM (with prompt templates)."""

    def __init__(self, ollama_client=None) -> None:
        """Initialize extractor.

        Args:
            ollama_client: OllamaClient instance (uses default if None)
        """
        self.ollama = ollama_client or get_ollama_client()

    def extract_field(
        self,
        field_name: str,
        text: str,
        section_num: int | None = None,
    ) -> dict[str, Any] | None:
        """Extract a field using LLM.

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
        """Extract multiple fields in optimized batch.

        Args:
            fields: List of field names
            text: Document text

        Returns:
            Dictionary mapping field names to results
        """
        logger.info("LLM extracting %d fields", len(fields))

        results = self.ollama.extract_multiple_fields(
            text=text[:6000],
            fields=fields,
        )

        # Convert results
        final_results = {}
        for field_name, result in results.items():
            final_results[field_name] = {
                "value": result.value,
                "confidence": result.confidence,
                "context": result.context,
                "source": "llm",
            }

        return final_results

    def refine_heuristic(
        self,
        field_name: str,
        heuristic_result: dict[str, Any],
        text: str,
    ) -> dict[str, Any]:
        """Refine a heuristic extraction with LLM.

        Args:
            field_name: Field name
            heuristic_result: Result from heuristic extraction
            text: Document text

        Returns:
            Refined result (or original if LLM confidence is lower)
        """
        llm_result = self.extract_field(field_name, text)

        if not llm_result:
            return heuristic_result

        # Use LLM result if confidence is higher
        llm_conf = llm_result.get("confidence", 0.0)
        heur_conf = heuristic_result.get("confidence", 0.0)

        if llm_conf > heur_conf:
            logger.debug(
                "LLM refined %s (%.2f -> %.2f)",
                field_name,
                heur_conf,
                llm_conf,
            )
            return llm_result

        return heuristic_result
