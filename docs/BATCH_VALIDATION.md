# Batch Validation Feature

## Overview

The batch validation feature enables parallel validation of multiple chemicals against the PubChem database, significantly improving performance when processing multiple SDS documents.

## Features

- **Parallel Processing**: Validates multiple chemicals concurrently using ThreadPoolExecutor
- **Rate Limiting**: Respects PubChem's 5 requests/second limit across all parallel workers
- **Caching**: Leverages existing cache system to avoid redundant API calls
- **Flexible Input**: Supports partial data (product name only, CAS only, or both)
- **Ordered Results**: Returns results in the same order as input items

## Usage

### Basic Batch Validation

```python
from src.sds.external_validator import ExternalValidator, BatchValidationItem

validator = ExternalValidator()

# Create batch items
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

# Validate in parallel
results = validator.validate_batch(items, max_workers=5)

# Process results
for result in results:
    if result.product_name_result:
        print(f"Item {result.index}: valid={result.product_name_result.is_valid}")
```

### Simplified Interface

For simple cases where you just want to validate product names:

```python
product_names = ["Ethanol", "Methanol", "Acetone"]
cas_numbers = ["64-17-5", "67-56-1", "67-64-1"]

results = validator.validate_batch_simple(product_names, cas_numbers)

for i, result in enumerate(results):
    print(f"{product_names[i]}: confidence boost = {result.confidence_boost}")
```

### Partial Data

You can validate items with incomplete data:

```python
items = [
    BatchValidationItem(
        index=0,
        product_name="Benzene"
        # No CAS number provided
    ),
    BatchValidationItem(
        index=1,
        cas_number="71-43-2"
        # No product name provided
    ),
    BatchValidationItem(
        index=2,
        product_name="Toluene",
        cas_number="108-88-3",
        formula="C7H8"
    )
]

results = validator.validate_batch(items)
```

## Performance

### Speedup

With caching and parallel processing:
- **First run**: ~0.6-0.8 seconds for 3 items (with rate limiting)
- **Cached run**: ~0.01-0.05 seconds for 3 items (cache hit)
- **Speedup**: ~20-40x with cache, ~3-4x with parallelism alone

### Rate Limiting

The batch validator enforces PubChem's 5 requests/second limit across all parallel workers:

```python
# With 10 items and 5 workers, minimum time is ~2 seconds
items = [BatchValidationItem(i, product_name=f"Chemical_{i}") for i in range(10)]
results = validator.validate_batch(items, max_workers=5)
# Takes ~2-3 seconds due to rate limiting
```

### Cache Efficiency

The validator caches both successful and failed lookups to avoid redundant API calls:

```python
# Get cache statistics
stats = validator.get_cache_stats()
print(f"Cache hits: {stats['hits']}")
print(f"Cache misses: {stats['misses']}")
print(f"Hit rate: {stats['hit_rate']:.1%}")
print(f"Cache size: {stats['size']}")
```

## Integration with SDS Processor

The batch validation can be integrated into the SDS processor for efficient multi-document processing:

```python
class SDSProcessor:
    def process_batch(self, file_paths: List[Path]) -> List[ProcessingResult]:
        """Process multiple SDS documents with batch validation."""
        # Extract initial data from all documents
        extractions = [self._extract_basic_info(fp) for fp in file_paths]
        
        # Prepare batch validation items
        batch_items = [
            BatchValidationItem(
                index=i,
                product_name=ext.get("product_name"),
                cas_number=ext.get("cas_number")
            )
            for i, ext in enumerate(extractions)
        ]
        
        # Validate all at once
        validation_results = self.external_validator.validate_batch(
            batch_items,
            max_workers=5
        )
        
        # Apply validation results to extractions
        for i, val_result in enumerate(validation_results):
            if val_result.product_name_result:
                extractions[i]["validation"] = val_result.product_name_result
        
        # Continue processing with validated data
        return [self._finalize_processing(fp, ext) 
                for fp, ext in zip(file_paths, extractions)]
```

## API Reference

### BatchValidationItem

Dataclass representing an item to validate:

```python
@dataclass
class BatchValidationItem:
    index: int                          # Position in batch (for result ordering)
    product_name: Optional[str] = None  # Product name to validate
    cas_number: Optional[str] = None    # CAS number to validate
    formula: Optional[str] = None       # Chemical formula to validate
```

### BatchValidationResult

Dataclass representing validation results:

```python
@dataclass
class BatchValidationResult:
    index: int                                          # Position in batch
    product_name_result: Optional[ValidationResult]    # Product name validation
    cas_number_result: Optional[ValidationResult]      # CAS number validation
    formula_result: Optional[ValidationResult]         # Formula validation
    error: Optional[str] = None                        # Error message if failed
```

### Methods

#### validate_batch()

```python
def validate_batch(
    items: List[BatchValidationItem],
    max_workers: int = 5
) -> List[BatchValidationResult]
```

Validate multiple chemicals in parallel with rate limiting.

**Parameters:**
- `items`: List of chemicals to validate
- `max_workers`: Maximum parallel workers (default 5 to match rate limit)

**Returns:**
- List of validation results in the same order as input

#### validate_batch_simple()

```python
def validate_batch_simple(
    product_names: List[str],
    cas_numbers: Optional[List[str]] = None
) -> List[ValidationResult]
```

Simplified batch validation for product names with optional CAS numbers.

**Parameters:**
- `product_names`: List of product names to validate
- `cas_numbers`: Optional list of CAS numbers (same length as product_names)

**Returns:**
- List of validation results for product names

## Testing

Run the batch validation tests:

```bash
pytest tests/test_batch_validation.py -v
```

Or run the standalone demo:

```bash
python tests/test_batch_validation.py
```

## Best Practices

1. **Worker Count**: Use `max_workers=5` to match PubChem's rate limit
2. **Batch Size**: Optimal batch size is 10-50 items for good performance
3. **Cache Warming**: Process common chemicals first to warm the cache
4. **Error Handling**: Check for `error` field in results for individual failures
5. **Progress Tracking**: Log batch completion for long-running operations

## Limitations

- **Rate Limiting**: PubChem enforces 5 requests/second maximum
- **Timeout**: Individual requests timeout after 10 seconds
- **Cache Size**: Default cache holds 500 PubChem responses
- **Memory**: Large batches (>1000 items) may consume significant memory

## Future Enhancements

- [ ] Async/await implementation for better concurrency
- [ ] Progress callbacks for UI integration
- [ ] Configurable retry logic for failed requests
- [ ] Batch size optimization based on cache hit rate
- [ ] Integration with other chemical databases (ChemSpider, NIST)
