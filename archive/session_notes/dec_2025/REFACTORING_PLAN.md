# UI Refactoring Plan: Decompose Monolithic app.py (2,345 lines)

## Executive Summary
Break down the 2,345-line `src/ui/app.py` into modular, testable tab components while preserving all functionality and maintaining backward compatibility.

---

## Current State Analysis

### Structure
- **File Size**: 2,345 lines
- **Classes**: 3 (WorkerSignals, TaskRunner, MainWindow)
- **Methods**: 96 total (94 in MainWindow)
- **Tabs**: 10 UI tabs with 9 `_create_*_tab()` methods

### Tabs to Extract
1. RAG Tab (lines 191-252, ~60 lines)
2. SDS Tab (lines 253-452, ~200 lines)
3. Status Tab (lines 453-554, ~100 lines)
4. Records Tab (lines 555-601, ~45 lines)
5. Review Tab (lines 602-630, ~30 lines)
6. Backup Tab (lines 631-656, ~25 lines)
7. Chat Tab (lines 657-718, ~60 lines)
8. Automation Tab (lines 1318+, ~150 lines)
9. Regex Lab Tab (lines 1112-1317, ~200 lines)
10. Placeholder Tab (generic helper, keep in core)

### Shared State (MainWindow Services)
- **Backend Services**: db, ingestion, ollama, profile_router, heuristics, sds_extractor
- **Theme System**: colors, app_settings
- **Threading**: thread_pool, _cancel_processing
- **Status System**: status_bar, status_label, _set_status()
- **Styling Helpers**: _style_button(), _style_label(), _style_table(), etc.
- **Task Execution**: _start_task(), worker signal handling

### Interdependencies
- Tabs need access to main window's services
- Tab events need to update MainWindow status
- Async operations span tab lifecycle
- Some processing state is shared (file maps, cancellation flags)

---

## Proposed Refactoring Strategy

### Architecture Pattern: Hybrid Tab Components with Shared Context

**Design Rationale:**
- Extract UI creation from logic (Pure Composition)
- Provide shared services via context object
- Use signals for cross-component communication
- Minimize MainWindow coupling while keeping code simple

### New Directory Structure

```
src/ui/
├── app.py                          # Refactored MainWindow (core orchestration only)
├── theme.py                        # (unchanged)
├── tabs/
│   ├── __init__.py                # TabContext definition, base classes
│   ├── base.py                    # BaseTab class with common functionality
│   ├── rag_tab.py                 # RAG ingestion tab
│   ├── sds_tab.py                 # SDS processing tab
│   ├── status_tab.py              # Status monitoring tab
│   ├── records_tab.py             # Records display tab
│   ├── review_tab.py              # Review functionality
│   ├── backup_tab.py              # Backup operations
│   ├── chat_tab.py                # Chat interface
│   ├── regex_lab_tab.py           # Regex testing
│   └── automation_tab.py          # Automation workflows
└── components/
    ├── __init__.py                # Shared UI components
    ├── styled_widgets.py          # Reusable styled widgets
    └── workers.py                 # (move from app.py) TaskRunner, WorkerSignals
```

### Implementation Steps

#### Phase 1: Extract Shared Infrastructure (1 hour)
1. **Create `src/ui/components/workers.py`**
   - Move `WorkerSignals` class
   - Move `TaskRunner` class
   - Keep imports simple

2. **Create `src/ui/components/styled_widgets.py`**
   - Extract styling helper methods → reusable functions
   - Convert instance methods to module-level functions
   - Signature: `style_button(btn, colors)`, `style_label(label, colors)`, etc.

3. **Create `src/ui/tabs/base.py`**
   - Define `TabContext` dataclass:
     ```python
     @dataclass
     class TabContext:
         db: DatabaseManager
         ingestion: KnowledgeIngestionService
         ollama: OllamaClient
         profile_router: ProfileRouter
         heuristics: HeuristicExtractor
         sds_extractor: SDSExtractor
         colors: dict
         app_settings: QSettings
         thread_pool: QThreadPool
         # Callbacks for MainWindow communication
         set_status: Callable[[str], None]
         on_error: Callable[[str], None]
         start_task: Callable[...]
     ```
   - Define `BaseTab(QWidget)` with:
     - `__init__(context: TabContext)`
     - Common methods: `_style_button()`, `_style_label()`, `_set_status()`
     - Access to all context services

#### Phase 2: Extract Utility Tab Classes (2 hours)
4. **Create `src/ui/tabs/status_tab.py`**
   - Extract `_create_status_tab()` → `StatusTab` class
   - Move all status-related handlers
   - Size: ~100 lines

5. **Create `src/ui/tabs/records_tab.py`**
   - Extract Records tab functionality
   - Size: ~50 lines

6. **Create `src/ui/tabs/review_tab.py`**
   - Extract Review tab functionality
   - Size: ~40 lines

7. **Create `src/ui/tabs/backup_tab.py`**
   - Extract Backup tab functionality
   - Size: ~30 lines

