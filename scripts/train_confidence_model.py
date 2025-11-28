#!/usr/bin/env python3
"""
Train the ML confidence model using historical extraction data.
"""
import argparse
from src.database.db_manager import DatabaseManager
from src.sds.ml_confidence_model import MLConfidenceModel, collect_training_data_from_db
from src.utils.logger import get_logger

logger = get_logger(__name__)


def train_model(min_examples: int = 50, force_retrain: bool = False):
    """
    Train ML confidence model from database.
    
    Args:
        min_examples: Minimum training examples required
        force_retrain: Force retraining even if model exists
    """
    print("=" * 80)
    print("ML CONFIDENCE MODEL TRAINING")
    print("=" * 80)
    
    # Initialize database
    db = DatabaseManager()
    
    # Check existing model
    model = MLConfidenceModel()
    
    if model.is_trained and not force_retrain:
        print("\n✓ Model already trained")
        stats = model.get_training_stats()
        print(f"  Training examples: {stats.get('training_examples', 'N/A')}")
        print(f"  RMSE: {stats.get('regression', {}).get('rmse', 'N/A'):.4f}")
        print(f"  Accuracy: {stats.get('classification', {}).get('accuracy', 'N/A'):.2%}")
        print("\nUse --force to retrain")
        return
    
    # Collect training data
    print("\n📊 Collecting training data from database...")
    training_examples = collect_training_data_from_db(db)
    
    if len(training_examples) < min_examples:
        print(f"\n⚠️  Insufficient training data: {len(training_examples)} examples")
        print(f"   Need at least {min_examples} examples for reliable training")
        print("\n💡 Suggestions:")
        print("   1. Process more SDS documents")
        print("   2. Enable external validation to collect quality labels")
        print("   3. Lower min_examples threshold (may reduce accuracy)")
        return
    
    print(f"✓ Collected {len(training_examples)} training examples")
    
    # Analyze training data
    quality_distribution = {}
    for ex in training_examples:
        tier = ex.quality_tier
        quality_distribution[tier] = quality_distribution.get(tier, 0) + 1
    
    print("\n📈 Training Data Distribution:")
    for tier, count in sorted(quality_distribution.items()):
        percentage = count / len(training_examples) * 100
        print(f"  {tier:.<20} {count:>5} ({percentage:>5.1f}%)")
    
    # Train model
    print("\n🔧 Training ML model...")
    stats = model.train(training_examples)
    
    if "error" in stats:
        print(f"\n❌ Training failed: {stats['error']}")
        return
    
    # Display results
    print("\n✅ Training Complete!")
    print("\n📊 Model Performance:")
    print("-" * 80)
    
    print("\nRegression (Confidence Prediction):")
    reg_stats = stats["regression"]
    print(f"  RMSE:     {reg_stats['rmse']:.4f}")
    print(f"  R² Score: {reg_stats['r2_score']:.4f}")
    
    print("\nClassification (Quality Tier):")
    clf_stats = stats["classification"]
    print(f"  Accuracy: {clf_stats['accuracy']:.2%}")
    print(f"  F1 Score: {clf_stats['f1_score']:.4f}")
    
    # Feature importance
    print("\n🔍 Top Feature Importance:")
    print("-" * 80)
    importance = model.get_feature_importance()
    sorted_features = sorted(importance.items(), key=lambda x: x[1], reverse=True)
    
    for i, (feature, score) in enumerate(sorted_features[:10], 1):
        bar = "█" * int(score * 50)
        print(f"  {i:>2}. {feature:.<35} {score:>6.4f} {bar}")
    
    # Recommendations
    print("\n💡 Model Insights:")
    print("-" * 80)
    
    if reg_stats['rmse'] < 0.1:
        print("  ✅ Excellent confidence prediction accuracy")
    elif reg_stats['rmse'] < 0.15:
        print("  ✓ Good confidence prediction accuracy")
    else:
        print("  ⚠️  Moderate confidence prediction accuracy")
        print("     Consider collecting more training data")
    
    if clf_stats['accuracy'] >= 0.85:
        print("  ✅ Excellent quality classification")
    elif clf_stats['accuracy'] >= 0.75:
        print("  ✓ Good quality classification")
    else:
        print("  ⚠️  Moderate quality classification")
        print("     Consider balancing training data across quality tiers")
    
    # Most important features
    top_3 = sorted_features[:3]
    print(f"\n  🎯 Focus on: {', '.join(f[0] for f in top_3)}")
    
    print("\n" + "=" * 80)
    print("Model saved and ready for use!")
    print("=" * 80)


def test_model():
    """Test the trained model with sample extractions."""
    print("=" * 80)
    print("ML CONFIDENCE MODEL TESTING")
    print("=" * 80)
    
    model = MLConfidenceModel()
    
    if not model.is_trained:
        print("\n❌ Model not trained. Run training first:")
        print("   python scripts/train_confidence_model.py")
        return
    
    print("\n✓ Model loaded successfully")
    
    # Test cases
    test_cases = [
        {
            "field_name": "cas_number",
            "value": "7664-93-9",
            "source": "heuristic",
            "context": "CAS Number: 7664-93-9",
            "pattern_strength": 0.95,
            "cross_validated": True,
            "description": "High-quality CAS number extraction"
        },
        {
            "field_name": "product_name",
            "value": "Sulfuric Acid",
            "source": "llm",
            "context": "Product Identification: Sulfuric Acid",
            "pattern_strength": 0.80,
            "cross_validated": False,
            "description": "Good product name extraction"
        },
        {
            "field_name": "hazard_class",
            "value": "8",
            "source": "heuristic",
            "context": "Hazard Class: 8 - Corrosive",
            "pattern_strength": 0.90,
            "cross_validated": True,
            "description": "High-quality hazard class"
        },
        {
            "field_name": "incompatibilities",
            "value": "Avoid contact with metals",
            "source": "rag",
            "context": "Incompatibilities: Avoid contact with metals and organic materials",
            "pattern_strength": 0.60,
            "cross_validated": False,
            "description": "Moderate quality narrative field"
        },
        {
            "field_name": "manufacturer",
            "value": "ABC Corp",
            "source": "llm",
            "context": "Manufacturer: ABC Corp",
            "pattern_strength": 0.70,
            "cross_validated": False,
            "description": "Moderate manufacturer extraction"
        },
    ]
    
    print("\n🧪 Test Predictions:")
    print("-" * 80)
    
    for i, test in enumerate(test_cases, 1):
        print(f"\nTest {i}: {test['description']}")
        print(f"  Field: {test['field_name']}")
        print(f"  Value: {test['value']}")
        print(f"  Source: {test['source']}")
        
        features = model.extract_features(
            field_name=test['field_name'],
            value=test['value'],
            source=test['source'],
            context=test['context'],
            pattern_strength=test['pattern_strength'],
            cross_validated=test['cross_validated'],
        )
        
        prediction = model.predict(features)
        
        print(f"  → Confidence: {prediction['confidence']:.2%}")
        print(f"  → Quality: {prediction['quality_tier']}")
        print(f"  → High Quality: {prediction['is_high_quality']}")
        print(f"  → Model: {prediction['model_type']}")
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train ML confidence model")
    parser.add_argument(
        "--min-examples",
        type=int,
        default=50,
        help="Minimum training examples required (default: 50)"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force retraining even if model exists"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Test the trained model"
    )
    
    args = parser.parse_args()
    
    if args.test:
        test_model()
    else:
        train_model(min_examples=args.min_examples, force_retrain=args.force)
