"""Heuristic-based field extraction using regex patterns."""

from __future__ import annotations

import re
from typing import Any

from ..config.constants import EXTRACTION_FIELDS, UN_NUMBER_RANGE
from ..utils.logger import get_logger

logger = get_logger(__name__)


class HeuristicExtractor:
    """Extract fields using regex patterns (no LLM)."""

    def extract_field(
        self,
        field_name: str,
        text: str,
        sections: dict[int, str] | None = None,
        profile: Any = None,
    ) -> dict[str, Any] | None:
        """Extract a single field using heuristics.

        Args:
            field_name: Field to extract (e.g., 'cas_number')
            text: Full document text
            sections: Extracted SDS sections
            profile: Optional ManufacturerProfile with overrides

        Returns:
            Dictionary with value, confidence, context or None
        """
        # Check for profile regex override
        if profile and profile.regex_overrides and field_name in profile.regex_overrides:
            override_pattern = profile.regex_overrides[field_name]
            try:
                match = re.search(override_pattern, text, re.IGNORECASE | re.MULTILINE)
                if match:
                    val = match.group(1).strip() if match.groups() else match.group(0).strip()
                    context = text[max(0, match.start() - 50) : match.end() + 50].strip()
                    return {
                        "value": val,
                        "confidence": 0.95, # High confidence for profile match
                        "context": context,
                        "source": f"heuristic_profile_{profile.name}",
                    }
            except Exception as e:
                logger.debug(f"Profile regex failed for {field_name}: {e}")

        # Find field definition
        field_def = next(
            (f for f in EXTRACTION_FIELDS if f.name == field_name),
            None,
        )

        if not field_def or not field_def.pattern:
            return None

        # Get search space
        search_text = text
        if field_def.section and sections and field_def.section in sections:
            search_text = sections[field_def.section]

        # Extract using pattern
        match = field_def.pattern.search(search_text)
        if not match:
            return None

        # Extract value (handle groups)
        value = None
        for group_idx in range(1, len(match.groups()) + 1):
            group_val = match.group(group_idx)
            if group_val:
                value = group_val.strip()
                break

        if not value:
            return None

        # Post-process based on field type
        if field_name == "un_number":
            value = self._validate_un_number(value)
            if not value:
                return None
        elif field_name == "cas_number":
            value = self._validate_cas_number(value)
            if not value:
                return None
        elif field_name == "hazard_class":
            value = self._validate_hazard_class(value)
            if not value:
                return None
        elif field_name == "packing_group":
            value = self._normalize_packing_group(value)

        # Get context snippet
        context = search_text[max(0, match.start() - 100) : match.end() + 100].strip()

        return {
            "value": value,
            "confidence": self._estimate_confidence(field_name, value),
            "context": context,
            "source": "heuristic",
        }

    def extract_all_fields(
        self,
        text: str,
        sections: dict[int, str] | None = None,
        profile: Any = None,
    ) -> dict[str, dict[str, Any]]:
        """Extract all fields from document.

        Args:
            text: Full document text
            sections: Extracted sections
            profile: Optional ManufacturerProfile

        Returns:
            Dictionary mapping field names to extraction results
        """
        results = {}

        for field_def in EXTRACTION_FIELDS:
            try:
                result = self.extract_field(field_def.name, text, sections, profile)
                if result:
                    results[field_def.name] = result
            except Exception as e:
                logger.debug("Failed to extract %s: %s", field_def.name, e)

        logger.info("Heuristic extraction found %d fields", len(results))
        return results

    # === Validation Methods ===

    def _validate_un_number(self, value: str) -> str | None:
        """Validate UN number format."""
        # Extract digits only
        digits = re.sub(r"\D", "", value)

        if len(digits) != 4:
            return None

        # Check range
        num = int(digits)
        if not (UN_NUMBER_RANGE[0] <= num <= UN_NUMBER_RANGE[1]):
            return None

        return digits

    def _validate_cas_number(self, value: str) -> str | None:
        """Validate CAS number format."""
        # CAS format: XXXXX-XX-X (2-7 digits, 2 digits, 1 digit)
        if not re.match(r"^\d{2,7}-\d{2}-\d$", value):
            return None
        return value

    def _validate_hazard_class(self, value: str) -> str | None:
        """Validate hazard class format."""
        # Clean up
        value = value.strip()

        # Valid formats: 1, 2.1, 3.2.2, etc.
        if not re.match(r"^\d(?:\.\d)*$", value):
            return None

        return value

    def _normalize_packing_group(self, value: str) -> str:
        """Normalize packing group to Roman numerals."""
        value = value.upper().strip()

        # Convert digits to Roman numerals
        mapping = {"1": "I", "2": "II", "3": "III"}
        return mapping.get(value, value)

    def _estimate_confidence(self, field_name: str, value: str) -> float:
        """Estimate extraction confidence based on field type."""
        base_confidence = {
            "un_number": 0.85,
            "cas_number": 0.80,
            "hazard_class": 0.78,
            "product_name": 0.75,
            "manufacturer": 0.72,
            "packing_group": 0.80,
            "h_statements": 0.70,
            "p_statements": 0.70,
            "incompatibilities": 0.65,
        }.get(field_name, 0.70)

        # Adjust based on value quality
        if not value or len(value) < 2:
            base_confidence -= 0.2
        elif len(value) > 200:
            base_confidence -= 0.1

        return min(0.99, max(0.0, base_confidence))