#### Phase 3: Extract Complex Tab Classes (4 hours)
8. **Create `src/ui/tabs/rag_tab.py`**
   - Extract RAG ingestion tab
   - Include: file ingestion, URL ingestion, sources table, logs
   - Handlers: `_on_ingest_files()`, `_on_ingest_url()`, `_refresh_sources_table()`, etc.
   - Signals connected back to MainWindow
   - Size: ~200 lines

9. **Create `src/ui/tabs/sds_tab.py`**
   - Extract SDS processing tab (LARGEST TAB)
   - Include: folder selection, processing controls, table, progress bar
   - Handlers: all SDS processing logic, file result callbacks, progress updates
   - Keep: `_process_sds_task()`, `_on_file_processed()`, `_on_sds_done()`, etc.
   - Challenge: Shared `_processing_file_map`, `_processing_name_map`
   - Solution: Pass these through signals/callbacks
   - Size: ~300 lines

10. **Create `src/ui/tabs/chat_tab.py`**
    - Extract Chat tab
    - Size: ~70 lines

11. **Create `src/ui/tabs/regex_lab_tab.py`**
    - Extract Regex Lab tab
    - Include: regex editor, test patterns, results display
    - Size: ~220 lines

12. **Create `src/ui/tabs/automation_tab.py`**
    - Extract Automation tab
    - Include: workflow configuration, execution controls
    - Size: ~180 lines

#### Phase 4: Refactor MainWindow (2 hours)
13. **Refactor `src/ui/app.py`**
    - Remove all `_create_*_tab()` methods (moved to modules)
    - Remove styling methods (moved to components)
    - Keep only:
      - Theme initialization
      - Service initialization
      - Tab instantiation and addition to QTabWidget
      - Callback handlers for tab events
      - Status bar management
      - Window lifecycle
      - Helper utilities shared across tabs
    - New `_build_ui()`:
      ```python
      def _build_ui(self):
          central = QWidget()
          layout = QVBoxLayout(central)

          # Header
          header = self._build_header()
          layout.addWidget(header)

          # Create context for tabs
          context = TabContext(
              db=self.db,
              ingestion=self.ingestion,
              ollama=self.ollama,
              ...
              set_status=self._set_status,
              on_error=self._on_error,
              start_task=self._start_task,
          )

          # Instantiate and add tabs
          self.tabs = QTabWidget()
          self.tabs.addTab(RAGTab(context), "RAG")
          self.tabs.addTab(SDSTab(context), "SDS")
          # ...
          layout.addWidget(self.tabs)

          self.setCentralWidget(central)
      ```
    - Result: ~500-600 lines (down from 2,345)

#### Phase 5: Testing & Verification (1 hour)
14. **Verify Functionality**
    - All 10 tabs functional
    - Styling preserved
    - Signals/callbacks working
    - No regressions

15. **Update Imports**
    - `from .tabs import RAGTab, SDSTab, ...`
    - `from .components import style_button, style_label, ...`

---

## Benefits

| Aspect | Before | After |
|--------|--------|-------|
| **Lines in app.py** | 2,345 | ~550 |
| **Largest file size** | 2,345 lines (app.py) | ~300 lines (sds_tab.py) |
| **Testability** | Coupled to MainWindow | Independent tab classes |
| **Maintainability** | Hard to modify tabs | Easy to modify/extend |
| **Reusability** | Styling scattered | Reusable styled components |
| **Scalability** | Adding tabs difficult | Simple class per tab |

---

## Backwards Compatibility

✅ **Preserved:**
- All existing functionality
- All UI behavior and styling
- Signal handling and threading
- Service layer interfaces
- Configuration loading

✅ **No breaking changes** (internal refactoring only)

---

## Risk Analysis

### Low Risk
- Pure structural reorganization
- No logic changes
- Tab dependencies are well-defined
- Existing tests unaffected

### Medium Risk
- Threading/signal connections (verify carefully)
- Context object initialization (ensure all services passed)
- Processing state maps in SDS tab (needs callback mechanism)

### Mitigation
- Extract one tab at a time (enable incremental validation)
- Preserve all signal emissions
- Test each tab independently
- Run full integration tests before commit

---

## Recommended Approach

### Incremental Extraction (Lower Risk)
1. Extract `BaseTab` and styling utilities first
2. Extract simple tabs (Backup, Review, Records)
3. Extract RAG tab
4. Extract SDS tab (most complex - validate thoroughly)
5. Extract Chat, Regex Lab, Automation tabs
6. Refactor MainWindow last
7. Run full test suite
8. Single commit with message: "refactor(ui): decompose monolithic app.py into modular tabs"

### Expected Timeline
- **Planning**: Done
- **Phase 1-2**: 3 hours
- **Phase 3**: 4 hours
- **Phase 4**: 2 hours
- **Phase 5**: 1 hour
- **Total**: ~10 hours

---

## Open Questions for User

1. **Extraction Pace**: Implement all at once or incrementally (test after each tab)?
2. **Testing**: Should we add unit tests for individual tabs as part of this refactoring?
3. **Tab Plugins**: Would you like a registry pattern for dynamic tab loading in the future?
