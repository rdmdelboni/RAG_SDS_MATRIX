# RAG_SDS_MATRIX - Quick Start Usage Guide

## Overview

This guide shows you how to use the RAG_SDS_MATRIX system for processing Safety Data Sheets with LLM-powered extraction and RAG capabilities.

## Prerequisites

✅ **Ollama installed and running**
```bash
ollama serve
```

✅ **Required models pulled**
```bash
ollama pull qwen2.5:7b-instruct-q4_K_M
ollama pull llama3.1:8b
ollama pull qwen3-embedding:4b
```

✅ **Virtual environment activated**
```bash
source .venv/bin/activate
```

## Basic Usage

### 1. GUI Application

**Start the UI:**
```bash
python main.py
```

The application provides:
- 📄 Document upload and processing
- 🔍 RAG-powered search interface
- 📊 Chemical compatibility matrix
- ✏️ Editable data tables
- 🔄 Batch validation

### 2. Python API

#### Initialize Components

```python
from src.config import get_settings
from src.models import get_ollama_client
from src.rag import get_vector_store
from src.database import get_db_manager

# Load settings
settings = get_settings()

# Get LLM client
llm = get_ollama_client()

# Get vector store
vector_store = get_vector_store()

# Get database
db = get_db_manager()
```

#### Extract Fields from SDS

```python
# Load SDS text
with open("sds_document.txt", "r") as f:
    sds_text = f.read()

# Extract specific field
result = llm.extract_field(
    text=sds_text,
    field_name="product_name",
    prompt_template="""
    Extract the product name from this Safety Data Sheet.
    
    Text: {text}
    
    Return JSON with: {{"value": "...", "confidence": 0.0-1.0}}
    """
)

print(f"Product Name: {result.value}")
print(f"Confidence: {result.confidence}")
```

#### Extract Multiple Fields

```python
# Define fields to extract
fields = [
    "product_name",
    "manufacturer",
    "cas_number",
    "hazard_statements",
]

# Extract all at once
results = llm.extract_multiple_fields(
    text=sds_text,
    fields=fields
)

for field, result in results.items():
    print(f"{field}: {result.value} (confidence: {result.confidence:.2f})")
```

#### Process Documents for RAG

```python
from src.rag.document_loader import DocumentLoader
from src.rag.chunker import Chunker

# Load document
loader = DocumentLoader()
documents = loader.load_file("sds_document.pdf")

# Chunk documents
chunker = Chunker(
    chunk_size=1000,
    chunk_overlap=200
)
chunks = chunker.chunk_documents(documents)

# Add to vector store
vector_store.add_documents(chunks)

print(f"Added {len(chunks)} chunks to vector store")
```

#### Query RAG System

```python
# Search for relevant information
results = vector_store.search(
    query="What are the flammability hazards?",
    k=5
)

# Format results
for i, result in enumerate(results, 1):
    print(f"\n--- Result {i} (score: {result.score:.3f}) ---")
    print(f"Source: {result.source}")
    print(f"Content: {result.content[:200]}...")

# Get formatted context for LLM
context = vector_store.search_with_context(
    query="What are the flammability hazards?",
    k=5
)

# Ask LLM with context
response = llm.chat(
    message="What are the flammability hazards of this chemical?",
    context=context,
    system_prompt="You are a chemical safety expert. Answer based on the provided context."
)

print(f"\nAnswer: {response}")
```

#### Database Operations

```python
# Get statistics
stats = db.get_statistics()
print(f"Total documents: {stats['total_documents']}")
print(f"Processed: {stats['processed']}")

# Store extraction results
db.store_extraction({
    "file_hash": "abc123",
    "file_name": "acetone_sds.pdf",
    "product_name": "Acetone",
    "manufacturer": "Chemical Corp",
    "cas_number": "67-64-1",
    # ... more fields
})

# Query extractions
extractions = db.get_all_extractions()
for ext in extractions:
    print(f"{ext['product_name']} - {ext['manufacturer']}")
```

## Advanced Usage

### Custom Prompts

