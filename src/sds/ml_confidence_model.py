"""
Machine Learning-based confidence prediction model for SDS extractions.

Uses historical validation data to train a classifier that predicts extraction quality.
"""
import json
import pickle
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import numpy as np

from ..config.settings import get_settings
from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ExtractionFeatures:
    """Feature vector for ML model."""
    # Pattern features
    pattern_match_strength: float
    value_length: int
    has_special_chars: bool
    has_numbers: bool
    has_uppercase: bool
    
    # Context features
    context_keyword_count: int
    context_length: int
    distance_from_label: int
    
    # Source features
    source_heuristic: bool
    source_llm: bool
    source_rag: bool
    
    # Field-specific features
    field_cas_number: bool
    field_product_name: bool
    field_hazard_class: bool
    field_other: bool
    
    # Cross-validation features
    has_cross_validation: bool
    cross_fields_count: int
    
    def to_array(self) -> np.ndarray:
        """Convert to numpy array for model input."""
        return np.array([
            self.pattern_match_strength,
            float(self.value_length),
            float(self.has_special_chars),
            float(self.has_numbers),
            float(self.has_uppercase),
            float(self.context_keyword_count),
            float(self.context_length),
            float(self.distance_from_label),
            float(self.source_heuristic),
            float(self.source_llm),
            float(self.source_rag),
            float(self.field_cas_number),
            float(self.field_product_name),
            float(self.field_hazard_class),
            float(self.field_other),
            float(self.has_cross_validation),
            float(self.cross_fields_count),
        ])


@dataclass
class TrainingExample:
    """Training example for ML model."""
    features: ExtractionFeatures
    actual_confidence: float
    is_validated: bool
    quality_tier: str


