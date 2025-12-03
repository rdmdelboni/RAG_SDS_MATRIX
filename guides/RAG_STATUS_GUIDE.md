# RAG Status Viewer - Quick Reference

## Overview

The `rag_status.py` script lets you see what has been ingested into your RAG knowledge base.

## Usage Examples

### Show Overall Status
```bash
python scripts/rag_status.py
```
Shows:
- Total documents ingested
- Total chunks in vector store
- Breakdown by source type (PDFs, CAMEO chemicals, web pages, etc.)
- Recent ingestions
- Structured data (incompatibilities, hazards)

### View Grouped by Source Type
```bash
python scripts/rag_status.py --grouped
```
Shows all documents organized by source type with document counts.

### List Documents from Specific Source
```bash
# All PDFs
python scripts/rag_status.py --source file --list

# All CAMEO chemicals
python scripts/rag_status.py --source cameo_chemical --list

# All web pages
python scripts/rag_status.py --source simple_http --list
```

### View Details of Specific Document
```bash
python scripts/rag_status.py --detail 1
```
Shows:
- Document title
- Source type and URL
- Number of chunks
- When it was indexed
- Full metadata

### Show Structured Data Only
```bash
python scripts/rag_status.py --structured
```
Shows:
- Chemical incompatibilities (count + samples)
- Chemical hazards (count + samples)

## Current RAG Status

### Summary
- **Total Documents**: 5,232
- **Total Chunks**: 34,630
- **Source Types**: 3

### Breakdown by Source

| Source Type | Count | Details |
|------------|-------|---------|
| CAMEO Chemicals | 5,203 | From cameochemicals.noaa.gov |
| Files (PDFs/Excel) | 24 | From data/input folder |
| Web Pages | 5 | From various URLs |

### Sample CAMEO Chemicals (Latest)
- Chemical ID: 21243
- Chemical ID: 19048
- Chemical ID: 19064
- Chemical ID: 4838
- Chemical ID: 1732

### Structured Data
- **Chemical Incompatibilities**: 12 rules
  - H₂O₂ (7722-84-1) + Ethanol (64-17-5) → Restricted (NFPA)
  - Nitric Acid (7697-37-2) + Water (7732-18-5) → Incompatible (UNIFAL)
  - Sodium (7440-23-5) + Water (7732-18-5) → Incompatible (CAMEO)

- **Chemical Hazards**: 6 chemicals
  - Formaldehyde (50-00-0) - NIOSH
  - Benzene (71-43-2) - CETESB
  - Ethanol (64-17-5) - NIOSH

### Sample File Ingestions
- `svhc_identification_full-2025-11-21.xlsx` (502 chunks)
- `substance_evaluation_full-2025-11-21.xlsx` (829 chunks)
- `restriction_process_full-2025-11-21.xlsx` (937 chunks)

## What Each Source Type Means

### cameo_chemical
- From NOAA CAMEO Chemicals database
- Each document = 1 chemical with hazard info
- Typically 1 chunk per chemical
- Format: Chemical name, CAS number, NFPA rating, hazards

### file
- Local files (PDFs, Excel, Word, Markdown, etc.)
- From `data/input` folder
- Typically 10-1000+ chunks depending on file size
- Format: Structured document with text extraction

### simple_http
- Web pages fetched from URLs
- From various sources (CDC, CETESB, CAS, etc.)
- Typically 1-26 chunks depending on page size
- Format: HTML converted to text

## Next Steps

### To View More Details
```bash
# See all CAMEO chemicals (up to 100)
python scripts/rag_status.py --source cameo_chemical --list

# See all PDF/Excel files
python scripts/rag_status.py --source file --list

# Get details on document ID 10
python scripts/rag_status.py --detail 10
```

### To Continue Ingestion
```bash
# Continue CAMEO ingestion from letter B onwards
python scripts/ingest_cameo_chemicals.py --start B

# Ingest more PDFs from data/input
python scripts/ingest_documents.py --folder data/input

# Monitor ingestion progress
python scripts/monitor_cameo_ingestion.py
```

### To Build Matrix
Once you have enough ingested data:
```bash
python src/matrix/builder.py  # (check actual entry point)
```

---

**Last Updated**: November 22, 2025
**RAG Documents**: 5,232
**Total Chunks**: 34,630
