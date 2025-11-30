# Quick Start Guide - Column Resizing Complete

## Running the App

```bash
cd /home/rdmdelboni/Work/Gits/RAG_SDS_MATRIX
source .venv/bin/activate
python main.py
```
 
### Throttling External Calls

To avoid overloading external services while keeping throughput stable, configure these environment variables before running:

```zsh
export INGESTION_RPS=0.5        # general ingestion HTTP requests/sec
export CAMEO_RPS=0.5            # CAMEO scraper requests/sec
export PUBCHEM_RPS=20           # PubChem requests/min
export PUBCHEM_SKIP_CONFIDENCE_GE=0.85  # skip enrichment on high-confidence docs
export PUBCHEM_CACHE_ENABLED=true       # enable persistent PubChem cache
```

You can place these in `.env.local` or export them in your shell session.

## Using Table Column Resizing

### How to Resize Columns

1. **Locate the resize handle**: Look for a **cyan-colored vertical line** between column headers
2. **Position your cursor**: Hover over the cyan line between two columns
3. **Cursor will change**: The cursor will change to a double-headed arrow (↔)
4. **Drag to resize**: Click and drag left or right to adjust the column width
5. **Release to finish**: Release the mouse button when satisfied with the width

### Visual Guide

```
┌─────────────────┬─────────────────┬──────────────┐
│   Filename      │  Quality Tier   │ Confidence   │  ← Column headers
├─────────────────┼─────────────────┼──────────────┤
│ document1.pdf   │ excellent       │ 95.2%        │
│ document2.pdf   │ good            │ 87.3%        │
│ document3.pdf   │ acceptable      │ 72.1%        │
└─────────────────┴─────────────────┴──────────────┘
                  ↑
         Cyan resize handle
         (drag here to resize)
```

## Key Features

### Large, Readable Fonts
- **Font Size**: 14pt (JetBrains Mono)
- **Row Height**: 40px
- **Padding**: Comfortable spacing around text

### Smart Scrollbars
- Vertical scrollbar appears automatically when needed
- Auto-hides when all content fits on screen
- Mouse wheel scrolling supported

### Professional Dark Theme
- Background: Dark navy (#0f172a)
- Text: Light gray (#e2e8f0)
- Headers: Darker navy (#1e293b)
- Accents: Cyan (#4fd1c5)

## Available Tabs

All tabs now have the improved SimpleTable with column resizing:

1. **Quality Dashboard** - Monitor data quality metrics
2. **RAG Search** - Search and retrieve from knowledge base
3. **Sources** - View document sources
4. **SDS Extraction** - Safety Data Sheet extraction results
5. **Status** - System status and statistics
6. **Records** - View all processed records
7. **Backup** - Manage database backups

## Testing Column Resizing

A test script is available to try column resizing in isolation:

```bash
source .venv/bin/activate
python test_simple_table.py
```

This will open a test window with sample data where you can practice resizing columns.

## Troubleshooting

### Columns won't resize
- Ensure you're clicking on the cyan separator between columns
- The cursor should change to ↔ when hovering over the resize handle
- Try dragging slowly at first

### Font looks small
- This should not happen - font is set to 14pt
- If it appears small, you may need to adjust system display scaling
- Check `src/config/settings.py` if needed

### Window flickers during resize
- This should NOT happen with the new implementation
- If it does, please report the issue

## Database

Data is automatically saved to:
- **Extractions**: `/data/duckdb/extractions.db`
- **Knowledge Base (RAG)**: `/data/chroma_db/`

The app preserves all previously trained RAG data when running migrations.

## Performance

Column resizing is optimized for large datasets:
- Smooth dragging even with 1000+ rows
- Minimal CPU usage during resize
- No noticeable latency

## Support

For issues or questions:
- Check the application logs in the terminal
- Review `SESSION_SUMMARY.md` for recent changes
- See `COLUMN_RESIZE_IMPLEMENTATION.md` for technical details

---

**Enjoy the improved table experience!** 🎉
