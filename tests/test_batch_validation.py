"""
Tests for batch validation functionality.
"""
import time
import pytest
from src.sds.external_validator import (
    ExternalValidator,
    BatchValidationItem,
    BatchValidationResult
)


@pytest.fixture
def validator():
    """Create external validator instance."""
    return ExternalValidator(cache_ttl=3600)


def test_batch_validation_basic(validator):
    """Test basic batch validation with multiple chemicals."""
    items = [
        BatchValidationItem(
            index=0,
            product_name="Sulfuric Acid",
            cas_number="7664-93-9"
        ),
        BatchValidationItem(
            index=1,
            product_name="Sodium Chloride",
            cas_number="7647-14-5"
        ),
        BatchValidationItem(
            index=2,
            product_name="Water",
            cas_number="7732-18-5"
        )
    ]
    
    start_time = time.time()
    results = validator.validate_batch(items, max_workers=3)
    elapsed = time.time() - start_time
    
    # Check results
    assert len(results) == 3
    assert all(isinstance(r, BatchValidationResult) for r in results)
    
    # Results should be in same order as input
    assert results[0].index == 0
    assert results[1].index == 1
    assert results[2].index == 2
    
    # All should have successful validations
    assert results[0].product_name_result is not None
    assert results[0].product_name_result.is_valid
    
    assert results[1].product_name_result is not None
    assert results[1].product_name_result.is_valid
    
    assert results[2].product_name_result is not None
    assert results[2].product_name_result.is_valid
    
    # Batch should be faster than sequential (with cache misses)
    print(f"Batch validation of 3 items took {elapsed:.2f}s")
    assert elapsed < 3.0  # Should be faster than 3 sequential requests


def test_batch_validation_simple(validator):
    """Test simplified batch validation interface."""
    product_names = [
        "Ethanol",
        "Methanol",
        "Acetone"
    ]
    cas_numbers = [
        "64-17-5",
        "67-56-1",
        "67-64-1"
    ]
    
    results = validator.validate_batch_simple(product_names, cas_numbers)
    
    assert len(results) == 3
    assert all(r.is_valid for r in results)
    assert all(r.confidence_boost > 0 for r in results)


def test_batch_validation_with_cache(validator):
    """Test that batch validation uses cache effectively."""
    items = [
        BatchValidationItem(
            index=0,
            product_name="Hydrochloric Acid",
            cas_number="7647-01-0"
        ),
        BatchValidationItem(
            index=1,
            product_name="Hydrochloric Acid",
            cas_number="7647-01-0"
        ),
        BatchValidationItem(
            index=2,
            product_name="Hydrochloric Acid",
            cas_number="7647-01-0"
        )
    ]
    
    # First batch - cache miss
    start1 = time.time()
    validator.validate_batch(items, max_workers=3)
    elapsed1 = time.time() - start1
    
    # Second batch - should use cache
    start2 = time.time()
    validator.validate_batch(items, max_workers=3)
    elapsed2 = time.time() - start2
    
    # Check cache stats
    stats = validator.get_cache_stats()
    assert stats["hits"] > 0
    
    # Second batch should be much faster
    print(f"First batch: {elapsed1:.2f}s, Second batch: {elapsed2:.2f}s")
    assert elapsed2 < elapsed1 * 0.5  # At least 2x faster


def test_batch_validation_partial_data(validator):
    """Test batch validation with partial data."""
    items = [
        BatchValidationItem(
            index=0,
            product_name="Benzene"
            # No CAS number
        ),
        BatchValidationItem(
            index=1,
            cas_number="71-43-2"
            # No product name
        ),
        BatchValidationItem(
            index=2,
            product_name="Toluene",
            cas_number="108-88-3",
            formula="C7H8"
        )
    ]
    
    results = validator.validate_batch(items)
    
    assert len(results) == 3
    
    # First item: only product name validated
    assert results[0].product_name_result is not None
    assert results[0].cas_number_result is None
    
    # Second item: only CAS validated
    assert results[1].product_name_result is None
    assert results[1].cas_number_result is not None
    
    # Third item: all fields validated
    assert results[2].product_name_result is not None
    assert results[2].cas_number_result is not None
    assert results[2].formula_result is not None


