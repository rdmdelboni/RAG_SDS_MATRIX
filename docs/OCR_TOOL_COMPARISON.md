# OCR Tools Comparison: keras-ocr vs TrOCR vs docTR

## Executive Summary

For an SDS extraction pipeline requiring **speed** and **accuracy** on technical documents, **docTR** is the recommended choice due to its superior performance on structured documents, excellent speed-to-accuracy ratio, active maintenance, and production-ready features for table extraction.

---

## 1. Speed (Inference Time per Page)

### docTR ⭐ **Best for Production**
- **Detection (db_resnet50)**: ~1.1 sec/page (1024×1024 @ 2.30 GHz CPU)
- **Text Recognition (crnn_vgg16_bn)**: ~0.6 sec/batch of 64 words
- **End-to-End (db_resnet50 + crnn_vgg16_bn)**: ~2-3 seconds per page
- **Fast Models Available**: `db_mobilenet_v3_large` (0.5 sec detection), `viptr_tiny` (0.08 sec recognition)
- **GPU Optimization**: Significant speedup with CUDA/MPS support
- **Batch Processing**: Highly optimizable with configurable batch sizes (detection bs: default 2, recognition bs: default 128)

**Throughput**: ~300-1200 pages/hour depending on model selection and hardware

### keras-ocr
- **Latency**: ~417-699 ms per page (on Tesla P4 GPU with scale factor 2-3)
- **CPU Performance**: Slower than docTR on CPU; GPU dependent
- **Batch Processing**: Limited batch optimization capabilities
- **Throughput**: ~200-500 pages/hour on GPU

**Note**: keras-ocr benchmarks from COCO-Text dataset (scene text, not document-specific)

### TrOCR ⚠️ **Slowest for Structured Documents**
- **Inference**: Model-dependent (Small/Base/Large variants)
- **Latency**: ~300-500 ms per text line (line-level recognition, not full page)
- **Page-Level Processing**: Requires separate text detection step
- **Throughput**: ~100-300 pages/hour depending on text density and model size
- **Limitation**: Designed for line-level recognition; requires preprocessing for page layout

**Note**: TrOCR optimized for handwriting/scene text, not optimized for batch processing of full documents

---

## 2. Accuracy (Especially for Technical/Structured Text)

### docTR ⭐ **Best for Technical Documents**

#### Document-Specific Benchmarks (FUNSD & CORD datasets):
- **End-to-End Performance** (db_resnet50 + crnn_vgg16_bn):
  - Recall: 73.37% | Precision: 76.11% (FUNSD - forms)
  - Recall: 84.80% | Precision: 79.09% (CORD - receipts)

- **Comparison with Cloud Services**:
  - **docTR**: Recall 73.37% vs AWS Textract 78.10% (competitive)
  - **docTR**: Precision 76.11% vs Azure Form Recognizer 85.89% (close)
  - **docTR**: Open-source alternative with comparable accuracy to $0.15-0.40/page cloud APIs

#### Text Detection Accuracy (db_resnet50):
- FUNSD: Recall 83.56%, Precision 86.68%
- CORD: Recall 92.61%, Precision 86.39%

#### Text Recognition Accuracy (crnn_vgg16_bn):
- Exact match: 88.21% (FUNSD)
- Partial match: 88.95% (FUNSD)

#### Strengths for SDS:
✅ Handles **rotated/skewed documents** (via polygon detection)  
✅ **Table-aware** with block and line grouping  
✅ **Layout preservation** with geometric bounding boxes  
✅ **Multi-language support** (French, English, and extensible vocabs)  
✅ Trained on **form documents** (FUNSD) → excellent for structured SDS tables

### TrOCR
- **Handwritten Text**: CER 2.89% (Large model on IAM dataset)
- **Printed Text**: F1 96.60% (SROIE dataset - receipts)
- **Technical Accuracy**: Good for clean, printed text but not optimized for complex layouts

#### Weaknesses for SDS:
❌ **No built-in table detection** or layout understanding  
❌ Designed for **line-level recognition** (no page-level layout reconstruction)  
❌ Requires **manual preprocessing** to segment text regions  
❌ Best for clean documents; struggles with forms and structured layouts  
❌ Chemical formulas and special characters: No benchmarking

### keras-ocr
- **Accuracy**: 53% precision, 50% recall on COCO-Text (scene text)
- **Comparison**: Underperforms vs cloud APIs (GCP: 53% precision, AWS: 45%)
- **Strengths**: Good for general text detection (CRAFT detector is robust)