class MLConfidenceModel:
    """
    Machine learning model for predicting extraction confidence.
    
    Uses a simple ensemble of:
    1. Linear regression for continuous confidence scores
    2. Logistic regression for quality classification
    3. Decision tree for feature importance
    """
    
    def __init__(self, model_path: Optional[Path] = None):
        """Initialize ML model."""
        self.model_path = model_path or (get_settings().paths.data / "ml_models" / "confidence_model.pkl")
        self.model_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.is_trained = False
        self.feature_importance = {}
        self.training_stats = {}
        
        # Model components (lazy loaded)
        self._regressor = None
        self._classifier = None
        self._feature_names = [
            "pattern_match_strength",
            "value_length",
            "has_special_chars",
            "has_numbers",
            "has_uppercase",
            "context_keyword_count",
            "context_length",
            "distance_from_label",
            "source_heuristic",
            "source_llm",
            "source_rag",
            "field_cas_number",
            "field_product_name",
            "field_hazard_class",
            "field_other",
            "has_cross_validation",
            "cross_fields_count",
        ]
        
        # Try to load existing model
        self._load_model()
    
    def extract_features(
        self,
        field_name: str,
        value: str,
        source: str,
        context: str = "",
        pattern_strength: float = 0.8,
        cross_validated: bool = False,
        cross_field_count: int = 0,
    ) -> ExtractionFeatures:
        """
        Extract features from an extraction for prediction.
        
        Args:
            field_name: Name of extracted field
            value: Extracted value
            source: Source of extraction (heuristic/llm/rag)
            context: Surrounding text context
            pattern_strength: Regex pattern match quality
            cross_validated: Whether cross-validation passed
            cross_field_count: Number of cross-validated fields
        
        Returns:
            ExtractionFeatures object
        """
        # Value features
        value_length = len(value)
        has_special_chars = any(c in value for c in "!@#$%^&*()[]{}|\\/<>")
        has_numbers = any(c.isdigit() for c in value)
        has_uppercase = any(c.isupper() for c in value)
        
        # Context features
        context_keywords = [
            "product", "chemical", "manufacturer", "cas", "hazard",
            "identification", "section", "number", "class", "un"
        ]
        context_keyword_count = sum(1 for kw in context_keywords if kw.lower() in context.lower())
        context_length = len(context)
        
        # Distance from label (estimate based on context)
        distance_from_label = self._estimate_distance_from_label(field_name, context)
        
        # Source features
        source_lower = source.lower()
        source_heuristic = "heuristic" in source_lower
        source_llm = "llm" in source_lower
        source_rag = "rag" in source_lower
        
        # Field features
        field_lower = field_name.lower()
        field_cas_number = "cas" in field_lower
        field_product_name = "product" in field_lower or "name" in field_lower
        field_hazard_class = "hazard" in field_lower
        field_other = not (field_cas_number or field_product_name or field_hazard_class)
        
        return ExtractionFeatures(
            pattern_match_strength=pattern_strength,
            value_length=value_length,
            has_special_chars=has_special_chars,
            has_numbers=has_numbers,
            has_uppercase=has_uppercase,
            context_keyword_count=context_keyword_count,
            context_length=context_length,
            distance_from_label=distance_from_label,
            source_heuristic=source_heuristic,
            source_llm=source_llm,
            source_rag=source_rag,
            field_cas_number=field_cas_number,
            field_product_name=field_product_name,
            field_hazard_class=field_hazard_class,
            field_other=field_other,
            has_cross_validation=cross_validated,
            cross_fields_count=cross_field_count,
        )
    
    def _estimate_distance_from_label(self, field_name: str, context: str) -> int:
        """Estimate distance from field label in context."""
        if not context:
            return 100  # Unknown
        
        # Look for field label in context
        label_keywords = {
            "product_name": ["product", "chemical name"],
            "manufacturer": ["manufacturer", "supplier"],
            "cas_number": ["cas", "cas number"],
            "un_number": ["un", "un number"],
            "hazard_class": ["hazard class", "classification"],
        }
        
        keywords = label_keywords.get(field_name, [field_name.replace("_", " ")])
        context_lower = context.lower()
        
        min_distance = 100
        for keyword in keywords:
            if keyword in context_lower:
                idx = context_lower.index(keyword)
                # Approximate distance (characters from start)
                min_distance = min(min_distance, idx)
        
        return min_distance
    
    def train(self, training_examples: List[TrainingExample]) -> Dict[str, Any]:
        """
        Train the ML model on historical extraction data.
        
        Args:
            training_examples: List of labeled training examples
        
        Returns:
            Training statistics and metrics
        """
        if len(training_examples) < 10:
            logger.warning(f"Insufficient training data: {len(training_examples)} examples (need at least 10)")
            return {"error": "insufficient_data", "count": len(training_examples)}
        
        logger.info(f"Training ML confidence model with {len(training_examples)} examples")
        
        # Extract features and labels
        X = np.array([ex.features.to_array() for ex in training_examples])
        y_regression = np.array([ex.actual_confidence for ex in training_examples])
        y_classification = np.array([
            1 if ex.quality_tier in ["excellent", "good"] else 0
            for ex in training_examples
        ])
        
        # Split into train/test
        from sklearn.model_selection import train_test_split
        X_train, X_test, y_reg_train, y_reg_test, y_clf_train, y_clf_test = train_test_split(
            X, y_regression, y_classification, test_size=0.2, random_state=42
        )
        
        # Train regression model (for continuous confidence)
        from sklearn.ensemble import RandomForestRegressor
        self._regressor = RandomForestRegressor(
            n_estimators=100,
            max_depth=10,
            random_state=42,
            n_jobs=-1
        )
        self._regressor.fit(X_train, y_reg_train)
        
        # Train classifier (for quality tier)
        from sklearn.ensemble import RandomForestClassifier
        self._classifier = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            random_state=42,
            n_jobs=-1
        )
        self._classifier.fit(X_train, y_clf_train)
        
        # Calculate metrics
        from sklearn.metrics import mean_squared_error, r2_score, accuracy_score, f1_score
        
        reg_predictions = self._regressor.predict(X_test)
        clf_predictions = self._classifier.predict(X_test)
        
        stats = {
            "training_examples": len(training_examples),
            "train_size": len(X_train),
            "test_size": len(X_test),
            "regression": {
                "mse": float(mean_squared_error(y_reg_test, reg_predictions)),
                "rmse": float(np.sqrt(mean_squared_error(y_reg_test, reg_predictions))),
                "r2_score": float(r2_score(y_reg_test, reg_predictions)),
            },
            "classification": {
                "accuracy": float(accuracy_score(y_clf_test, clf_predictions)),
                "f1_score": float(f1_score(y_clf_test, clf_predictions)),
            },
        }
        
        # Feature importance
        self.feature_importance = {
            name: float(importance)
            for name, importance in zip(self._feature_names, self._regressor.feature_importances_)
        }
        
        self.training_stats = stats
        self.is_trained = True
        
        # Save model
        self._save_model()
        
        logger.info(f"Model trained successfully. RMSE: {stats['regression']['rmse']:.4f}, "
                   f"Accuracy: {stats['classification']['accuracy']:.2%}")
        
        return stats
    
    def predict(self, features: ExtractionFeatures) -> Dict[str, Any]:
        """
        Predict confidence score for an extraction.
        
        Args:
            features: Extracted features
        
        Returns:
            Prediction with confidence and quality tier
        """
        if not self.is_trained:
            logger.warning("Model not trained, using fallback prediction")
            return self._fallback_prediction(features)
        
        X = features.to_array().reshape(1, -1)
        
        # Predict confidence (regression)
        confidence = float(self._regressor.predict(X)[0])
        confidence = max(0.0, min(1.0, confidence))  # Clamp to [0, 1]
        
        # Predict quality (classification)
        quality_proba = self._classifier.predict_proba(X)[0]
        is_high_quality = self._classifier.predict(X)[0] == 1
        
        # Map to quality tier
        if confidence >= 0.85:
            quality_tier = "excellent"
        elif confidence >= 0.75:
            quality_tier = "good"
        elif confidence >= 0.60:
            quality_tier = "acceptable"
        elif confidence >= 0.40:
            quality_tier = "poor"
        else:
            quality_tier = "unreliable"
        
        return {
            "confidence": confidence,
            "quality_tier": quality_tier,
            "is_high_quality": bool(is_high_quality),
            "high_quality_probability": float(quality_proba[1]) if len(quality_proba) > 1 else 0.0,
            "model_type": "ml_ensemble",
        }
    
    def _fallback_prediction(self, features: ExtractionFeatures) -> Dict[str, Any]:
        """Simple rule-based fallback when model not trained."""
        # Use a weighted sum of key features
        confidence = 0.5  # Base
        
        confidence += features.pattern_match_strength * 0.2
        confidence += (0.1 if features.source_heuristic else 0.0)
        confidence += (0.08 if features.has_cross_validation else 0.0)
        confidence += (0.05 if features.context_keyword_count > 0 else 0.0)
        
        confidence = max(0.0, min(1.0, confidence))
        
        if confidence >= 0.75:
            quality_tier = "good"
        elif confidence >= 0.60:
            quality_tier = "acceptable"
        else:
            quality_tier = "poor"
        
        return {
            "confidence": confidence,
            "quality_tier": quality_tier,
            "is_high_quality": confidence >= 0.75,
            "high_quality_probability": confidence,
            "model_type": "rule_based_fallback",
        }
    
    def _save_model(self):
        """Save trained model to disk."""
        if not self.is_trained:
            logger.warning("Cannot save untrained model")
            return
        
        model_data = {
            "regressor": self._regressor,
            "classifier": self._classifier,
            "feature_importance": self.feature_importance,
            "training_stats": self.training_stats,
            "feature_names": self._feature_names,
        }
        
        with open(self.model_path, "wb") as f:
            pickle.dump(model_data, f)
        
        logger.info(f"Model saved to {self.model_path}")
    
    def _load_model(self):
        """Load trained model from disk."""
        if not self.model_path.exists():
            logger.debug(f"No existing model found at {self.model_path}")
            return
        
        try:
            with open(self.model_path, "rb") as f:
                model_data = pickle.load(f)
            
            self._regressor = model_data["regressor"]
            self._classifier = model_data["classifier"]
            self.feature_importance = model_data.get("feature_importance", {})
            self.training_stats = model_data.get("training_stats", {})
            self._feature_names = model_data.get("feature_names", self._feature_names)
            
            self.is_trained = True
            logger.info(f"Model loaded from {self.model_path}")
            
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            self.is_trained = False
    
    def get_feature_importance(self) -> Dict[str, float]:
        """Get feature importance scores."""
        return self.feature_importance
    
    def get_training_stats(self) -> Dict[str, Any]:
        """Get training statistics."""
        return self.training_stats