```python
# Define custom extraction prompt
CUSTOM_PROMPT = """
You are analyzing a Safety Data Sheet. Extract the {field_name}.

Rules:
- Be precise and concise
- Include only verified information
- Return "NOT_FOUND" if information is missing

Document text:
{text}

Return JSON: {{"value": "...", "confidence": 0.0-1.0, "context": "..."}}
"""

result = llm.extract_field(
    text=sds_text,
    field_name="emergency_phone",
    prompt_template=CUSTOM_PROMPT,
    system_prompt="You are an expert SDS analyzer."
)
```

### Batch Processing

```python
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

def process_sds(file_path: Path):
    """Process a single SDS file."""
    try:
        # Load and process
        loader = DocumentLoader()
        docs = loader.load_file(str(file_path))
        
        # Extract key fields
        text = " ".join([doc.page_content for doc in docs])
        results = llm.extract_multiple_fields(
            text=text,
            fields=["product_name", "manufacturer", "cas_number"]
        )
        
        # Store in database
        db.store_extraction({
            "file_name": file_path.name,
            **{k: v.value for k, v in results.items()}
        })
        
        # Add to vector store
        chunker = Chunker()
        chunks = chunker.chunk_documents(docs)
        vector_store.add_documents(chunks)
        
        return {"success": True, "file": file_path.name}
    
    except Exception as e:
        return {"success": False, "file": file_path.name, "error": str(e)}

# Process multiple files
sds_dir = Path("data/input")
sds_files = list(sds_dir.glob("*.pdf"))

with ThreadPoolExecutor(max_workers=4) as executor:
    results = list(executor.map(process_sds, sds_files))

# Summary
successful = sum(1 for r in results if r["success"])
print(f"Processed {successful}/{len(results)} files successfully")
```

### OCR for Scanned PDFs

```python
from pdf2image import convert_from_path

# Convert PDF to images
images = convert_from_path("scanned_sds.pdf")

# OCR each page
extracted_text = []
for i, image in enumerate(images, 1):
    # Save temporarily
    image.save(f"/tmp/page_{i}.png")
    
    # OCR
    text = llm.ocr_image(f"/tmp/page_{i}.png")
    extracted_text.append(text)
    
    print(f"Page {i}: {len(text)} characters extracted")

# Combine all pages
full_text = "\n\n".join(extracted_text)

# Extract fields from OCR'd text
results = llm.extract_multiple_fields(
    text=full_text,
    fields=["product_name", "manufacturer", "hazard_statements"]
)
```

### Incremental Retraining

```python
from src.rag.incremental_retrainer import IncrementalRetrainer

# Initialize retrainer
retrainer = IncrementalRetrainer(
    vector_store=vector_store,
    db_manager=db
)

# Check if retraining needed
if retrainer.needs_retraining():
    print("Retraining vector store...")
    retrainer.retrain()
    print("Retraining complete")
else:
    print("Vector store up to date")
```

### Custom LLM Provider

```python
from src.models import get_llm, LLMProvider

# Use Ollama (default)
llm_ollama = get_llm("ollama")

# Use OpenAI (optional)
llm_openai = get_llm(
    "openai",
    api_key="sk-...",
    model="gpt-4-turbo-preview"
)

# Use Azure OpenAI (optional)
llm_azure = get_llm(
    "azure_openai",
    api_key="...",
    endpoint="https://....openai.azure.com",
    deployment="gpt-4"
)

# Use custom endpoint (optional)
llm_custom = get_llm(
    "custom",
    endpoint="https://your-llm.com/api/generate",
    api_key="..."
)

# All use same interface
response = llm_ollama.chat("What is acetone?")
```

## Scripts

### SDS Pipeline

```bash
# Process all SDS files in input directory
./run_sds_pipeline.sh

# Or use Python directly
python scripts/sds_pipeline.py
```

### Ingest Documents

```bash
# Ingest documents into vector store
python scripts/ingest_documents.py --input data/input --recursive

# With specific file types
python scripts/ingest_documents.py --input data/input --types pdf,docx
```

### RAG Status