#### Weaknesses for SDS:
❌ **Designed for scene text**, not document text  
❌ **Poor structured text handling** (tables, forms)  
❌ Limited accuracy on technical documents  
❌ Case/punctuation insensitive → problematic for chemical notation  
❌ Outdated (last release: Sep 2020, 1,500+ unresolved issues)

---

## 3. Resource Requirements

### docTR ⭐ **Most Efficient**

| Aspect | Details |
|--------|---------|
| **GPU Memory** | 2-4 GB for inference (easily fits on mid-range GPUs) |
| **CPU Performance** | Excellent; CPU-viable for non-real-time applications |
| **Model Sizes** | Detection: 4.2-28.8 MB; Recognition: 2.1-58.7 MB |
| **Total Load Time** | ~2-5 seconds for full model |
| **Inference Speed (CPU)** | ~1-5 sec/page (CPU-optimized) |
| **PyTorch Backend** | Supports PyTorch 1.9+ |
| **Quantization** | Supports model export and optimization (ONNX, TorchScript) |
| **Docker Support** | Official Docker images with CUDA 12.2 support |

**Minimal Dependencies**:
```
python-doctr
pytorch
torchvision
opencv-python
pillow
```

### TrOCR

| Aspect | Details |
|--------|---------|
| **GPU Memory** | 4-8 GB recommended (transformer models are heavier) |
| **Model Sizes** | Small: 62M; Base: 334M; Large: 558M |
| **Total Load Time** | ~5-10 seconds |
| **Inference Speed (CPU)** | Slow on CPU; GPU recommended |
| **PyTorch/TensorFlow** | Transformer-based; requires HuggingFace |
| **Dependencies** | transformers, torch, PIL |

**Cons for SDS**:
- Larger memory footprint than docTR
- No native document detection (requires external detector)
- Not optimized for batch processing

### keras-ocr

| Aspect | Details |
|--------|---------|
| **GPU Memory** | 4-6 GB (dynamic allocation with MEMORY_GROWTH) |
| **Model Sizes** | CRAFT detector + CRNN recognizer (combined ~30-50 MB) |
| **TensorFlow Dependency** | Heavy; TensorFlow 2.0+ |
| **Dependencies** | tensorflow, keras, opencv, imgaug |
| **Maintenance** | ⚠️ Community maintained; last update Sep 2020 |
| **Dependency Conflicts** | Known OpenCV-related issues |

**Cons**:
- TensorFlow can be heavy to install
- OpenCV flavor conflicts
- Less active maintenance

---

## 4. Ease of Integration

### docTR ⭐ **Best Developer Experience**

```python
from doctr.io import DocumentFile
from doctr.models import ocr_predictor

# 3-line initialization
model = ocr_predictor(pretrained=True)
doc = DocumentFile.from_pdf("path/to/sds.pdf")
result = model(doc)

# Structured output with geometry
for page in result.pages:
    for block in page.blocks:
        for line in block.lines:
            for word in line.words:
                print(f"{word.value} @ {word.geometry}")
```

**Advantages**:
✅ **Clean Python API** with intuitive method chaining  
✅ **PDF support built-in** (from_pdf, from_images, from_url)  
✅ **Structured output** (Document → Pages → Blocks → Lines → Words)  
✅ **Geometry preservation** (coordinates, bounding boxes, confidence scores)  
✅ **JSON export** for downstream processing  
✅ **XML/hOCR export** for compatibility  
✅ **GPU/MPS support** seamlessly integrated  
✅ **Batch processing** easily tunable  
✅ Excellent **documentation** with examples

### TrOCR

```python
from transformers import TrOCRProcessor, VisionEncoderDecoderModel
from PIL import Image
import requests

processor = TrOCRProcessor.from_pretrained('microsoft/trocr-large-handwritten')
model = VisionEncoderDecoderModel.from_pretrained('microsoft/trocr-large-handwritten')

# Requires manual text detection + cropping
pixel_values = processor(images=image, return_tensors="pt").pixel_values
generated_ids = model.generate(pixel_values)
text = processor.batch_decode(generated_ids, skip_special_tokens=True)[0]
```

**Challenges**:
❌ **Line-level only** (requires external text detection)  
❌ **No PDF support** (must convert to images first)  
❌ **Manual preprocessing** required for layout  
❌ **Limited geometry output** (text only, no bounding boxes)  
❌ Setup requires HuggingFace + PyTorch knowledge

### keras-ocr

