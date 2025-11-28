# UI Integration Guide - RAG SDS Matrix

## Overview

All CLI tools have been modularized into customtkinter UI tabs for seamless integration into the main application.

## Architecture

```
src/ui/
├── app.py                 # Main application window (1,776 lines)
├── tabs/
│   ├── __init__.py       # Tab exports
│   └── ui_tabs.py        # Modular tab implementations (NEW)
├── theme.py              # Color and styling configuration
└── components/           # Future: Reusable UI components
```

## Tab Implementation

### 1. **RAGViewerTab** - Query RAG Knowledge Base
**Purpose**: Display and search RAG records
**Features**:
- Query incompatibilities, hazards, CAMEO chemicals, file documents
- Limit results (configurable)
- Real-time results display
- Multi-threaded to prevent UI freezing

**Integration**:
```python
from src.ui.tabs import RAGViewerTab

# In app.py _setup_rag_tab():
viewer = RAGViewerTab(tab)
viewer.pack(fill="both", expand=True)
```

**Methods**:
- `_setup_ui()` - Initialize UI components
- `_on_query()` - Execute RAG query via subprocess

**Data Flow**:
```
RAGViewerTab._on_query()
  → subprocess.run(scripts/rag_records.py)
  → Display results in text widget
```

---

### 2. **SDSProcessorTab** - Process SDS Files
**Purpose**: Complete SDS processing workflow
**Features**:
- Folder selection dialog
- Multiple processing modes:
  - List files only
  - Extract & classify
  - Full pipeline (deduplication → extraction → processing)
  - RAG-enhanced processing (extracts + enriches with RAG knowledge)
- Real-time progress display
- Multi-threaded processing

**Integration**:
```python
from src.ui.tabs import SDSProcessorTab

# In app.py _setup_sds_tab():
processor = SDSProcessorTab(tab)
processor.pack(fill="both", expand=True)
```

**Methods**:
- `_setup_ui()` - Initialize UI components
- `_select_input_folder()` - Launch folder selection dialog
- `_on_process()` - Execute processing pipeline

**Processing Modes**:
```
Mode: "list"    → sds_pipeline.py --list-only
Mode: "extract" → sds_pipeline.py --extract-only
Mode: "full"    → sds_pipeline.py (all steps)
Mode: "rag"     → rag_sds_processor.py (RAG-enhanced)
```

---

### 3. **BackupTab** - Backup & Export
**Purpose**: Export RAG data for backup/sharing
**Features**:
- One-click RAG backup
- JSON + CSV dual format
- Automatic versioning with timestamp
- Output folder selection
- Progress display

**Integration**:
```python
from src.ui.tabs import BackupTab

# Create custom tab for backup:
backup = BackupTab(tab)
backup.pack(fill="both", expand=True)
```

**Methods**:
- `_setup_ui()` - Initialize UI components
- `_on_backup_rag()` - Execute backup process

**Data Flow**:
```
BackupTab._on_backup_rag()
  → subprocess.run(scripts/rag_backup.py)
  → Display export results
  → Show completion message
```

---

## Integration Steps

### Step 1: Add Tabs to Main Application
Update `src/ui/app.py` to import and use the new tabs:

```python
from .tabs import RAGViewerTab, SDSProcessorTab, BackupTab

class Application(ctk.CTk):
    def _setup_rag_tab(self) -> None:
        """Setup RAG Knowledge Base tab."""
        tab = self.tab_view.tab("RAG")
        
        # Add RAG viewer
        viewer = RAGViewerTab(tab)
        viewer.pack(fill="both", expand=True, padx=10, pady=10)
    
    def _setup_sds_tab(self) -> None:
        """Setup SDS Processing tab."""
        tab = self.tab_view.tab("SDS")
        
        # Add SDS processor
        processor = SDSProcessorTab(tab)
        processor.pack(fill="both", expand=True, padx=10, pady=10)
```

### Step 2: Create New Tab for Backup
Add a new tab in `_setup_ui()`:

```python
def _setup_ui(self) -> None:
    # ... existing tab setup ...
    self.tab_view.add("Backup & Export")
    
    # Setup new backup tab
    backup_tab = self.tab_view.tab("Backup & Export")
    backup = BackupTab(backup_tab)
    backup.pack(fill="both", expand=True, padx=10, pady=10)
```

### Step 3: Update Tab Navigation
Modify `_setup_ui()` to use the new tabs:

```python
# Instead of placeholder implementations, use modular tabs:
self._setup_rag_viewer_tab()      # Uses RAGViewerTab
self._setup_sds_processor_tab()   # Uses SDSProcessorTab
self._setup_backup_tab()          # Uses BackupTab
```

---

## Tab Features

### Multi-Threading
All tabs use threading to prevent UI freezing:

```python
def run_query():
    # Heavy operation
    result = subprocess.run(cmd, ...)
    
thread = threading.Thread(target=run_query, daemon=True)
thread.start()
```

### File Dialogs
Tabs use `tkinter.filedialog` for user-friendly folder/file selection:

```python
folder = filedialog.askdirectory(title="Select Input Folder")
```

### Error Handling
All operations wrapped in try-except with user feedback:

```python
try:
    result = subprocess.run(cmd, ...)
    self.results_text.insert("end", result.stdout)
except Exception as e:
    messagebox.showerror("Error", str(e))
```

---

## Configuration

### Theme Support
Tabs automatically use theme colors from `get_colors()`:

```python
self.colors = get_colors("dark")  # or "light"

# Use colors:
ctk.CTkButton(..., fg_color=self.colors["accent"])
```

### Color Scheme
Available colors:
- `bg` - Background
- `surface` - Surface/panel background
- `text` - Primary text
- `text_secondary` - Secondary text
- `accent` - Accent color (buttons)
- `success` - Success color (green)
- `error` - Error color (red)

---

## CLI Tool Integration

Each tab integrates with corresponding CLI tools via subprocess:

| Tab | CLI Script | Command |
|-----|-----------|---------|
| RAGViewerTab | rag_records.py | `python scripts/rag_records.py --{query_type} --limit {n}` |
| SDSProcessorTab | sds_pipeline.py | `python scripts/sds_pipeline.py --input {folder} [--list-only \| --extract-only]` |
| SDSProcessorTab | rag_sds_processor.py | `python scripts/rag_sds_processor.py --input {folder}` |
| BackupTab | rag_backup.py | `python scripts/rag_backup.py --output {folder}` |

---

## Usage Examples

### Example 1: Query RAG from UI
1. Open "RAG" tab
2. Select query type (e.g., "Incompatibilities")
3. Set result limit
4. Click "🔍 Query RAG"
5. Results display in text area

### Example 2: Process SDS with RAG Enhancement
1. Open "SDS Processing" tab
2. Click "Choose Folder" and select SDS input folder
3. Select "RAG-enhanced processing" mode
4. Click "▶ Process SDS"
5. Monitor progress in text area

### Example 3: Backup RAG Data
1. Open "Backup & Export" tab
2. Click "🔄 Backup RAG Data"
3. Select output folder
4. Wait for completion message
5. Files saved to selected folder (JSON + CSV)

---

## Extension Points

### Adding New Tabs
Create a new class inheriting from `ctk.CTkFrame`:

```python
class NewFeatureTab(ctk.CTkFrame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.colors = get_colors("dark")
        self._setup_ui()
    
    def _setup_ui(self):
        # UI components here
        pass
```

### Customizing Appearance
Modify colors in tab's `_setup_ui()`:

```python
self.colors = get_colors("light")  # Switch theme

ctk.CTkButton(
    frame,
    fg_color=self.colors["success"],  # Green button
)
```

### Adding Progress Bars
Use `CTkProgressBar` for long operations:

```python
self.progress = ctk.CTkProgressBar(
    self,
    fg_color=self.colors["surface"],
    progress_color=self.colors["accent"],
)
self.progress.pack(fill="x", padx=10, pady=5)

# Update progress:
self.progress.set(0.5)  # 50%
```

---

## Performance Considerations

1. **Threading**: All subprocess calls are threaded to prevent UI freezing
2. **Text Widget Updates**: Use `.update()` to refresh display
3. **Memory**: Text widgets automatically manage scrolling
4. **Subprocess Limits**: Each operation runs in separate process

---

## Testing

### Test RAGViewerTab
```bash
python -c "
import customtkinter as ctk
from src.ui.tabs import RAGViewerTab

app = ctk.CTk()
tab = RAGViewerTab(app)
tab.pack(fill='both', expand=True)
app.mainloop()
"
```

### Test SDSProcessorTab
```bash
python -c "
import customtkinter as ctk
from src.ui.tabs import SDSProcessorTab

app = ctk.CTk()
tab = SDSProcessorTab(app)
tab.pack(fill='both', expand=True)
app.mainloop()
"
```

### Test BackupTab
```bash
python -c "
import customtkinter as ctk
from src.ui.tabs import BackupTab

app = ctk.CTk()
tab = BackupTab(app)
tab.pack(fill='both', expand=True)
app.mainloop()
"
```

---

## Next Steps

1. ✅ Create modular tab implementations (ui_tabs.py)
2. ⏳ Integrate tabs into main app.py
3. ⏳ Add progress bars with `CTkProgressBar`
4. ⏳ Add real-time status updates
5. ⏳ Create results visualization (tables, charts)
6. ⏳ Add configuration options
7. ⏳ Implement keyboard shortcuts
8. ⏳ Add logging/debug console tab

---

## File Structure
```
src/ui/
├── app.py                    # Main application
├── tabs/
│   ├── __init__.py
│   └── ui_tabs.py           # RAGViewerTab, SDSProcessorTab, BackupTab
├── theme.py                 # Colors & styling
└── components/
    └── (future: reusable components)

scripts/
├── rag_records.py           # Query RAG (integrated via RAGViewerTab)
├── rag_backup.py            # Backup RAG (integrated via BackupTab)
├── sds_pipeline.py          # SDS workflow (integrated via SDSProcessorTab)
├── rag_sds_processor.py     # RAG-enhanced SDS (integrated via SDSProcessorTab)
└── *.sh                     # Bash wrappers
```

---

## Support

For issues or questions:
1. Check logs in `data/logs/` directory
2. Review individual tab documentation
3. Verify CLI scripts work standalone
4. Check for subprocess errors in UI