```bash
# Check RAG system status
python scripts/rag_status.py

# Output:
# Vector Store: 1,234 documents
# Database: 567 extractions
# Last update: 2025-12-03 10:30:00
```

### Database Inspection

```bash
# Inspect DuckDB database
python scripts/inspect_duckdb.py

# Export to CSV
python scripts/inspect_duckdb.py --export extractions.csv
```

## Common Patterns

### Error Handling

```python
from src.utils.logger import get_logger

logger = get_logger(__name__)

try:
    result = llm.extract_field(
        text=sds_text,
        field_name="product_name",
        prompt_template="Extract product name: {text}"
    )
    
    if result.confidence < 0.5:
        logger.warning(
            "Low confidence extraction: %s (%.2f)",
            result.value,
            result.confidence
        )
except Exception as e:
    logger.error("Extraction failed: %s", e)
    # Fallback to heuristics or manual review
```

### Caching Results

```python
from functools import lru_cache

@lru_cache(maxsize=1000)
def extract_with_cache(text_hash: str, field: str) -> str:
    """Cache extraction results by text hash."""
    result = llm.extract_field(
        text=sds_text,
        field_name=field,
        prompt_template=f"Extract {field}: {{text}}"
    )
    return result.value

# Use hash of text for caching
import hashlib
text_hash = hashlib.md5(sds_text.encode()).hexdigest()
product_name = extract_with_cache(text_hash, "product_name")
```

### Confidence Thresholds

```python
MIN_CONFIDENCE = 0.7

result = llm.extract_field(
    text=sds_text,
    field_name="cas_number",
    prompt_template="Extract CAS number: {text}"
)

if result.confidence >= MIN_CONFIDENCE:
    # High confidence - use directly
    db.store_extraction({"cas_number": result.value})
else:
    # Low confidence - flag for review
    db.store_extraction({
        "cas_number": result.value,
        "requires_review": True,
        "confidence": result.confidence
    })
```

## Tips & Best Practices

### 1. **Start with Test Documents**
- Test with a few SDS documents first
- Validate extraction accuracy
- Adjust prompts as needed

### 2. **Monitor Confidence Scores**
- Track average confidence across fields
- Flag low-confidence extractions for review
- Refine prompts to improve confidence

### 3. **Use Chunking Wisely**
- Default: 1000 tokens with 200 overlap
- Increase for more context
- Decrease for faster search

### 4. **Optimize Vector Store**
- Clear old/irrelevant documents periodically
- Reindex after major updates
- Monitor search performance

### 5. **Leverage Batch Processing**
- Process multiple files in parallel
- Use appropriate worker count for your hardware
- Monitor resource usage

### 6. **Test Ollama Connection**
```python
if not llm.test_connection():
    print("❌ Ollama not running!")
    print("Start with: ollama serve")
else:
    print("✅ Ollama connected")
    models = llm.list_models()
    print(f"Available models: {models}")
```

## Troubleshooting

### "Vector store not ready"
```python
# Force reinitialization
vector_store._db = None
if vector_store.ensure_ready():
    print("✅ Vector store recovered")
```

### "Extraction timeout"
```bash
# Increase timeout
export LLM_TIMEOUT=300  # 5 minutes
```

### "Out of memory"
```bash
# Reduce workers and batch size
export MAX_WORKERS=2
# In code: batch_size=50 instead of 100
```

## Next Steps

1. **Read the full guides:**
   - [`LLM_CONFIGURATION_GUIDE.md`](LLM_CONFIGURATION_GUIDE.md)
   - [`QUICK_START_GUIDE.md`](../QUICK_START_GUIDE.md)
   - [`RAG_SDS_PROCESSING_GUIDE.md`](../RAG_SDS_PROCESSING_GUIDE.md)

2. **Explore examples:**
   - [`examples/rag_tracking_example.py`](../examples/rag_tracking_example.py)
   - [`test_ui_tabs.py`](../test_ui_tabs.py)

3. **Run tests:**
   ```bash
   pytest tests/ -v
   ```

4. **Join the community:**
   - Report issues on GitHub
   - Contribute improvements
   - Share your use cases

---

**Happy processing! 🚀**
