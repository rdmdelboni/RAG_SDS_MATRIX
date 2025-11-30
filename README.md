# RAG SDS Matrix

A RAG-enhanced Safety Data Sheet (SDS) processor that extracts chemical safety information and generates compatibility matrices using a hybrid approach combining heuristic extraction, LLM refinement, and RAG-augmented generation.

## Features

- **Hybrid Extraction Pipeline**: Combines regex heuristics, LLM refinement, PubChem enrichment, and RAG augmentation
- **PubChem Integration**: Automatic validation and enrichment using PubChem's chemical database
  - Validates CAS numbers, product names, and molecular formulas
  - Fills missing fields (molecular weight, IUPAC names, structure identifiers)
  - Enriches GHS hazard statements (H/P codes) with complete classifications
  - Detects inconsistencies and data quality issues
- **Multi-format Support**: Process PDF, TXT, MD, and DOCX SDS documents
- **Chemical Compatibility Matrix**: Automatic generation of incompatibility matrices
- **Structured Data Integration**: JSONL-based incompatibility rules and hazard records
- **Knowledge Base Management**: Build and query a vector database of chemical safety documentation
- **Decision Auditing**: Full traceability of compatibility decisions with justifications
- **Multi-format Export**: CSV, Excel, and JSON export with separate dangerous chemicals reports

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         UI Layer                             │
│         (PySide6 / Qt - Desktop GUI, follows OS theme)       │
└─────────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────────┐
│                    Processing Pipeline                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │  Heuristics  │→ │  LLM Refine  │→ │  PubChem     │     │
│  │  (Regex)     │  │  (Ollama)    │  │  Enrichment  │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
│                                              ↓               │
│                         ┌──────────────────────────────┐    │
│                         │   RAG Completion (Optional)  │    │
│                         │      (ChromaDB)              │    │
│                         └──────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────────┐
│                    Data Layer                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │   DuckDB     │  │   ChromaDB   │  │  PubChem API │     │
│  │ (Structured) │  │  (Vectors)   │  │  (External)  │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────┘
```

## Requirements

- **Python**: 3.11+
- **Ollama**: Running locally with models installed
- **System**: Linux, macOS, or Windows with WSL

## Installation

### 1. Clone the Repository

```bash
git clone <repository-url>
cd RAG_SDS_MATRIX
```

### 2. Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Install Ollama Models

```bash
ollama pull qwen2.5:7b-instruct-q4_K_M
ollama pull llama3.1:8b
ollama pull qwen3-embedding:4b
ollama pull deepseek-ocr:latest  # Optional, for OCR
```

### 5. Configure Environment

```bash
# Copy example configuration
cp .env.example .env

# Create local config for API keys (not tracked by git)
cp .env.example .env.local

# Edit .env.local and add your API keys if using external services
nano .env.local
```

### 6. Initialize Data Directories

The application will automatically create required directories on first run:
- `data/chroma_db/` - Vector database
- `data/duckdb/` - Structured database
- `data/logs/` - Application logs
- `data/input/` - Input documents
- `data/output/` - Export results

## Usage

### Start the Application

```bash
python main.py
```

### Basic Workflow

1. **Build Knowledge Base** (RAG Tab):
   - Click "Add Documents" to load PDF/TXT files
   - Or "Add URL" to fetch web content
   - Documents are chunked and indexed for semantic search

2. **Process SDS Documents** (SDS Tab):
   - Click "Select Folder" to choose directory with SDS files
   - Toggle "Use RAG" for dangerous chemical enrichment
   - Click "Process" to extract chemical data

3. **Generate Matrix**:
   - Click "Build Matrix" to create compatibility matrix
   - View results in tabbed interface:
     - Statistics
     - Incompatibility Matrix
     - Hazard Classes
     - Dangerous Chemicals

4. **Export Results**:
   - Click "Export" to save matrices
   - Supports CSV, Excel, JSON formats
   - Includes separate dangerous chemicals report

### RAG Search

Use the RAG Search feature to query the knowledge base:

```
Query: "What are the incompatibilities of sodium hydroxide?"
```

The system retrieves relevant documents and generates contextual answers using LLM.

## Advanced Features

### Structured Data Ingestion

Ingest JSONL files with incompatibility rules and hazard data:

```bash
python scripts/ingest_mrlp.py \
  --incompatibilities data/datasets/mrlp/incompatibilities.jsonl \
  --hazards data/datasets/mrlp/hazards.jsonl
