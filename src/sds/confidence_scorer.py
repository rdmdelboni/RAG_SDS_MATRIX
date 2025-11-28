"""
Confidence scoring model for SDS field extraction quality assessment.
"""
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from enum import Enum

from ..utils.logger import get_logger

logger = get_logger(__name__)


class FieldSource(Enum):
    """Source of field extraction."""
    HEURISTIC = "heuristic"
    LLM = "llm"
    RAG = "rag"
    EXTERNAL_API = "external_api"
    NORMALIZED = "normalized"
    CROSS_VALIDATED = "cross_validated"


@dataclass
class ConfidenceFactors:
    """Factors contributing to field confidence score."""
    base_score: float  # Initial extraction confidence
    source_weight: float  # Weight based on extraction source
    validation_boost: float  # Boost from external validation
    cross_validation_boost: float  # Boost from field consistency
    pattern_quality: float  # Quality of regex match (if applicable)
    context_score: float  # Contextual evidence strength
    
    def calculate_final_score(self) -> float:
        """
        Calculate final confidence score.
        
        Combines all factors with diminishing returns to prevent
        scores from exceeding 1.0 unrealistically.
        """
        # Start with base score
        score = self.base_score
        
        # Add weighted source reliability
        score += self.source_weight * 0.15
        
        # Add validation boosts (with diminishing returns)
        total_boost = self.validation_boost + self.cross_validation_boost
        score += total_boost * (1.0 - score)  # Boost scales with remaining uncertainty
        
        # Factor in pattern and context quality
        quality_factor = (self.pattern_quality + self.context_score) / 2
        score = score * quality_factor
        
        # Clamp to [0, 1]
        return max(0.0, min(1.0, score))