def collect_training_data_from_db(db_manager) -> List[TrainingExample]:
    """
    Collect training examples from database extractions.
    
    Args:
        db_manager: DatabaseManager instance
    
    Returns:
        List of training examples
    """
    logger.info("Collecting training data from database")
    
    # Query extractions with metadata
    query = """
    SELECT 
        e.field_name,
        e.value,
        e.confidence,
        e.source,
        e.context,
        e.validation_status,
        e.metadata
    FROM extractions e
    WHERE e.metadata IS NOT NULL
    AND e.confidence IS NOT NULL
    ORDER BY e.created_at DESC
    """
    
    results = db_manager.conn.execute(query).fetchall()
    
    training_examples = []
    
    for row in results:
        field_name, value, confidence, source, context, validation_status, metadata_json = row
        
        # Parse metadata
        try:
            metadata = json.loads(metadata_json) if metadata_json else {}
        except:
            metadata = {}
        
        # Extract features
        quality_tier = metadata.get("quality_tier", "unknown")
        is_validated = metadata.get("external_validation", {}).get("is_valid", False)
        
        # Skip if no quality tier
        if quality_tier == "unknown":
            continue
        
        # Create features (simplified - would need full context in production)
        features = ExtractionFeatures(
            pattern_match_strength=metadata.get("pattern_match_strength", 0.8),
            value_length=len(value) if value else 0,
            has_special_chars=any(c in (value or "") for c in "!@#$%^&*()[]{}"),
            has_numbers=any(c.isdigit() for c in (value or "")),
            has_uppercase=any(c.isupper() for c in (value or "")),
            context_keyword_count=len(context.split()) if context else 0,
            context_length=len(context) if context else 0,
            distance_from_label=50,  # Default
            source_heuristic="heuristic" in source.lower(),
            source_llm="llm" in source.lower(),
            source_rag="rag" in source.lower(),
            field_cas_number="cas" in field_name.lower(),
            field_product_name="product" in field_name.lower(),
            field_hazard_class="hazard" in field_name.lower(),
            field_other=True,
            has_cross_validation=is_validated,
            cross_fields_count=0,  # Would need to calculate
        )
        
        example = TrainingExample(
            features=features,
            actual_confidence=confidence,
            is_validated=is_validated,
            quality_tier=quality_tier,
        )
        
        training_examples.append(example)
    
    logger.info(f"Collected {len(training_examples)} training examples")
    return training_examples