```

**Incompatibilities Format:**
```json
{"cas_a": "1310-73-2", "cas_b": "7664-93-9", "rule": "I", "source": "NFPA"}
```

**Hazards Format:**
```json
{"cas": "1310-73-2", "hazard_flags": {"dangerous": true}, "idlh": 10, "env_risk": true}
```

### Check System Status

```bash
python scripts/status.py
```

Shows:
- Documents processed
- RAG documents indexed
- Incompatibility rules
- Hazard records
- Matrix decisions logged

## MRLP Sources & Whitelist

- The ingestion pipeline uses a high-trust whitelist of domains (UNIFAL, CAMEO/NOAA, CETESB, NIOSH/CDC, OSHA, CAS, ABNT, gov.br, NFPA, UNECE/GHS). This is configured via the `ALLOWED_SOURCE_DOMAINS` environment variable.
- Override or extend the whitelist in `.env` (comma-separated):  
   `ALLOWED_SOURCE_DOMAINS=unifal-mg.edu.br,cameochemicals.noaa.gov,cdc.gov,osha.gov,cetesb.sp.gov.br`
- Ingestion methods (`ingest_url`, `ingest_simple_urls`, Google CSE results, Bright Data snapshots, Craw4AI seeds) skip any URL whose domain is not whitelisted (flagged as `domain_not_allowed` / `not_whitelisted`).
- The `MatrixBuilder` prioritizes structured incompatibility rules (UNIFAL/CAMEO/NFPA) before SDS free-text matches and hazard-based elevation.

### Configuration Options

Edit `.env` or `.env.local`:

```bash
# LLM Settings
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_EXTRACTION_MODEL=qwen2.5:7b-instruct-q4_K_M
LLM_TEMPERATURE=0.1
LLM_MAX_TOKENS=2000

# Processing
MAX_WORKERS=8
CHUNK_SIZE=1000
CHUNK_OVERLAP=200

# Hazard Threshold (IDLH in ppm)
HAZARD_IDLH_THRESHOLD=50

# UI
UI_LANGUAGE=pt  # or 'en'
UI_THEME=dark   # or 'light'
```

## Testing

Run the test suite:

```bash
# All tests
pytest

# With coverage
pytest --cov=src --cov-report=html

# Specific test file
pytest tests/test_matrix_builder.py -v
```

## Project Structure

```
RAG_SDS_MATRIX/
├── main.py                 # Application entry point
├── requirements.txt        # Python dependencies
├── .env.example           # Configuration template
├── .gitignore             # Git exclusions
│
├── src/                   # Source code
│   ├── config/           # Settings, constants, i18n
│   ├── database/         # DuckDB persistence
│   ├── matrix/           # Compatibility matrix building
│   ├── models/           # Ollama LLM client
│   ├── rag/              # Vector store, chunking, retrieval
│   ├── sds/              # SDS extraction pipeline
│   ├── ui/               # PySide6/Qt interface
│   └── utils/            # Logging utilities
│
├── tests/                # Test suite
│   ├── test_heuristics.py
│   ├── test_matrix_builder.py
│   ├── test_sds_processor.py
│   └── ...
│
├── scripts/              # Utility scripts
│   ├── ingest_mrlp.py   # Structured data ingestion
│   └── status.py        # System status check
│
└── data/                 # Data directories (auto-created)
    ├── chroma_db/       # Vector database
    ├── duckdb/          # Structured database
    ├── logs/            # Application logs
    ├── input/           # Input documents
    └── output/          # Export results
```

## How It Works

### Extraction Pipeline

1. **Heuristic Extraction** (Fast, ~1s):
   - Regex patterns for CAS numbers, UN numbers, hazard classes
   - Section-based extraction (ABNT NBR 14725 sections)
   - Confidence scoring based on pattern matches

2. **LLM Refinement** (If needed, ~5-10s):
   - Triggered when heuristic confidence < 82%
   - Uses Ollama with task-specific prompts
   - Validates and improves extraction quality

3. **RAG Enrichment** (For dangerous chemicals):
   - Searches vector database for relevant context
   - Augments incompatibility data with external knowledge
   - Provides justifications for safety decisions

### Matrix Building

1. **Data Collection**: Fetch processed SDS extractions from database
2. **Rule Matching**: Apply structured incompatibility rules (JSONL)
3. **Hazard Elevation**: Upgrade compatibility based on IDLH/environmental risk
4. **Decision Logging**: Record all decisions with source attribution
5. **Export**: Generate CSV/Excel/JSON with full audit trail

## Troubleshooting

### Ollama Connection Issues

```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Start Ollama
ollama serve
```

### Missing Dependencies

```bash
# Reinstall all dependencies
pip install -r requirements.txt --force-reinstall
```

### Database Issues

```bash
# Remove and reinitialize databases
rm -rf data/chroma_db data/duckdb
python main.py  # Will recreate databases
```

### Test Discovery Issues

Create `pytest.ini`:
```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
```

## Performance Tips

1. **Adjust Workers**: Increase `MAX_WORKERS` for faster batch processing
2. **Confidence Threshold**: Raise to 0.9 to skip more LLM calls
3. **Chunk Size**: Reduce for faster vector search, increase for better context
4. **Model Selection**: Use smaller Ollama models for faster processing

## Security

- API keys stored in `.env.local` (not tracked by git)
- Local LLM processing (no data sent to external APIs)
- File permissions restricted on sensitive files (600)
- Content hashing prevents duplicate processing

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- **LangChain**: RAG orchestration
- **ChromaDB**: Vector database
- **DuckDB**: Analytical database
- **Ollama**: Local LLM inference
- **PySide6 (Qt)**: Desktop UI framework

## Support

For issues, questions, or contributions, please open an issue on GitHub.

---

**Version**: 1.0.0  
**Last Updated**: November 22, 2025  
**Status**: Production Ready ✅
