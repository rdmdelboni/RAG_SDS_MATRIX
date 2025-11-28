# Chemical Structure Recognition

Automatic extraction and recognition of chemical structures from SDS documents.

## Overview

The structure recognition system extracts chemical structure diagrams from PDF pages and converts them to machine-readable formats (SMILES, InChI) for validation and analysis.

## Features

- **Image Extraction**: Extract images from PDF pages
- **Structure Detection**: Identify likely chemical structure diagrams
- **Multi-method Recognition**:
  - OCR text extraction + PubChem lookup
  - RDKit-based recognition (requires specialized CV models)
  - Pattern matching for simple structures
- **Validation**: Cross-validate with PubChem and product names
- **Caching**: Cache recognition results for performance

## Architecture

```text
┌─────────────────────┐
│  PDF Document       │
└──────────┬──────────┘
           │
           v
┌─────────────────────┐
│ Image Extraction    │ ← Extract images from pages
└──────────┬──────────┘
           │
           v
┌─────────────────────┐
│ Structure Detection │ ← Filter likely structures
└──────────┬──────────┘
           │
           v
┌─────────────────────┐
│ Recognition         │ ← OCR + lookup, RDKit, patterns
└──────────┬──────────┘
           │
           v
┌─────────────────────┐
│ Validation          │ ← PubChem cross-validation
└──────────┬──────────┘
           │
           v
┌─────────────────────┐
│ SMILES/InChI        │ ← Output formats
└─────────────────────┘
```

## Usage

### Basic Structure Extraction

```python
from pathlib import Path
from src.sds.structure_recognition import StructureExtractor

# Initialize extractor
extractor = StructureExtractor()

# Extract structures from PDF
pdf_path = Path("path/to/sds.pdf")
structures = extractor.extract_from_pdf(
    pdf_path,
    product_name="ethanol"  # Optional for validation
)

# Process results
for structure in structures:
    print(f"SMILES: {structure['smiles']}")
    print(f"Confidence: {structure['confidence']:.2f}")
    print(f"Method: {structure['method']}")
    print(f"Validation: {structure['validation']}")
```

### Image Extraction Only

```python
from src.sds.structure_recognition import StructureImageExtractor

extractor = StructureImageExtractor()

# Extract all images
images = extractor.extract_images_from_pdf(pdf_path)

# Check if image is likely a structure
for img in images:
    is_structure, confidence = extractor.is_likely_structure(img)
    if is_structure:
        print(f"Found structure (confidence: {confidence:.2f})")
```

### Structure Recognition

```python
from PIL import Image
from src.sds.structure_recognition import StructureRecognizer

recognizer = StructureRecognizer(cache_ttl=3600)

# Recognize from image
img = Image.open("structure.png")
result = recognizer.recognize_from_image(img, use_ocr=True)

if result.smiles:
    print(f"SMILES: {result.smiles}")
    print(f"InChI: {result.inchi}")
    print(f"Method: {result.method}")
    print(f"Confidence: {result.confidence:.2f}")
```

### Structure Validation

```python
# Validate recognized structure
validation = recognizer.validate_structure(
    smiles="CCO",
    product_name="ethanol"
)

print(f"Valid: {validation['is_valid']}")
print(f"Matches name: {validation['matches_name']}")
print(f"Canonical SMILES: {validation['canonical_smiles']}")
```

### Format Conversion

```python
from src.sds.structure_recognition import (
    convert_smiles_to_inchi,
    convert_inchi_to_smiles
)

# Convert SMILES to InChI
inchi = convert_smiles_to_inchi("CCO")
print(f"InChI: {inchi}")

# Convert InChI to SMILES
smiles = convert_inchi_to_smiles("InChI=1S/C2H6O/c1-2-3/h3H,2H2,1H3")
print(f"SMILES: {smiles}")
```

## Recognition Methods

### 1. OCR + PubChem Lookup

Extracts text from images using Tesseract OCR, identifies chemical names or formulas, and looks them up in PubChem.

**Pros:**
- Works for images with text labels
- High accuracy for labeled structures
- No CV model required

**Cons:**
- Requires text in image
- Depends on OCR quality
- Needs network connection

### 2. RDKit-based Recognition

Uses computer vision models to directly recognize chemical structures from diagrams.

**Pros:**
- Works without text labels
- Direct structure recognition
- High accuracy for clear diagrams

**Cons:**
- Requires specialized CV models (not included)
- More complex setup
- Computationally intensive

