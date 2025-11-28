"""
Utility functions for formatting validation status and quality indicators in UI.
"""
from typing import Any, Dict, Optional


def get_validation_badge(validated: Any) -> str:
    """
    Get validation status badge text.
    
    Args:
        validated: Boolean or string indicating validation status
    
    Returns:
        Badge text (✓, ⚠, ✗, or empty)
    """
    if validated is None or validated == "":
        return ""
    
    # Handle different types
    if isinstance(validated, bool):
        return "✓" if validated else ""
    
    if isinstance(validated, str):
        validated_lower = validated.lower()
        if validated_lower in ("true", "1", "yes"):
            return "✓"
        elif validated_lower in ("false", "0", "no"):
            return ""
    
    if isinstance(validated, (int, float)):
        return "✓" if validated > 0 else ""
    
    return ""


def get_quality_badge(quality_tier: Any) -> str:
    """
    Get quality tier badge.
    
    Args:
        quality_tier: Quality tier string (excellent/good/acceptable/poor/unreliable)
    
    Returns:
        Badge text with emoji
    """
    if not quality_tier or quality_tier == "unknown":
        return ""
    
    tier = str(quality_tier).lower()
    
    badges = {
        "excellent": "🌟",
        "good": "✓",
        "acceptable": "~",
        "poor": "⚠",
        "unreliable": "✗",
    }
    
    return badges.get(tier, "")


def get_quality_color(quality_tier: Any) -> str:
    """
    Get color for quality tier.
    
    Args:
        quality_tier: Quality tier string
    
    Returns:
        Color name/hex code
    """
    if not quality_tier or quality_tier == "unknown":
        return "#gray"
    
    tier = str(quality_tier).lower()
    
    colors = {
        "excellent": "#50fa7b",  # Green
        "good": "#8be9fd",       # Cyan
        "acceptable": "#f1fa8c",  # Yellow
        "poor": "#ffb86c",       # Orange
        "unreliable": "#ff5555",  # Red
    }
    
    return colors.get(tier, "#gray")


def format_confidence(confidence: Optional[float], decimals: int = 2) -> str:
    """
    Format confidence score as percentage.
    
    Args:
        confidence: Confidence value (0-1)
        decimals: Number of decimal places
    
    Returns:
        Formatted percentage string
    """
    if confidence is None:
        return "N/A"
    
    try:
        conf_float = float(confidence)
        return f"{conf_float * 100:.{decimals}f}%"
    except (ValueError, TypeError):
        return "N/A"


def get_validation_tooltip(result: Dict[str, Any]) -> str:
    """
    Generate tooltip text for validation status.
    
    Args:
        result: Database result row with validation info
    
    Returns:
        Tooltip text describing validation status
    """
    parts = []
    
    # Quality tier
    quality = result.get("quality_tier")
    if quality and quality != "unknown":
        parts.append(f"Quality: {quality}")
    
    # Validation status
    validated = result.get("validated")
    if validated:
        parts.append("Externally validated via PubChem")
    
    # Confidence
    confidence = result.get("avg_confidence")
    if confidence is not None:
        parts.append(f"Confidence: {format_confidence(confidence)}")
    
    return " | ".join(parts) if parts else "No validation data"


def format_product_name_with_badges(product_name: str, result: Dict[str, Any]) -> str:
    """
    Format product name with validation and quality badges.
    
    Args:
        product_name: Chemical product name
        result: Database result with validation data
    
    Returns:
        Formatted string with badges
    """
    if not product_name:
        return ""
    
    badges = []
    
    # Quality badge
    quality_badge = get_quality_badge(result.get("quality_tier"))
    if quality_badge:
        badges.append(quality_badge)
    
    # Validation badge
    validation_badge = get_validation_badge(result.get("validated"))
    if validation_badge:
        badges.append(validation_badge)
    
    if badges:
        return f"{product_name} {' '.join(badges)}"
    
    return product_name
