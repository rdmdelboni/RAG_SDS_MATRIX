# CAMEO Chemical Database Ingestion Guide

## Overview

This guide explains how to ingest all chemical data sheets from the **CAMEO Chemicals database** (https://cameochemicals.noaa.gov) into your RAG knowledge base.

**What this script does:**
- ✅ Automatically fetches all chemical IDs from browse pages (A-Z)
- ✅ Extracts chemical details (name, CAS, hazards, NFPA ratings, etc.)
- ✅ Chunks and ingests data into ChromaDB vector store
- ✅ Deduplicates content automatically
- ✅ Provides detailed progress tracking and error reporting
- ✅ Rate-limits requests to be respectful to CAMEO servers

**Technology stack:**
- BeautifulSoup4 (HTML parsing) - Free & lightweight
- requests (HTTP) - Already in dependencies
- LangChain + ChromaDB (vector storage)

---

## Quick Start

### Basic Usage - Ingest All Chemicals (A-Z)

```bash
# Activate virtual environment
source venv/bin/activate

# Run ingestion
python scripts/ingest_cameo_chemicals.py
```

This will:
1. Process letters A through Z sequentially
2. Fetch ~3,000+ chemicals (estimated)
3. Take approximately 1-2 hours (default timing)
4. Provide real-time progress updates

### Expected Output

```
======================================================================
  🧪 CAMEO Chemical Database Ingestion
======================================================================
Letters to process: ABCDEFGHIJKLMNOPQRSTUVWXYZ
Request timeout: 30s
Delay between requests: 1.0s
Estimated time: ~1.4 hours (rough estimate)
======================================================================

### Processing letter 'A' ###
Fetching chemical IDs for letter 'A' from https://cameochemicals.noaa.gov/browse/A
Found 123 unique chemicals for letter 'A'
[1/123] Processing chemical 18052...
✓ Ingested: Acetone (ID: 18052, 3 chunks)
...

======================================================================
📊 INGESTION STATISTICS
======================================================================
Total Chemicals Found:      3247
Successfully Scraped:       3198
Successfully Ingested:      3156
Failed to Scrape:           49
Skipped (no chunks):        0

Success Rate:               97.2%
======================================================================
```

---

## Advanced Usage

### 1. Ingest Only Specific Letters

```bash
# Ingest only A, B, C
python scripts/ingest_cameo_chemicals.py --letters ABC

# Ingest consonants only (faster testing)
python scripts/ingest_cameo_chemicals.py --letters BCDFGHJKLMNPRSTVWXYZ
```

### 2. Resume from Specific Letter

If the script gets interrupted, resume from where it left off:

```bash
# Resume from M onwards (M-Z)
python scripts/ingest_cameo_chemicals.py --start M
```

This is useful if you were interrupted and want to avoid re-processing A-L.

### 3. Adjust Timing Parameters

```bash
# Faster (less respectful):
python scripts/ingest_cameo_chemicals.py --timeout 15 --delay 0.5

# Slower (more respectful to CAMEO servers):
python scripts/ingest_cameo_chemicals.py --timeout 60 --delay 2.0
```

**Recommendations:**
- `--timeout`: Keep between 20-60 seconds
- `--delay`: Keep between 0.5-2.0 seconds (1.0s default is good)

### 4. Run in Background (Linux/macOS)

```bash
# Run with output to file
nohup python scripts/ingest_cameo_chemicals.py > cameo_ingestion.log 2>&1 &

# Monitor progress
tail -f cameo_ingestion.log

# Check how many chemicals were ingested
tail -20 cameo_ingestion.log
```

---

## What Data Gets Extracted

For each chemical, the script extracts:

```
Chemical: Acetone
ID: 18052
CAS Number: 67-64-1
Synonyms: Dimethyl ketone, 2-Propanone, Propanone

Hazard Summary:
[Flammability info, fire risk, etc.]

Health Hazard:
[Health effects, toxicity, etc.]

Fire Hazard:
[Flammability data, flash point, etc.]

Reactivity Hazard:
[Stability, incompatibilities, etc.]

Primary Hazards: Flammable, Eye Irritant, Carcinogenic

NFPA Rating: {"health": 2, "flammability": 3, "reactivity": 0}

Source: https://cameochemicals.noaa.gov/chemical/18052
```

This structured data is then:
- **Chunked** into semantic pieces (default 1000 chars with 200 overlap)
- **Embedded** using your configured embedding model
- **Stored** in ChromaDB for vector search
- **Deduplicated** by content hash

---

## Verify Ingestion Success

### Check Statistics

```bash
# Show ingestion summary
python scripts/status.py
```

Expected output:
```
Database: /home/user/RAG_SDS_MATRIX/data/duckdb/extractions.db
Documents: 3500
Processed: 2850
RAG Documents: 3200
```

### Query Ingested Data

```bash
# From UI: Use RAG Search tab
# Query: "What is the incompatibility of acetone?"

# From command line:
python -c "
from src.rag.vector_store import get_vector_store
vs = get_vector_store()
results = vs.similarity_search('acetone hazards', k=3)
for r in results:
    print(f\"Match: {r.metadata['title']}\")
    print(f\"Score: {r.metadata.get('distance', 'N/A')}\n\")
"
```

---

## Troubleshooting

### Issue: "Failed to fetch browse page"

**Cause:** Network error or CAMEO server unreachable

**Solutions:**
```bash
# Check internet connection
ping cameochemicals.noaa.gov

# Try with longer timeout
python scripts/ingest_cameo_chemicals.py --timeout 60

# Try specific letter again
python scripts/ingest_cameo_chemicals.py --letters A
```

### Issue: "Could not extract name for chemical"

**Cause:** CAMEO page structure changed or chemical page is malformed

**Impact:** That chemical is skipped, but ingestion continues

**Solution:** Usually temporary, can be resolved by:
1. Running again later
2. Reporting to CAMEO if persistent

### Issue: Database lock error

**Cause:** Another process is using the database

**Solution:**
```bash
# Close any other Python processes
ps aux | grep python

# Kill process if needed
kill -9 <PID>

# Then try ingestion again
python scripts/ingest_cameo_chemicals.py --letters A
```

### Issue: Out of memory

**Cause:** Too many chemicals loaded at once (if chunks are large)

**Solution:** Reduce chunk size in `.env`:
```bash
CHUNK_SIZE=500  # Default is 1000
CHUNK_OVERLAP=100
```

---

## Performance Optimization

### Speed Up (with trade-offs)

```bash
# Parallel processing would be faster, but requires more refactoring
# For now, use lower delay:
python scripts/ingest_cameo_chemicals.py --delay 0.5

# Ingest only certain letters
python scripts/ingest_cameo_chemicals.py --letters ABCDEFGHIJ
```

### Check Progress During Ingestion

```bash
# In another terminal, monitor the log
tail -f data/logs/ingest_cameo_chemicals.log

# Or check database size
du -sh data/chroma_db/
```

---

## Cost Analysis

**Resources used:**
- **Network:** ~50-100 MB (CAMEO pages are lightweight)
- **Storage:** ~500 MB - 2 GB (depends on chunk size and overlap)
- **Time:** ~1.5 hours at default speed
- **Cost:** $0 (no external APIs, just CAMEO servers)

**Bandwidth:**
- Average page size: ~50 KB
- ~3200 chemicals × 50 KB ≈ 160 MB total

---

## Integration with Your Workflow

### After Ingestion

1. **Use in RAG Search:**
   ```
   Query: "What are the incompatibilities of sodium hydroxide?"
   System will retrieve CAMEO data + other documents
   ```

2. **Use in Matrix Building:**
   - CAMEO data enriches your chemical compatibility matrix
   - Hazard data influences incompatibility rules

3. **Export Enriched Data:**
   ```bash
   python scripts/status.py
   # See: "RAG Documents: 3156"
   ```

### Scheduling Regular Updates

To keep CAMEO data fresh, run periodically:

```bash
# Weekly update (cron job - add to crontab)
0 0 * * 0 cd /path/to/RAG_SDS_MATRIX && source venv/bin/activate && python scripts/ingest_cameo_chemicals.py >> data/logs/cameo_weekly.log 2>&1

# Or use a shell script
#!/bin/bash
cd /path/to/RAG_SDS_MATRIX
source venv/bin/activate
python scripts/ingest_cameo_chemicals.py --delay 2.0  # Be respectful during scheduled runs
```

---

## FAQs

**Q: Will this harm CAMEO servers?**
A: No. We use respectful rate limiting (1 second between requests). This is well within acceptable limits.

**Q: Can I ingest just my chemical of interest?**
A: Currently the script processes all chemicals in a letter. You could modify it to fetch a specific chemical ID directly. Let me know if you need this!

**Q: What if a chemical has no data?**
A: It's skipped automatically. The script is resilient to incomplete data.

**Q: Can I run multiple ingestion scripts simultaneously?**
A: Not recommended - they'll compete for database locks. Run sequentially.

**Q: How do I know if ingestion worked?**
A: Check the final statistics. Success rate should be > 90%. Then verify with:
```bash
python scripts/status.py  # Check RAG Documents count
```

---

## Example Use Cases

### Case 1: Initial Setup (Recommended)

```bash
# Day 1: Build comprehensive knowledge base
python scripts/ingest_cameo_chemicals.py --delay 1.0
# Takes ~1.5 hours, gets ~3000+ chemicals

# Day 2: Verify and start using
python scripts/status.py
# Check: "RAG Documents: 3156"

# Use in your workflow immediately
```

### Case 2: Partial Ingestion (Testing)

```bash
# Test with just A-E first
python scripts/ingest_cameo_chemicals.py --letters ABCDE
# Takes ~15 minutes, gets ~500 chemicals

# Verify quality
# Then do the rest
python scripts/ingest_cameo_chemicals.py --start F
```

### Case 3: Interrupted Run (Recovery)

```bash
# If interrupted at letter P:
python scripts/ingest_cameo_chemicals.py --start P

# Picks up from P-Z, no re-processing of A-O
```

---

## Next Steps

1. **Run the ingestion:**
   ```bash
   source venv/bin/activate
   python scripts/ingest_cameo_chemicals.py
   ```

2. **Monitor progress:**
   - Watch console output
   - Check `data/logs/ingest_cameo_chemicals.log`

3. **Verify success:**
   ```bash
   python scripts/status.py
   ```

4. **Start using:**
   - Open UI: `python main.py`
   - Try RAG Search with chemical queries
   - Use in matrix building

---

## Support

If you encounter issues:

1. Check the log file: `data/logs/ingest_cameo_chemicals.log`
2. Verify CAMEO is accessible: `curl https://cameochemicals.noaa.gov`
3. Check available disk space: `df -h`
4. Review this guide's troubleshooting section

For CAMEO-specific questions, visit: https://cameochemicals.noaa.gov

---

**Last Updated:** November 2025
**Compatible with:** RAG SDS Matrix v1.0+
**Status:** Production Ready ✅