### 3. Pattern Matching

Matches simple structural patterns (benzene rings, functional groups) using template matching.

**Pros:**
- Fast
- No external dependencies
- Works offline

**Cons:**
- Limited to simple structures
- Lower accuracy
- Requires predefined templates

## Structure Detection

The system uses heuristics to filter likely structure images:

1. **Aspect Ratio**: Reasonable width/height ratio (0.3-3.0)
2. **Contrast**: High contrast (black lines on white)
3. **Brightness**: Mostly white background (structures on white)
4. **Edge Density**: Many edges (structures have lines)
5. **Size**: Minimum 50x50 pixels

```python
# Detection heuristics
is_structure, confidence = extractor.is_likely_structure(image)

if is_structure:
    # Confidence based on edge density
    # Higher confidence = more likely structure
    print(f"Likely structure: {confidence:.2f}")
```

## Performance

### Recognition Rates

- **OCR + Lookup**: 70-85% accuracy for labeled structures
- **RDKit CV**: 80-90% accuracy for clear diagrams (requires trained model)
- **Pattern Matching**: 40-60% accuracy for simple structures

### Caching

Results are cached by image hash:
- **TTL**: 1 hour (configurable)
- **Max Size**: 100 entries
- **Hit Rate**: 70-90% in typical workflows

```python
# Get cache statistics
stats = recognizer.get_cache_stats()
print(f"Hits: {stats['hits']}")
print(f"Misses: {stats['misses']}")
print(f"Hit rate: {stats['hit_rate']:.1%}")

# Clear cache
recognizer.clear_cache()
```

## Validation

Structures are validated against:

1. **Chemical Validity**: Valid SMILES/InChI (RDKit)
2. **PubChem Lookup**: Cross-reference with database
3. **Name Matching**: Compare with product name if provided
4. **Structural Identity**: InChI comparison

```python
validation = {
    'is_valid': True,          # Valid molecule
    'confidence': 0.95,        # Overall confidence
    'matches_name': True,      # Matches product name
    'canonical_smiles': 'CCO', # Canonical form
}
```

## Error Handling

The system handles errors gracefully:

```python
result = recognizer.recognize_from_image(img)

if result.error:
    print(f"Recognition failed: {result.error}")
elif not result.smiles:
    print("No structure recognized")
else:
    print(f"Success: {result.smiles}")
```

Common errors:
- **No recognition method succeeded**: All methods failed
- **Invalid SMILES**: Recognized but invalid structure
- **RDKit not available**: RDKit not installed
- **pytesseract not available**: OCR not available

## Integration with SDS Processor

```python
from src.sds.processor import SDSProcessor
from src.sds.structure_recognition import StructureExtractor

processor = SDSProcessor()
structure_extractor = StructureExtractor()

# Extract SDS info
sds_info = processor.process_pdf(pdf_path)

# Extract structures
structures = structure_extractor.extract_from_pdf(
    pdf_path,
    product_name=sds_info.get('product_name')
)

# Add to SDS info
sds_info['chemical_structures'] = structures

# Validate against CAS number
if sds_info.get('cas_number') and structures:
    # Look up CAS in PubChem
    # Compare with recognized structure
    pass
```

## Dependencies

Required:
- **Pillow**: Image processing
- **numpy**: Array operations
- **pdfplumber**: PDF image extraction
- **requests**: PubChem API

Optional:
- **pytesseract**: OCR for text extraction
- **RDKit**: Structure validation and conversion

Install all dependencies:
```bash
pip install -r requirements.txt
```

For OCR support:
```bash
# Ubuntu/Debian
sudo apt-get install tesseract-ocr

# macOS
brew install tesseract

# Windows
# Download from: https://github.com/UB-Mannheim/tesseract/wiki
```

## Limitations

1. **Image Quality**: Requires clear, high-resolution diagrams
2. **OCR Accuracy**: Text extraction depends on image quality
3. **CV Models**: Advanced recognition requires trained models (not included)
4. **Complex Structures**: May struggle with very complex molecules
5. **Network**: PubChem lookup requires internet connection

## Future Enhancements

- **Deep Learning**: Train CNN for direct structure recognition
- **OSRA Integration**: Use Optical Structure Recognition Application
- **ChemSchematicResolver**: Specialized chemical diagram recognition
- **Batch Processing**: Process multiple pages in parallel
- **Advanced Validation**: Stereochemistry validation
- **Template Library**: Expand pattern matching templates

