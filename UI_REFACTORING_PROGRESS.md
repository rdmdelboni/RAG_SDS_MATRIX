# UI Refactoring Progress Report

## Completed (3/6 Phases)

### ✅ Phase 1: Extract Shared Infrastructure
- **workers.py** (50 lines)
  - WorkerSignals: Qt signal definitions
  - TaskRunner: Generic thread pool executor
- **styled_widgets.py** (200+ lines)
  - Reusable styling functions: `style_button()`, `style_label()`, `style_table()`, etc.
  - Converts instance methods to module-level functions for reusability
- **components/__init__.py** 
  - Exports all styling and worker utilities

### ✅ Phase 2: Create Tab Base Classes  
- **tabs/__init__.py** (120 lines)
  - `TabContext`: Dataclass with all shared services (db, ingestion, ollama, colors, etc.)
  - `BaseTab`: Base QWidget class providing:
    - Access to context and colors
    - Style methods: `_style_button()`, `_style_label()`, etc.
    - Status callbacks: `_set_status()`, `_on_error()`
    - Task execution: `_start_task()`

### ✅ Phase 3 (Partial): Extract Simple Tabs
- **backup_tab.py** (90 lines)
  - Complete template showing extraction pattern
  - UI creation: `_build_ui()`
  - Event handlers: `_on_backup()`, `_backup_task()`, `_on_backup_done()`
  - Demonstrates clean separation of concerns

## Remaining (3/6 Phases)

### Phase 3 (Continued): Extract Remaining Simple Tabs
The following tabs follow the **EXACT SAME PATTERN** as BackupTab:

1. **review_tab.py** (~60 lines)
   - Handlers: `_on_refresh_review()`, `_on_review_loaded()`
   - UI: Table with 6 columns
   - Uses shared: `_populate_table()`, `_colorize_not_found_in_review()`

2. **records_tab.py** (~70 lines)
   - Handlers: `_on_refresh_records()`, `_on_records_loaded()`
   - UI: Table with 7 columns + SpinBox for limit
   - Uses shared: `_populate_table()`

3. **status_tab.py** (~100 lines)
   - Handlers: `_refresh_db_stats()` (called on init)
   - UI: 3 info sections (Database, Ollama, RAG) with styled frames
   - No async tasks - purely display

### Phase 4: Extract Complex Tabs
These tabs have more business logic and state management:

1. **rag_tab.py** (~250 lines)
   - Features: File ingestion, URL ingestion, sources table, logs
   - Handlers: `_on_ingest_files()`, `_on_ingest_url()`, `_on_ingest_done()`
   - Uses: `_refresh_sources_table()`, `_refresh_rag_stats()`

2. **sds_tab.py** (~350 lines) - LARGEST TAB
   - Features: Folder selection, processing controls, progress bar, results table
   - Handlers: `_on_process_sds()`, `_on_file_processed()`, `_on_sds_done()`
   - Complex state: `_processing_file_map`, `_processing_name_map`, `_cancel_processing`
   - Uses: `_resolve_row_index()`, `_format_status()`, progress callbacks

3. **chat_tab.py** (~90 lines)
   - Features: Chat display, input, send button
   - Handlers: `_on_chat_send()`, chat task execution
   - Uses RAG retrieval + Ollama LLM

4. **regex_lab_tab.py** (~250 lines)
   - Features: File picker, profile selector, test buttons
   - Handlers: Regex testing, heuristic extraction

5. **automation_tab.py** (~200 lines)
   - Features: Workflow configuration, execution controls
   - Handlers: Automation pipeline handlers

### Phase 5: Refactor MainWindow
- Remove all `_create_*_tab()` methods (~500 lines removed)
- Remove styling methods (~150 lines moved)
- Keep only: initialization, context setup, callbacks, status management
- **Result**: 2,345 → ~500 lines

### Phase 6: Testing & Integration
- Verify all tabs functional
- Test signal/callback flow
- Run full regression suite
- Single commit

## Key Insights for Remaining Work

### Shared Methods (Stay in MainWindow)
These helpers are called by multiple tabs - keep in MainWindow, pass methods via TabContext:

```python
# In TabContext callbacks
get_db_manager = Callable  # For DB operations
_populate_table = Callable  # For filling tables  
_colorize_not_found_in_review = Callable  # Special formatting
_refresh_rag_stats = Callable  # RAG status update
_refresh_db_stats = Callable  # DB status update
```

### Tab Dependency Graph
```
BackupTab      (independent) ✅
ReviewTab      → _populate_table, _colorize_not_found_in_review  
RecordsTab     → _populate_table
StatusTab      → _refresh_db_stats, _refresh_rag_stats
RAGTab         → _refresh_rag_stats, _refresh_sources_table
SDSTab         → _populate_table (complex - many helper methods)
ChatTab        → ingestion.retriever, ollama
RegexLabTab    → profile_router, heuristics
AutomationTab  → (varies - check implementation)
```

### Code Extraction Template
For each tab:
1. Copy `_create_*_tab()` → `_build_ui()` method
2. Copy all `_on_*` handlers → tab methods
3. Replace `self._style_*` calls with parent class methods
4. Replace `self.colors` with `self.colors` (from BaseTab)
5. Replace `self._start_task` with `self._start_task` (from BaseTab)
6. Update any direct MainWindow references → `self.context.*`

## Effort Estimate

| Phase | Time | Complexity |
|-------|------|-----------|
| Phases 1-2 ✅ | 3h | Low |
| Phase 3 (rest) | 2h | Low-Medium |
| Phase 4 | 4h | Medium-High |
| Phase 5 | 1h | Low |
| Phase 6 | 1h | Low |
| **Total Remaining** | **8h** | - |

## Next Steps

To continue, recommend:
1. Create remaining simple tabs (3, 4, 5 above) - follows BackupTab pattern exactly
2. Create complex tabs with full handler extraction
3. Refactor MainWindow to integrate all tabs via TabContext
4. Full functional testing
5. Single commit documenting all changes

The pattern is now established. All remaining tabs follow the same structure.