class ConfidenceScorer:
    """
    Model for scoring confidence in extracted SDS fields.
    
    Combines multiple signals:
    - Extraction source reliability (heuristic > LLM > RAG)
    - External validation (PubChem, etc.)
    - Cross-field consistency
    - Pattern match quality
    - Contextual evidence
    """
    
    # Source reliability weights (higher = more reliable)
    SOURCE_WEIGHTS = {
        FieldSource.HEURISTIC: 1.0,  # Direct regex extraction
        FieldSource.LLM: 0.85,  # LLM extraction
        FieldSource.RAG: 0.70,  # RAG-based completion
        FieldSource.EXTERNAL_API: 0.90,  # External validation
        FieldSource.NORMALIZED: 0.95,  # Normalized value
        FieldSource.CROSS_VALIDATED: 0.95,  # Cross-field validation
    }
    
    # Field-specific confidence thresholds
    FIELD_THRESHOLDS = {
        "product_name": 0.75,  # High threshold for critical field
        "manufacturer": 0.70,
        "cas_number": 0.80,  # Very high - must be accurate
        "un_number": 0.80,
        "hazard_class": 0.70,
        "packing_group": 0.65,
        "incompatibilities": 0.60,  # Lower - often narrative
        "formula": 0.70,
        "physical_state": 0.60,
    }
    
    def __init__(self):
        pass
    
    def score_field(
        self,
        field_name: str,
        value: str,
        source: FieldSource,
        base_confidence: float = 0.70,
        validation_result: Optional[Any] = None,
        cross_validation_passed: bool = False,
        pattern_match_strength: float = 0.80,
        context_indicators: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Calculate comprehensive confidence score for an extracted field.
        
        Args:
            field_name: Name of the field being scored
            value: Extracted value
            source: Source of extraction
            base_confidence: Initial confidence from extraction method
            validation_result: Optional external validation result
            cross_validation_passed: Whether cross-field validation succeeded
            pattern_match_strength: Quality of pattern match (0-1)
            context_indicators: List of contextual keywords found near extraction
        
        Returns:
            Dict with confidence score and contributing factors
        """
        # Get source weight
        source_weight = self.SOURCE_WEIGHTS.get(source, 0.70)
        
        # Calculate validation boost
        validation_boost = 0.0
        if validation_result:
            if hasattr(validation_result, "is_valid") and validation_result.is_valid:
                validation_boost = validation_result.confidence_boost
        
        # Calculate cross-validation boost
        cross_validation_boost = 0.08 if cross_validation_passed else 0.0
        
        # Calculate context score
        context_score = self._calculate_context_score(field_name, context_indicators)
        
        # Build confidence factors
        factors = ConfidenceFactors(
            base_score=base_confidence,
            source_weight=source_weight,
            validation_boost=validation_boost,
            cross_validation_boost=cross_validation_boost,
            pattern_quality=pattern_match_strength,
            context_score=context_score,
        )
        
        final_score = factors.calculate_final_score()
        
        # Determine quality tier
        threshold = self.FIELD_THRESHOLDS.get(field_name, 0.70)
        quality_tier = self._get_quality_tier(final_score, threshold)
        
        return {
            "confidence": final_score,
            "quality_tier": quality_tier,
            "threshold": threshold,
            "passes_threshold": final_score >= threshold,
            "factors": {
                "base_score": factors.base_score,
                "source": source.value,
                "source_weight": factors.source_weight,
                "validation_boost": factors.validation_boost,
                "cross_validation_boost": factors.cross_validation_boost,
                "pattern_quality": factors.pattern_quality,
                "context_score": factors.context_score,
            },
        }
    
    def _calculate_context_score(self, field_name: str, indicators: Optional[List[str]]) -> float:
        """
        Score based on contextual evidence near extraction.
        
        Args:
            field_name: Field being extracted
            indicators: Keywords/phrases found in context
        
        Returns:
            Context score (0-1)
        """
        if not indicators:
            return 0.70  # Neutral when no context available
        
        # Field-specific context keywords (high-value indicators)
        context_keywords = {
            "product_name": ["product", "identification", "chemical name", "substance"],
            "manufacturer": ["manufacturer", "supplier", "company", "producer"],
            "cas_number": ["cas", "registry", "cas-no", "cas no"],
            "un_number": ["un", "un number", "un no", "un-no"],
            "hazard_class": ["hazard", "class", "classification", "category"],
            "packing_group": ["packing", "group", "pg"],
            "incompatibilities": ["incompatible", "avoid", "reactive", "stability"],
        }
        
        relevant_keywords = context_keywords.get(field_name, [])
        if not relevant_keywords:
            return 0.75  # Neutral for fields without defined keywords
        
        # Count matching indicators
        matches = sum(
            1 for indicator in indicators
            for keyword in relevant_keywords
            if keyword.lower() in indicator.lower()
        )
        
        # Score based on match density
        if matches == 0:
            return 0.60  # No context match - lower confidence
        elif matches == 1:
            return 0.80  # Single match - good
        elif matches >= 2:
            return 0.95  # Multiple matches - excellent
        
        return 0.75
    
    def _get_quality_tier(self, score: float, threshold: float) -> str:
        """
        Classify confidence score into quality tiers.
        
        Args:
            score: Confidence score
            threshold: Field-specific threshold
        
        Returns:
            Quality tier label
        """
        if score >= threshold + 0.15:
            return "excellent"
        elif score >= threshold:
            return "good"
        elif score >= threshold - 0.10:
            return "acceptable"
        elif score >= threshold - 0.20:
            return "poor"
        else:
            return "unreliable"
    
    def aggregate_document_confidence(self, field_scores: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calculate overall document extraction confidence.
        
        Args:
            field_scores: Dict of field_name -> score_result
        
        Returns:
            Aggregated document-level confidence metrics
        """
        if not field_scores:
            return {
                "overall_confidence": 0.0,
                "quality_tier": "unreliable",
                "fields_above_threshold": 0,
                "total_fields": 0,
                "critical_fields_ok": False,
            }
        
        # Critical fields that must pass
        critical_fields = ["product_name", "cas_number"]
        
        scores = [s["confidence"] for s in field_scores.values()]
        passes = [s["passes_threshold"] for s in field_scores.values()]
        
        overall_confidence = sum(scores) / len(scores) if scores else 0.0
        fields_above_threshold = sum(passes)
        total_fields = len(field_scores)
        
        # Check critical fields
        critical_fields_ok = all(
            field_scores.get(field, {}).get("passes_threshold", False)
            for field in critical_fields
            if field in field_scores
        )
        
        # Determine overall quality tier
        if overall_confidence >= 0.85 and critical_fields_ok:
            quality_tier = "excellent"
        elif overall_confidence >= 0.75 and critical_fields_ok:
            quality_tier = "good"
        elif overall_confidence >= 0.65:
            quality_tier = "acceptable"
        elif overall_confidence >= 0.50:
            quality_tier = "poor"
        else:
            quality_tier = "unreliable"
        
        return {
            "overall_confidence": overall_confidence,
            "quality_tier": quality_tier,
            "fields_above_threshold": fields_above_threshold,
            "total_fields": total_fields,
            "threshold_pass_rate": fields_above_threshold / total_fields if total_fields > 0 else 0.0,
            "critical_fields_ok": critical_fields_ok,
        }