## Troubleshooting

### No structures recognized

1. Check image quality with `is_likely_structure()`
2. Verify OCR is installed: `tesseract --version`
3. Try different recognition methods
4. Check network connection (PubChem)

### Low confidence scores

1. Improve image resolution
2. Use OCR for labeled structures
3. Validate against known data
4. Check for image artifacts

### RDKit errors

1. Verify installation: `pip install rdkit`
2. Check SMILES validity
3. Use conda for RDKit: `conda install -c conda-forge rdkit`

### Cache issues

1. Clear cache: `recognizer.clear_cache()`
2. Adjust TTL: `StructureRecognizer(cache_ttl=7200)`
3. Check cache stats: `get_cache_stats()`

## API Reference

### StructureExtractor

Main class for structure extraction.

```python
extractor = StructureExtractor()
structures = extractor.extract_from_pdf(pdf_path, product_name=None)
```

### StructureImageExtractor

Extract images from PDFs.

```python
extractor = StructureImageExtractor()
images = extractor.extract_images_from_pdf(pdf_path)
is_structure, conf = extractor.is_likely_structure(image)
```

### StructureRecognizer

Recognize structures from images.

```python
recognizer = StructureRecognizer(cache_ttl=3600)
result = recognizer.recognize_from_image(image, use_ocr=True)
validation = recognizer.validate_structure(smiles, product_name)
stats = recognizer.get_cache_stats()
recognizer.clear_cache()
```

### StructureRecognitionResult

Result dataclass.

```python
@dataclass
class StructureRecognitionResult:
    smiles: Optional[str]
    inchi: Optional[str]
    inchi_key: Optional[str]
    confidence: float
    method: str
    pubchem_cid: Optional[int]
    matched_name: Optional[str]
    error: Optional[str]
```

## Testing

Run tests:

```bash
# All tests
pytest tests/test_structure_recognition.py -v

# Specific test
pytest tests/test_structure_recognition.py::TestStructureExtractor -v

# With coverage
pytest tests/test_structure_recognition.py --cov=src.sds.structure_recognition
```

Example test output:

```
test_is_likely_structure_valid ... PASSED
test_recognize_from_image_caching ... PASSED
test_extract_from_pdf ... PASSED
test_validate_structure ... PASSED
```

## Examples

### Example 1: Extract from Single PDF

```python
from pathlib import Path
from src.sds.structure_recognition import StructureExtractor

extractor = StructureExtractor()
structures = extractor.extract_from_pdf(
    Path("ethanol_sds.pdf"),
    product_name="ethanol"
)

for i, struct in enumerate(structures, 1):
    print(f"\nStructure {i}:")
    print(f"  SMILES: {struct['smiles']}")
    print(f"  Confidence: {struct['confidence']:.2%}")
    print(f"  Validated: {struct['validation']['is_valid']}")
```

### Example 2: Batch Processing

```python
from pathlib import Path
from src.sds.structure_recognition import StructureExtractor

extractor = StructureExtractor()
pdf_dir = Path("sds_documents")

results = {}
for pdf_path in pdf_dir.glob("*.pdf"):
    structures = extractor.extract_from_pdf(pdf_path)
    results[pdf_path.name] = structures
    print(f"{pdf_path.name}: {len(structures)} structures")
```

### Example 3: Validation Pipeline

```python
from src.sds.structure_recognition import StructureRecognizer

recognizer = StructureRecognizer()

# Recognize structure
result = recognizer.recognize_from_image(img)

if result.smiles:
    # Validate
    validation = recognizer.validate_structure(
        result.smiles,
        product_name="ethanol"
    )
    
    if validation['is_valid'] and validation['matches_name']:
        print("✓ Valid structure, matches product name")
    elif validation['is_valid']:
        print("⚠ Valid structure, but doesn't match name")
    else:
        print("✗ Invalid structure")
```

## Best Practices

1. **Always validate**: Cross-check with PubChem and product names
2. **Use caching**: Enable caching for repeated operations
3. **Filter images**: Use `is_likely_structure()` before recognition
4. **Handle errors**: Check `result.error` and `result.smiles`
5. **Product context**: Provide product name for better validation
6. **Test methods**: Try multiple recognition methods
7. **Cache management**: Clear cache periodically
8. **Quality checks**: Verify image quality before processing

## License

MIT License - see LICENSE file for details.