```python
import keras_ocr
import matplotlib.pyplot as plt

pipeline = keras_ocr.pipeline.Pipeline()
images = [keras_ocr.tools.read(url) for url in urls]
prediction_groups = pipeline.recognize(images)

for predictions in prediction_groups:
    for word, box in predictions:
        print(f"{word} @ {box}")
```

**Issues**:
⚠️ **High-level API** but less flexible  
⚠️ **No PDF support** (must use PIL/OpenCV for preprocessing)  
⚠️ **Limited configuration** for advanced use cases  
⚠️ **Outdated** (last active development 2020)  
⚠️ Documentation sparse; fewer examples

---

## 5. Best Use Cases & Limitations

### docTR
**Best For**:
- ✅ **Production OCR pipelines** (actively maintained, tested)
- ✅ **Structured document extraction** (forms, receipts, SDS)
- ✅ **Table-aware processing** (block/line grouping)
- ✅ **Multi-language documents** (French, English, extensible)
- ✅ **Rotated/skewed documents** (handles polygons)
- ✅ **Accuracy-critical applications** (competitive with cloud APIs)
- ✅ **Resource-constrained environments** (efficient inference)
- ✅ **Batch processing at scale** (tunable batch sizes)

**Limitations**:
- ❌ Vocabulary limited (trained on specific vocabs; special characters may need fine-tuning)
- ❌ Not optimized for handwriting (compared to TrOCR)
- ❌ Requires PyTorch (not available in TF)
- ❌ Chemical formulas: Depends on training data (may need fine-tuning)

### TrOCR
**Best For**:
- ✅ **Handwritten text recognition** (optimized on IAM dataset)
- ✅ **High-accuracy printed text** (96.60% F1 on SROIE receipts)
- ✅ **Transformer-based models** (if already using HuggingFace)
- ✅ **Scene text recognition** (natural images)

**Limitations**:
- ❌ **No page layout understanding** (line-level recognition only)
- ❌ **No table detection** (requires external detector)
- ❌ **Not document-optimized** (designed for scene text/forms)
- ❌ **Slow page-level processing** (requires per-line inference)
- ❌ **No PDF support** (manual conversion needed)
- ❌ **Heavy models** (338-558M parameters for Base/Large)
- ❌ **Chemical notation**: No specialized training; may struggle

### keras-ocr
**Best For**:
- ✅ **Quick prototyping** (simple API)
- ✅ **Scene text detection** (CRAFT detector is robust)
- ✅ **Projects with TensorFlow backend** (already using TF ecosystem)

**Limitations**:
- ❌ **Outdated & unmaintained** (last update Sep 2020)
- ❌ **Poor document accuracy** (designed for scene text)
- ❌ **No table support**
- ❌ **No PDF processing** (images only)
- ❌ **Limited configuration**
- ❌ **Dependency conflicts** (OpenCV flavors)
- ❌ **Case/punctuation insensitive** (problematic for chemistry)
- ❌ **Large codebase** (less maintainable)

---

## 6. Suitability for SDS PDF Processing

### Evaluation Criteria

| Criterion | Weight | docTR | TrOCR | keras-ocr |
|-----------|--------|-------|-------|-----------|
| **Structured Text/Tables** | 20% | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐ |
| **Speed on Technical Docs** | 15% | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ |
| **Chemical Formula Accuracy** | 15% | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐ |
| **Resource Efficiency** | 10% | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ |
| **Integration Ease** | 10% | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ |
| **Production Readiness** | 10% | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐ |
| **Active Maintenance** | 10% | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐ |
| **Extensibility** | 10% | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ |

**Final Score**: 
- docTR: **4.8/5.0** ✅
- TrOCR: **2.6/5.0**
- keras-ocr: **2.0/5.0**

### SDS-Specific Features

#### docTR ✅ **Optimized for SDS**
```
✓ PDF-to-text pipeline (built-in)
✓ Table detection via block/line grouping
✓ Hazard section identification (structured blocks)
✓ Chemical notation support (with fine-tuning)
✓ Page orientation handling (rotated/skewed SDS common)
✓ Geometric coordinates for field extraction
✓ Confidence scores for validation
✓ Batch processing for multi-page SDS documents
✓ Ready for downstream NLP/tagging
```

