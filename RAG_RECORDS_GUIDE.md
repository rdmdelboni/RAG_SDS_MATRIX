# RAG Records Viewer Guide

View actual records and data from your RAG knowledge base using the `rag_records.py` tool.

## Quick Start

### View all incompatibilities
```bash
python scripts/rag_records.py --incompatibilities
```

Output shows:
- Chemical CAS pairs (A + B)
- Incompatibility rule (I/R/C)
- Source (NFPA, UNIFAL, CAMEO, etc.)
- Justification and metadata

### View all hazards
```bash
python scripts/rag_records.py --hazards
```

Output shows:
- Chemical CAS numbers
- Hazard flags (toxic, flammable, etc.)
- Exposure limits (IDLH, PEL, REL)
- Environmental risk assessment
- Source (NIOSH, CETESB, etc.)

### View CAMEO chemicals
```bash
python scripts/rag_records.py --cameo --limit 20
```

Shows ingested CAMEO chemicals with:
- Document ID and chunk count
- Chemical ID and CAS number
- Hazard categories
- Direct URL to CAMEO database

### View file documents
```bash
python scripts/rag_records.py --files --limit 20
```

Lists ingested PDFs, Excel files, etc. with:
- Document title
- Number of chunks
- File path and page/row counts
- Metadata

## Advanced Queries

### Find specific incompatibilities

**Incompatibilities involving water (CAS 7732-18-5):**
```bash
python scripts/rag_records.py --incompatibilities --cas-b 7732-18-5
```

**Incompatibilities involving ethanol (CAS 64-17-5):**
```bash
python scripts/rag_records.py --incompatibilities --cas-a 64-17-5
```

**Only dangerous incompatibilities (rule I = "Incompatible"):**
```bash
python scripts/rag_records.py --incompatibilities --rule I
```

Rules:
- `I` = Incompatible (dangerous reaction)
- `R` = Reactive (problematic reaction)
- `C` = Conditional (reaction under specific conditions)

### Find specific hazards

**Hazards for formaldehyde (CAS 50-00-0):**
```bash
python scripts/rag_records.py --hazards --cas 50-00-0
```

**Hazards from NIOSH source:**
```bash
python scripts/rag_records.py --hazards --source NIOSH
```

**Hazards from CETESB (Brazilian regulatory agency):**
```bash
python scripts/rag_records.py --hazards --source CETESB
```

## Options

### General flags
- `--db PATH` - Custom database path (default: `data/duckdb/extractions.db`)
- `--limit N` - Maximum records to show (default: 20)

### View modes
- `--incompatibilities` - Show chemical incompatibilities
- `--hazards` - Show chemical hazards
- `--cameo` - Show CAMEO chemicals
- `--files` - Show file documents

### Filters
- `--cas CAS_NUMBER` - Filter by CAS number (for hazards)
- `--cas-a CAS_NUMBER` - Filter incompatibilities by first chemical
- `--cas-b CAS_NUMBER` - Filter incompatibilities by second chemical
- `--rule I|R|C` - Filter by incompatibility rule
- `--source SOURCE` - Filter by data source

## Examples

### Chemical Safety Check

Find everything about formaldehyde:
```bash
python scripts/rag_records.py --incompatibilities --cas-a 50-00-0
python scripts/rag_records.py --incompatibilities --cas-b 50-00-0
python scripts/rag_records.py --hazards --cas 50-00-0
```

### Find dangerous combinations

Show only "incompatible" (rule I) combinations:
```bash
python scripts/rag_records.py --incompatibilities --rule I
```

### Data source audit

See what came from CAMEO:
```bash
python scripts/rag_records.py --cameo --limit 100
```

See what came from uploaded files:
```bash
python scripts/rag_records.py --files --limit 100
```

See all regulatory data from CETESB:
```bash
python scripts/rag_records.py --hazards --source CETESB
```

## Data Schema

### Incompatibilities Table
| Field | Type | Description |
|-------|------|-------------|
| `cas_a` | string | First chemical CAS number |
| `cas_b` | string | Second chemical CAS number |
| `rule` | string | I (incompatible), R (reactive), C (conditional) |
| `source` | string | Data origin (NFPA, UNIFAL, CAMEO, etc.) |
| `justification` | text | Explanation of incompatibility |
| `metadata` | JSON | Additional structured data (risk, control measures, gases produced, etc.) |

### Hazards Table
| Field | Type | Description |
|-------|------|-------------|
| `cas` | string | Chemical CAS number |
| `hazard_flags` | JSON | Boolean flags for hazard types |
| `idlh` | float | Immediately Dangerous to Life/Health (ppm) |
| `pel` | float | OSHA Permissible Exposure Limit (ppm) |
| `rel` | float | NIOSH Recommended Exposure Limit (ppm) |
| `env_risk` | boolean | Environmental risk assessment |
| `source` | string | Data origin (NIOSH, CETESB, etc.) |
| `metadata` | JSON | Chemical name, notes, hazard categories, etc. |

### Documents Table
| Field | Type | Description |
|-------|------|-------------|
| `id` | integer | Unique document ID |
| `title` | string | Document title |
| `source_type` | string | `cameo_chemical`, `file`, `simple_http` |
| `chunk_count` | integer | Number of text chunks extracted |
| `source_url` | string | URL (for CAMEO and web sources) |
| `source_path` | string | File path (for uploaded files) |
| `metadata` | JSON | Format-specific metadata |

## Common Tasks

### Export incompatibilities for spreadsheet
```bash
python scripts/rag_records.py --incompatibilities --limit 1000 > incompatibilities.txt
```

### Check all hazards from uploaded PDFs
First see what files are loaded:
```bash
python scripts/rag_records.py --files --limit 50
```

Then cross-reference with hazard data:
```bash
python scripts/rag_records.py --hazards --limit 100
```

### Audit data sources
```bash
# CAMEO entries
python scripts/rag_records.py --cameo --limit 5000

# Uploaded files
python scripts/rag_records.py --files --limit 5000

# All hazards from each source
python scripts/rag_records.py --hazards --source NIOSH --limit 100
python scripts/rag_records.py --hazards --source CETESB --limit 100
```

## Tips

1. **Default behavior**: If you run `python scripts/rag_records.py` with no flags, it shows both incompatibilities and hazards.

2. **Limit results**: Use `--limit` to control output size. Large datasets default to showing 20 items.

3. **Combine filters**: You can use multiple filters together:
   ```bash
   python scripts/rag_records.py --incompatibilities --rule I --limit 50
   ```

4. **Source debugging**: Check `--source` values in metadata to verify data provenance.

5. **JSON metadata**: The `--metadata` field often contains structured data like hazard categories, control measures, or chemical properties. This is parsed and displayed in the output.
