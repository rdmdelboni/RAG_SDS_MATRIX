"""Field validation for extracted SDS data."""

from __future__ import annotations

from typing import Any

from ..config.constants import EXTRACTION_FIELDS, HAZARD_CLASSES, VALIDATION_THRESHOLDS
from ..utils.logger import get_logger
from .hazard_calculator import HazardCalculator

logger = get_logger(__name__)


class FieldValidator:
    """Validate extracted fields with confidence-based status."""

    HAZARD_CLASSES = set(HAZARD_CLASSES)

    def __init__(self):
        self.calculator = HazardCalculator()

    def check_consistency(self, extractions: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
        """
        Check internal consistency between composition and hazards.
        Returns a consistency report or None if data is missing.
        """
        comp_text = extractions.get("composition", {}).get("value")
        h_statements = extractions.get("h_statements", {}).get("value")
        
        if not comp_text or not h_statements:
            return None
            
        # Parse components
        components = self.calculator.parse_composition(comp_text)
        if not components:
            return None
            
        # Calculate expected hazards
        calculated = self.calculator.calculate_hazards(components)
        
        # Parse declared hazards (simple split)
        declared = [h.strip() for h in h_statements.split(',') if h.strip()]
        
        # Compare
        return self.calculator.validate_against_declared(calculated, declared)

    def validate_field(
        self,
        field_name: str,
        value: str,
        confidence: float,
    ) -> tuple[str, str | None]:
        """Validate a field and return status.

        Args:
            field_name: Field name
            value: Extracted value
            confidence: Confidence score (0.0-1.0)

        Returns:
            Tuple of (status, message) where status is 'valid', 'warning', or 'invalid'
        """
        # Check for "not found"
        if value.upper() in ("NOT_FOUND", "ERROR", ""):
            return "invalid", f"{field_name} not found in document"

        # Validate based on confidence thresholds
        valid_threshold = VALIDATION_THRESHOLDS["valid"]
        warning_threshold = VALIDATION_THRESHOLDS["warning"]

        if confidence >= valid_threshold:
            status = "valid"
            message = None
        elif confidence >= warning_threshold:
            status = "warning"
            message = f"Low confidence ({confidence:.0%})"
        else:
            status = "invalid"
            message = f"Very low confidence ({confidence:.0%})"

        # Additional field-specific validation
        field_message = self._validate_field_specific(field_name, value)
        if field_message:
            # Downgrade status if specific validation fails
            if status == "valid":
                status = "warning"
            message = field_message

        return status, message

    def _validate_field_specific(self, field_name: str, value: str) -> str | None:
        """Perform field-specific validation.

        Args:
            field_name: Field name
            value: Value to validate

        Returns:
            Error message or None if valid
        """
        if field_name == "un_number":
            if not value.isdigit() or len(value) != 4:
                return "Invalid UN number format (expected 4 digits)"

        elif field_name == "cas_number":
            import re

            if not re.match(r"^\d{2,7}-\d{2}-\d$", value):
                return "Invalid CAS number format"

        elif field_name == "hazard_class":
            if value not in self.HAZARD_CLASSES:
                return f"Unknown hazard class: {value}"

        elif field_name == "packing_group":
            if value not in ("I", "II", "III"):
                return "Packing group must be I, II, or III"

        elif field_name == "product_name":
            if len(value) < 3:
                return "Product name too short"
            if len(value) > 200:
                return "Product name too long"

        elif field_name == "manufacturer":
            if len(value) < 2:
                return "Manufacturer name too short"

        return None

    def is_dangerous(self, hazard_class: str | None) -> bool:
        """Determine if a chemical is dangerous based on hazard class.

        Args:
            hazard_class: UN hazard class

        Returns:
            True if dangerous
        """
        if not hazard_class:
            return False

        # Hazard classes considered dangerous
        dangerous_classes = {
            "1",
            "1.1",
            "1.2",
            "1.3",
            "1.4",
            "1.5",
            "1.6",  # Explosives
            "2.1",
            "2.2",
            "2.3",  # Gases
            "3",  # Flammable liquids
            "4",
            "4.1",
            "4.2",
            "4.3",  # Flammable solids
            "5",
            "5.1",
            "5.2",  # Oxidizers
            "6",
            "6.1",
            "6.2",  # Toxic
            "7",  # Radioactive
            "8",  # Corrosive
        }

        return hazard_class in dangerous_classes

    def calculate_completeness(
        self,
        extractions: dict[str, dict[str, Any]],
        required_fields: list[str] | None = None,
    ) -> float:
        """Calculate data completeness percentage.

        Args:
            extractions: Dictionary of field extractions
            required_fields: List of required fields (uses all if None)

        Returns:
            Completeness percentage (0.0-1.0)
        """
        if required_fields is None:
            required_fields = [f.name for f in EXTRACTION_FIELDS if f.required]

        if not required_fields:
            return 1.0

        filled = 0
        for field_name in required_fields:
            if field_name in extractions:
                value = extractions[field_name].get("value", "")
                if value and value.upper() != "NOT_FOUND":
                    filled += 1

        return filled / len(required_fields)

    def get_overall_confidence(self, extractions: dict[str, dict[str, Any]]) -> float:
        """Calculate average confidence across all extractions.

        Args:
            extractions: Dictionary of field extractions

        Returns:
            Average confidence (0.0-1.0)
        """
        if not extractions:
            return 0.0

        confidences = [
            ext.get("confidence", 0.0)
            for ext in extractions.values()
            if ext.get("value") and ext.get("value").upper() != "NOT_FOUND"
        ]

        if not confidences:
            return 0.0

        return sum(confidences) / len(confidences)


def validate_extraction_result(
    field_name: str,
    result: dict[str, Any],
) -> dict[str, Any]:
    """Validate an extraction result and add status.

    Args:
        field_name: Field name
        result: Extraction result dictionary

    Returns:
        Result with added 'validation_status' and 'validation_message'
    """
    validator = FieldValidator()

    status, message = validator.validate_field(
        field_name,
        result.get("value", ""),
        result.get("confidence", 0.0),
    )

    result["validation_status"] = status
    result["validation_message"] = message

    return result


def validate_full_consistency(extractions: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    """
    Perform cross-field consistency checks on the full extraction set.
    
    Args:
        extractions: Complete dictionary of all extracted fields
        
    Returns:
        Consistency report dictionary or None
    """
    validator = FieldValidator()
    return validator.check_consistency(extractions)