**Example SDS Processing Pipeline**:
```python
from doctr.io import DocumentFile
from doctr.models import ocr_predictor

model = ocr_predictor(pretrained=True)

# Process multi-page SDS
doc = DocumentFile.from_pdf("safety_data_sheet.pdf")
result = model(doc)

# Extract structured data
for page_idx, page in enumerate(result.pages):
    for block in page.blocks:
        # Identify section headers (e.g., "Hazard Identification")
        for line in block.lines:
            text = " ".join([w.value for w in line.words])
            geometry = line.geometry
            confidence = min([w.confidence for w in line.words])
            print(f"Section: {text} @ {geometry} (confidence: {confidence})")
```

#### TrOCR ⚠️ **Not Ideal for SDS**
```
✗ No page-level layout understanding
✗ Requires manual text detection (complexity)
✗ No table support
✗ Slow for multi-page processing
✗ Manual preprocessing for geometry
```

#### keras-ocr ❌ **Poor for SDS**
```
✗ Designed for scene text, not documents
✗ Outdated (no recent updates)
✗ Limited table handling
✗ No PDF native support
✗ Case/punctuation issues break chemical notation
```

---

## Recommendation for SDS Extraction Pipeline

### **Primary Choice: docTR** ✅

**Why docTR for SDS extraction**:

1. **Speed + Accuracy Balance**: 2-3 sec/page with 73-93% accuracy (depending on content)
2. **Structured Document Support**: Built for forms/receipts; transfers to SDS
3. **Table Awareness**: Block/line detection preserves layout critical for hazard tables
4. **Production Ready**: Actively maintained, Docker support, API templates
5. **Extensible**: Fine-tune on SDS-specific data to improve chemical notation
6. **Cost**: Open-source alternative to $0.15-0.40/page cloud APIs
7. **Integration**: Works seamlessly with your RAG pipeline for downstream processing

**Implementation Strategy**:
```python
# 1. Extract text and geometry from SDS PDFs
from doctr.io import DocumentFile
from doctr.models import ocr_predictor
import json

model = ocr_predictor(pretrained=True)

def process_sds(pdf_path):
    doc = DocumentFile.from_pdf(pdf_path)
    result = model(doc)
    
    sds_data = {
        "pages": [],
        "sections": {}
    }
    
    for page_idx, page in enumerate(result.pages):
        page_text = []
        for block in page.blocks:
            for line in block.lines:
                words_with_coords = [
                    {
                        "text": word.value,
                        "confidence": word.confidence,
                        "geometry": word.geometry
                    }
                    for word in line.words
                ]
                page_text.append({
                    "line": " ".join([w["text"] for w in words_with_coords]),
                    "words": words_with_coords,
                    "confidence": min([w["confidence"] for w in words_with_coords])
                })
        
        sds_data["pages"].append({
            "page_num": page_idx + 1,
            "content": page_text
        })
    
    return sds_data

# 2. Feed into your RAG enrichment system
sds_content = process_sds("path/to/sds.pdf")
# Pass to graph construction, LLM enrichment, etc.
```

**Optional Enhancements**:
- **Fine-tune on SDS-specific data** (~500-1000 examples) to improve chemical notation recognition
- **Combine with layout analysis** (pypdf, pdfplumber) to identify sections before OCR
- **Use confidence filtering** to flag low-confidence chemical formulas for manual review
- **Integrate with entity recognition** (NER) to extract hazard categories, GHS pictograms, etc.

### **Secondary Choice: TrOCR** (if handwritten annotations common)
Only use if SDS documents contain significant handwritten content requiring 96%+ accuracy on handwriting.

### **Avoid: keras-ocr** ❌
Outdated, unmaintained, and poorly suited for technical document extraction.

---

## Installation & Quick Start

### docTR
```bash
# Install
pip install python-doctr

# Quick test
python -c "
from doctr.io import DocumentFile
from doctr.models import ocr_predictor

model = ocr_predictor(pretrained=True)
doc = DocumentFile.from_pdf('test.pdf')
result = model(doc)
print(result.render())
"
```

### TrOCR
```bash
pip install transformers torch PIL

# Requires additional text detection setup
```

### keras-ocr
```bash
pip install keras-ocr tensorflow
# Be prepared for OpenCV dependency issues
```

---

## Conclusion

For your **SDS extraction pipeline**, **docTR is the clear winner**. It provides:
- ✅ **Optimal speed** for batch processing (2-3 sec/page)
- ✅ **Strong accuracy** on structured/technical text
- ✅ **Production-grade stability** and active maintenance
- ✅ **Seamless integration** with PDF input and geometric output
- ✅ **Cost-effective** compared to cloud APIs

Invest in docTR as your primary OCR engine, with optional fine-tuning on SDS samples to further improve chemical formula recognition.
