# RAG SDS Matrix UI User Guide

## Complete Guide to Using the Application

**Last Updated:** December 4, 2025
**Target Audience:** End Users, Operators, QA
**Difficulty Level:** Beginner to Intermediate

---

## Table of Contents

1. [Getting Started](#getting-started)
2. [Main Features](#main-features)
3. [RAG Knowledge Base Tab](#rag-knowledge-base-tab)
4. [SDS Processing Tab](#sds-processing-tab)
5. [Automation Tab](#automation-tab)
6. [Review & Edit Tab](#review--edit-tab)
7. [Records Tab](#records-tab)
8. [Chat Tab](#chat-tab)
9. [Status Tab](#status-tab)
10. [Tips & Troubleshooting](#tips--troubleshooting)

---

## Getting Started

### Launching the Application

```bash
python -m src.ui.app
```

The application window will open with multiple tabs at the bottom. Each tab provides different functionality.

### Application Layout

```
┌────────────────────────────────────────────────────────────┐
│  RAG SDS Matrix                                    [_][□][×] │
├────────────────────────────────────────────────────────────┤
│ [File] [Edit] [View] [Tools] [Help]                        │
├────────────────────────────────────────────────────────────┤
│                                                             │
│                    Main Content Area                        │
│              (Changes based on selected tab)                │
│                                                             │
│                                                             │
├────────────────────────────────────────────────────────────┤
│ [🧠 RAG] [📄 SDS] [⚙️ Automation] [✎ Review] [📋 Records]  │
│ [💬 Chat] [🔧 Regex Lab] [⚡ Status] [💾 Backup]           │
└────────────────────────────────────────────────────────────┘
```

### Status Bar

At the bottom of the application, you'll see:
- **Status messages** showing current operation
- **Progress bar** (appears during long operations)
- **Cancel button** (appears during running tasks)

---

## Main Features

### Feature 1: Real-Time Progress Tracking

When performing long operations, you'll see:

```
📊 Progress Bar  ▓▓▓▓▓░░░░░░░░░░░░░░░ 25%

📝 Status Message: Processing file 5 of 20...
```

**What it shows:**
- Percentage complete (0-100%)
- Detailed progress message
- Estimated work remaining

### Feature 2: Task Cancellation

When a task is running, a red "⊗ Cancel" button appears:

```
[⊗ Cancel Task]
```

**To cancel:**
1. Click the "⊗ Cancel" button
2. Wait for the task to complete cancellation
3. Message will show "Cancelled" when done

**Note:** Not all tasks have instant cancellation. The system will stop at the nearest safe point.

### Feature 3: Change Tracking (Review Tab)

When editing cells in the review table:
- Changes are automatically tracked
- A status shows "📝 3 change(s) pending"
- You can Save or Discard changes

### Feature 4: Data Refresh

Most tabs have a "🔄 Refresh" button:
- Reloads data from the database
- Updates statistics and displays
- Shows progress during refresh

---

## RAG Knowledge Base Tab

### Purpose
Manage the knowledge base used for AI reasoning. "RAG" stands for Retrieval-Augmented Generation.

### Main Functions

#### 1. Ingest Files

```
[📁 Ingest Files...]  [📂 Ingest Folder]  [🌐 Ingest URL]
```

**To ingest files:**
1. Click "📁 Ingest Files..." button
2. Select one or more PDF/document files
3. Progress bar appears showing ingestion progress
4. When complete: "✓ Ingested X documents, Y chunks"

**File types supported:**
- PDF documents
- Text files
- DOCX files
- Other document formats

**What happens:**
- Files are read and split into chunks
- Content is embedded into vector database
- Indexed for semantic search

#### 2. Ingest from Folder

```
[📂 Ingest Folder]
```

**To ingest from folder:**
1. Click "📂 Ingest Folder" button
2. Select a folder containing documents
3. All supported documents in folder are ingested
4. Progress shows file count and current file

**Use case:**
- Batch import large document collections
- Import entire project documentation

#### 3. Ingest from URL

```
[🌐 Ingest URL]

URL Input: [___________________________________]
```

**To ingest from URL:**
1. Paste a URL into the "URL Input" field
2. Click "🌐 Ingest URL" button
3. Webpage is downloaded and indexed
4. Progress shows download progress

**Supports:**
- Regular web pages
- PDF downloads
- Document links

#### 4. View Ingested Sources

The "Sources in Knowledge Base" table shows:
- **Title**: Document name
- **Type**: Document vs. Web page
- **Path**: File location or URL
- **Chunks**: Number of text chunks
- **Indexed**: When it was added

**To refresh sources:**
1. Click "🔄 Refresh" button
2. Table updates with latest sources

#### 5. Knowledge Base Statistics

Shows at the top:
```
📊 Knowledge Base Statistics:
   • Total Documents: 45
   • Processed: 42
   • Failed: 3
   • RAG Documents: 38
   • Total Chunks: 234
   • Last Updated: 2025-12-04 14:30
```

---

## SDS Processing Tab

### Purpose
Process Safety Data Sheets (SDS) and extract chemical information. Build a comparison matrix of chemicals.

### Workflow

#### Step 1: Select Folder

```
[📂 Select Folder]  Selected: /path/to/sds/files
```

1. Click "📂 Select Folder"
2. Choose folder containing SDS PDF files
3. Folder path shows in the field

#### Step 2: Review Files

A file list appears:
- Shows all PDF files in the folder
- Indicates processing status (✓, ✗, ⏳)
- Shows extraction results

**Selection options:**
```
[✓ All Files]  [⊗ Pending Only]
```

- "✓ All Files": Process all documents
- "⊗ Pending Only": Skip already processed files

#### Step 3: Process SDS Files

```
[▶ Process SDS Files]
```

1. Select files to process
2. Click "▶ Process SDS Files"
3. Progress bar shows processing progress
4. For each file:
   - Extracts hazard information
   - Extracts chemical properties
   - Queries RAG knowledge base (if enabled)

**Processing result:**
```
📝 Processing file 7 of 12: chemical_safety_07.pdf

[▓▓▓▓▓▓░░░░░░░░░░░░░░░░░░] 58%
```

#### Step 4: Build Matrix

```
[📊 Build Matrix]
```

1. After processing completes, click "📊 Build Matrix"
2. Matrix combines all extracted data
3. Creates comparison across all chemicals
4. Shows success or any errors

**Result:**
```
✓ Matrix built with 12 chemicals, 234 data points
```

#### Step 5: Export Results

```
[💾 Export]
```

1. Click "💾 Export" button
2. Choose format:
   - **Excel** (*.xlsx) - Formatted spreadsheet
   - **CSV** (*.csv) - Comma-separated values
3. Choose save location
4. Export completes with summary

---

## Automation Tab

### Purpose
Automate harvesting of SDS documents and batch processing. Schedule recurring harvests.

### Section 1: Harvest Process

**One-time SDS harvesting from CAS numbers.**

```
┌────────────────────────────────┐
│ 1. HARVEST PROCESS            │
├────────────────────────────────┤
│ CAS File: [__________] [📁]    │
│ Output:   [__________] [📁]    │
│ Limit:    [3  ▼]              │
│           ☐ Process SDS       │
│           ☐ Use RAG           │
│ [▶ Start Harvest]             │
└────────────────────────────────┘
```

**To harvest SDS:**

1. **Select CAS File:**
   - Click "📁" button next to "CAS File"
   - Choose text file with CAS numbers (one per line)
   - Example file:
     ```
     67-64-1      # Acetone
     64-17-5      # Ethanol
     7732-18-5    # Water
     ```

2. **Select Output Folder:**
   - Click "📁" button next to "Output"
   - Choose where to save downloaded SDS files

3. **Set Download Limit:**
   - Default is 3 SDS per CAS number
   - Increase for more comprehensive search
   - Decrease for faster processing

4. **Optional Settings:**
   - ☐ **Process SDS**: Immediately process downloaded files
   - ☐ **Use RAG**: Query knowledge base during processing

5. **Start Harvest:**
   - Click "▶ Start Harvest"
   - Progress shows:
     ```
     📊 Searching CAS: 67-64-1...
     Downloaded 2/3 documents
     ```

### Section 2: Scheduled Harvesting

**Automated harvesting on a repeating schedule.**

```
┌────────────────────────────────┐
│ 2. SCHEDULED HARVEST          │
├────────────────────────────────┤
│ CAS File:    [__________] [📁] │
│ Interval:    [60  ▼] minutes   │
│ Iterations:  [0   ▼] (0=infinite)│
│ Output:      [__________] [📁] │
│ Limit:       [3  ▼]           │
│              ☐ Process        │
│              ☐ Use RAG        │
│ [▶ Start Scheduler]           │
└────────────────────────────────┘
```

**To schedule harvests:**

1. **Configure Schedule:**
   - Set interval in minutes (e.g., 60 = hourly)
   - Set iterations (0 = runs forever, 1 = once, 5 = 5 times)

2. **Start Scheduler:**
   - Click "▶ Start Scheduler"
   - Harvest runs immediately, then repeats on schedule
   - Status shows current iteration

**Example schedules:**
- **Hourly updates**: Interval=60, Iterations=0 (infinite)
- **Daily check**: Interval=1440, Iterations=0 (daily)
- **Weekly batch**: Interval=10080, Iterations=4 (4 weeks)

**Cancel scheduling:**
- Click "⊗ Cancel" during any harvest run
- Scheduler will stop after current iteration

### Section 3: Packet Export

**Export collected SDS into organized packet.**

```
┌────────────────────────────────┐
│ 3. EXPORT PACKET              │
├────────────────────────────────┤
│ Matrix File: [__________] [📁] │
│ SDS Folder:  [__________] [📁] │
│ [▶ Export Packet]             │
└────────────────────────────────┘
```

**To export packet:**

1. Select matrix file (from SDS Processing tab)
2. Select folder containing harvested SDS
3. Click "▶ Export Packet"
4. Creates structured packet with:
   - Master matrix spreadsheet
   - Organized SDS documents
   - Summary metadata

### Section 4: Generate SDS PDF

**Generate formatted Safety Data Sheet from extracted data.**

```
┌────────────────────────────────┐
│ 4. GENERATE SDS PDF           │
├────────────────────────────────┤
│ Data File:   [__________] [📁] │
│ Output:      [__________] [📁] │
│ [▶ Generate PDF]              │
└────────────────────────────────┘
```

**To generate SDS PDF:**

1. Select JSON data file with chemical information
2. Select output folder for PDF
3. Click "▶ Generate PDF"
4. Formatted PDF is created with:
   - Chemical properties
   - Hazard information
   - Safety procedures
   - Emergency contacts

---

## Review & Edit Tab

### Purpose
Review extracted chemical data and make corrections before saving to database.

### Table Layout

```
┌───────────────────────────────────────────────────────┐
│ File         │ Status    │ Product   │ CAS  │ UN   │ Hazard
├───────────────────────────────────────────────────────┤
│ chem_01.pdf  │ SUCCESS   │ Acetone   │ 67.. │ 1987 │ 3
│ chem_02.pdf  │ NOT_FOUND │ Ethanol   │ 64.. │ 1170 │ 3
│ chem_03.pdf  │ SUCCESS   │ Water     │ 77.. │ N/A  │ ?
└───────────────────────────────────────────────────────┘
```

### Editing Data

**To edit a cell:**

1. Click on any cell (except File column)
2. Enter new value
3. Press Enter or click elsewhere
4. Change is tracked automatically

**Status indicators:**
- ✓ **SUCCESS**: Data successfully extracted
- ✗ **NOT_FOUND**: Extraction failed, needs review
- (Red text): NOT_FOUND entries highlighted

### Saving Changes

**After making edits:**

1. A message appears: "📝 3 change(s) pending"
2. Buttons enable:
   - **💾 Save Changes** (green button)
   - **↶ Discard Changes** (yellow button)

**To save:**
1. Click "💾 Save Changes"
2. Confirm in dialog: "Save 3 change(s) to database?"
3. Progress shows update status
4. When complete: "✓ Saved 3 changes"
5. Table refreshes with updated data

**To discard:**
1. Click "↶ Discard Changes"
2. Confirm: "Discard 3 pending change(s)?"
3. All edits are reverted
4. Table returns to original state

### Refresh Data

**To reload from database:**

1. Click "🔄 Refresh"
2. Fetches latest 100 records
3. All edits are cleared
4. Table updates with current data

---

## Records Tab

### Purpose
Browse and search all processed chemical records in the database.

### Features

```
Search: [___________________________] [🔍]

Results: 243 records found

┌──────────────────────────────────┐
│ Filename │ Status │ Product │ CAS │
├──────────────────────────────────┤
│          │        │         │     │
│ (Table content)                  │
└──────────────────────────────────┘

[◀ Previous] [1] [2] [3] [Next ▶]
```

### Searching

**To search records:**

1. Type in search field
2. Results filter in real-time
3. Shows matching records

**Search by:**
- Filename
- Product name
- CAS number
- UN number
- Status

---

## Chat Tab

### Purpose
Interact with AI assistant using the indexed knowledge base.

### Usage

```
┌─────────────────────────────────────┐
│ Knowledge Base Chat                 │
├─────────────────────────────────────┤
│                                     │
│ Chat History:                       │
│                                     │
│ User: What are the hazards of      │
│       acetone?                      │
│                                     │
│ AI: According to the knowledge     │
│     base, acetone is flammable...  │
│                                     │
├─────────────────────────────────────┤
│ Your message: [_____________] [Send]│
└─────────────────────────────────────┘
```

### Features

1. **Context-Aware Responses:**
   - AI uses ingested documents for answers
   - Responses based on knowledge base
   - Shows confidence and sources

2. **Model Selection:**
   - Available models listed
   - Choose different AI models
   - Different models have different capabilities

3. **Clear History:**
   - Button to clear chat history
   - Starts fresh conversation

---

## Status Tab

### Purpose
View application status, statistics, and system information.

### Information Displayed

```
📊 Database Statistics
   • Total Records: 243
   • Processed: 215
   • Failed: 28
   • Success Rate: 88.5%

📈 Processing Statistics
   • Total Uploaded: 243 files
   • SDS Processed: 156
   • Documents Indexed: 1,024 chunks
   • Average Time: 2.3 seconds/file

⚙️ System Status
   • Database: Connected ✓
   • RAG System: Ready ✓
   • AI Models: Available (3 loaded)
   • Thread Pool: Active (4 workers)

📅 Activity Log
   (Recent operations with timestamps)
```

### Refresh

Click "🔄 Refresh" to update statistics.

---

## Tips & Troubleshooting

### General Tips

**Tip 1: Progress Indication**
- Long operations show progress bar
- Message updates every 1-2 seconds
- Don't close app during progress (use Cancel instead)

**Tip 2: Data Backup**
- Use Backup tab before large operations
- Export matrix before bulk changes
- Keep CAS lists as reference

**Tip 3: Batch Operations**
- Harvest multiple CAS numbers at once
- Process all SDS in folder together
- Schedule recurring operations

### Troubleshooting

**Problem: "File not found" error**
- **Solution**: Verify file path exists
- Check file permissions
- Ensure file format is supported

**Problem: Progress bar stuck**
- **Solution**: Wait 30 seconds (some operations take time)
- If truly stuck, click "⊗ Cancel"
- Check system resources (disk space, RAM)

**Problem: AI responses not working**
- **Solution**: Check Ollama is running
- Verify knowledge base has documents (RAG tab)
- Try refreshing in Status tab

**Problem: Changes not saving**
- **Solution**: Confirm save dialog when it appears
- Check database is connected (Status tab)
- Try saving again

**Problem: Missing "Cancel" button**
- **Solution**: Task is completing or already done
- Wait for progress to finish
- Cancel only appears during running operations

### Performance Tips

1. **Process files in batches:**
   - Process 50-100 SDS per batch
   - Give database time to commit

2. **Schedule harvests off-peak:**
   - Run at night or weekends
   - Reduces system load during work hours

3. **Archive old data:**
   - Archive processed records after 90 days
   - Keeps database responsive

4. **Use folder ingestion:**
   - Faster than individual files
   - Better for batch operations

---

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+Q` | Quit application |
| `Ctrl+R` | Refresh current tab |
| `Ctrl+S` | Save (if applicable) |
| `Ctrl+Z` | Undo (if applicable) |
| `Tab` | Next tab |
| `Shift+Tab` | Previous tab |
| `Escape` | Cancel operation |

---

## Common Workflows

### Workflow 1: Add Documents to Knowledge Base

1. Open **RAG Tab**
2. Click "📁 Ingest Files"
3. Select PDF documents
4. Wait for completion
5. Verify in "Sources" table
6. Check statistics updated

### Workflow 2: Process Chemical SDS

1. Open **SDS Tab**
2. Click "📂 Select Folder"
3. Choose folder with SDS files
4. Click "✓ All Files" (or "⊗ Pending Only")
5. Click "▶ Process SDS Files"
6. Wait for completion
7. Click "📊 Build Matrix"
8. Click "💾 Export" to save results

### Workflow 3: Review and Correct Data

1. Open **Review Tab**
2. Click "🔄 Refresh" to load latest records
3. Click cells to edit incorrect data
4. When done with edits:
   - Click "💾 Save Changes" to confirm, OR
   - Click "↶ Discard Changes" to revert
5. Table automatically refreshes

### Workflow 4: Automated Weekly Harvesting

1. Open **Automation Tab**
2. Create CAS file with target chemicals
3. In "Scheduled Harvest" section:
   - Set Interval: 10080 (minutes in week)
   - Set Iterations: 0 (infinite)
   - Enable "☐ Process SDS" and "☐ Use RAG"
4. Click "▶ Start Scheduler"
5. Monitor in Status tab

---

## Getting Help

- **Application Help**: Press `F1` or use Help menu
- **Feature Questions**: See relevant tab documentation
- **Report Issues**: Use Feedback or contact support
- **Check Logs**: Status tab shows recent activity

---

## Summary

RAG SDS Matrix provides:

✅ **Knowledge Base Management** - Index documents for AI reasoning
✅ **SDS Processing** - Extract chemical data automatically
✅ **Automated Harvesting** - Find and download SDS on schedule
✅ **Data Review** - Edit and verify extracted information
✅ **AI Chat** - Ask questions about ingested documents
✅ **Progress Tracking** - Real-time updates during operations
✅ **Cancellation Support** - Stop long operations safely
✅ **Batch Operations** - Process multiple files efficiently

---

## See Also

- [Handler Implementation Guide](HANDLER_IMPLEMENTATION_GUIDE.md)
- [Architecture Patterns](ARCHITECTURE_PATTERNS.md)
- [Project Completion Report](PROJECT_COMPLETION_REPORT.md)