def test_batch_validation_invalid_chemicals(validator):
    """Test batch validation with invalid chemicals."""
    items = [
        BatchValidationItem(
            index=0,
            product_name="NotARealChemical123456789",
            cas_number="999-99-9"
        ),
        BatchValidationItem(
            index=1,
            product_name="Sodium Chloride",
            cas_number="7647-14-5"
        )
    ]
    
    results = validator.validate_batch(items)
    
    assert len(results) == 2
    
    # First should be invalid
    assert results[0].product_name_result is not None
    assert not results[0].product_name_result.is_valid
    
    # Second should be valid
    assert results[1].product_name_result is not None
    assert results[1].product_name_result.is_valid


def test_batch_validation_rate_limiting(validator):
    """Test that rate limiting is enforced in batch validation."""
    # Create 10 items
    items = [
        BatchValidationItem(
            index=i,
            product_name=f"Chemical_{i}",
            cas_number=f"{i}-00-0"
        )
        for i in range(10)
    ]
    
    start_time = time.time()
    results = validator.validate_batch(items, max_workers=5)
    elapsed = time.time() - start_time
    
    assert len(results) == 10
    
    # With 5 req/s limit and 10 items, should take at least 2 seconds
    # (even with parallelism, rate limit should enforce minimum time)
    print(f"10 items with rate limiting took {elapsed:.2f}s")
    assert elapsed >= 1.5  # Allow some tolerance


def test_batch_validation_empty_list(validator):
    """Test batch validation with empty list."""
    results = validator.validate_batch([])
    assert results == []


def test_batch_validation_simple_length_mismatch(validator):
    """Test that simple batch validation requires matching lengths."""
    product_names = ["Chemical 1", "Chemical 2"]
    cas_numbers = ["123-45-6"]  # Wrong length
    
    with pytest.raises(ValueError, match="same length"):
        validator.validate_batch_simple(product_names, cas_numbers)


def test_batch_validation_progress(validator):
    """Test batch validation with progress tracking."""
    # Create multiple items
    items = [
        BatchValidationItem(
            index=i,
            product_name=f"Test Chemical {i}",
            cas_number=f"{1000+i}-00-0"
        )
        for i in range(5)
    ]
    
    results = validator.validate_batch(items, max_workers=3)
    
    # All results should be present even if validation fails
    assert len(results) == 5
    assert all(r.index in range(5) for r in results)
    
    # Results should be sorted by index
    assert results == sorted(results, key=lambda r: r.index)


if __name__ == "__main__":
    # Run simple test
    validator = ExternalValidator()
    
    print("Testing batch validation...")
    items = [
        BatchValidationItem(0, product_name="Sulfuric Acid", cas_number="7664-93-9"),
        BatchValidationItem(1, product_name="Sodium Chloride", cas_number="7647-14-5"),
        BatchValidationItem(2, product_name="Water", cas_number="7732-18-5"),
    ]
    
    start = time.time()
    results = validator.validate_batch(items, max_workers=3)
    elapsed = time.time() - start
    
    print(f"\nCompleted in {elapsed:.2f}s")
    for result in results:
        print(f"  Item {result.index}: valid={result.product_name_result.is_valid if result.product_name_result else False}")
    
    # Test cache
    print("\nTesting cache (second run)...")
    start = time.time()
    results2 = validator.validate_batch(items, max_workers=3)
    elapsed2 = time.time() - start
    print(f"Completed in {elapsed2:.2f}s (cache speedup: {elapsed/elapsed2:.1f}x)")
    
    stats = validator.get_cache_stats()
    print(f"Cache stats: {stats}")
