# Architecture Patterns Documentation

## RAG SDS Matrix UI Architecture

**Last Updated:** December 4, 2025
**Target Audience:** Architecture Reviewers, Core Developers, Contributors
**Difficulty Level:** Advanced

---

## Table of Contents

1. [Overview](#overview)
2. [Tab Modularization](#tab-modularization)
3. [TabContext Dependency Injection](#tabcontext-dependency-injection)
4. [Signal-Based Async Pattern](#signal-based-async-pattern)
5. [Styling System](#styling-system)
6. [Error Handling Architecture](#error-handling-architecture)
7. [Integration Patterns](#integration-patterns)
8. [Data Flow](#data-flow)
9. [Design Decisions](#design-decisions)
10. [Testing Architecture](#testing-architecture)

---

## Overview

RAG SDS Matrix UI follows a **modular, signal-driven architecture** that separates concerns across independent tabs while maintaining consistent patterns for state management, async operations, and UI updates.

### Architecture Principles

- **Modularity**: Each tab is an independent component with minimal coupling
- **Dependency Injection**: Services provided through TabContext, not created internally
- **Non-blocking UI**: All long operations run in background threads
- **Type Safety**: Full type hints across all modules
- **Testability**: Mocks can be easily injected for testing

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     MainWindow                               │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │                    Tab Stack                          │   │
│  │                                                       │   │
│  │  ┌────────────────────────────────────────────────┐  │   │
│  │  │              BaseTab                           │  │   │
│  │  │ (Abstract base with common UI patterns)        │  │   │
│  │  └────────────────────────────────────────────────┘  │   │
│  │        ▲              ▲              ▲                │   │
│  │        │              │              │                │   │
│  │  ┌─────┴────┐   ┌─────┴────┐  ┌─────┴────┐          │   │
│  │  │ RAGTab   │   │ SDSTab   │  │AutomationTab       │   │
│  │  │ (9 impl) │   │ (8 impl) │  │ (5 impl)│          │   │
│  │  └──────────┘   └──────────┘  └──────────┘          │   │
│  │                                                       │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐            │   │
│  │  │ReviewTab │ │StatusTab │ │ChatTab   │            │   │
│  │  └──────────┘ └──────────┘ └──────────┘            │   │
│  │                                                       │   │
│  └───────────────────┬──────────────────────────────────┘   │
│                      │                                       │
└──────────────────────┼───────────────────────────────────────┘
                       │
                       ▼
            ┌──────────────────────┐
            │   TabContext         │
            │  (Dependency Inject) │
            └──────────────────────┘
                   ▲ ▲ ▲ ▲ ▲ ▲
         ┌─────────┘ │ │ │ │ └─────────┐
         │           │ │ │ │           │
    ┌────▼──┐  ┌─────▼─┴─┴─┴───┐  ┌──▼──────┐
    │ DB    │  │ Services      │  │ Thread  │
    │ Layer │  │ (Ingestion,   │  │ Pool    │
    │       │  │  Heuristics)  │  │         │
    └───────┘  └────────────────┘  └─────────┘
```

---

## Tab Modularization

### Base Tab Architecture

All tabs inherit from `BaseTab`, which provides common functionality:

```python
class BaseTab(QtWidgets.QWidget):
    """Base class for all tab implementations."""

    def __init__(self, context: TabContext) -> None:
        super().__init__()
        self.context = context
        self.colors = context.colors

    def _start_task(
        self,
        task_func: Callable,
        *args,
        on_progress: Callable[[int, str], None] | None = None,
        on_result: Callable[[object], None] | None = None,
    ) -> None:
        """Start a background task using the thread pool."""
        # Implementation delegates to context.start_task
```

### Tab Responsibilities

Each tab owns:
- **UI Construction** (`_build_ui()`)
- **Event Handlers** (Button clicks, selections)
- **Background Tasks** (Long operations)
- **State Management** (Cancellation flags, edit tracking)
- **UI Updates** (Progress display, results display)

Each tab delegates to:
- **Service Layer** (Database, ingestion, processing)
- **Thread Management** (Qt thread pool)
- **Error Reporting** (Centralized error callbacks)

### Tab Registry

```
RAGTab          - File/URL ingestion into knowledge base
SDSTab          - SDS document processing and matrix generation
AutomationTab   - Harvesting, scheduling, SDS generation
ReviewTab       - Edit-and-review workflow for extracted data
RecordsTab      - Database records browsing
BackupTab       - Backup and restoration
StatusTab       - Application status and statistics
ChatTab         - LLM chat interface
RegexLabTab     - Regex pattern testing and extraction
```

---

## TabContext Dependency Injection

### Pattern: Service Locator via Constructor

Instead of creating services internally, tabs receive them through TabContext:

```python
@dataclass
class TabContext:
    """Shared context provided to all tabs."""
    db: DatabaseLayer                    # Database access
    ingestion: IngestionService          # RAG indexing
    ollama: OllamaService                # LLM operations
    profile_router: ProfileRouter        # Manufacturer profiling
    heuristics: FieldExtractor           # Data extraction
    sds_extractor: SDSExtractor          # SDS processing
    colors: dict[str, str]               # Theme colors
    app_settings: ApplicationSettings    # App configuration
    thread_pool: QtCore.QThreadPool      # Background execution
    set_status: Callable[[str], None]    # Global status updates
    on_error: Callable[[str], None]      # Global error handling
    start_task: Callable[...]            # Task execution helper
```

### Benefits

✅ **Testability**: Mock services in tests
✅ **Flexibility**: Swap implementations without changing tabs
✅ **Consistency**: All tabs use same service instances
✅ **Decoupling**: Tabs don't import service modules directly

### Usage Pattern

```python
class RAGTab(BaseTab):
    def _ingest_files_task(self, files: Iterable[Path], *, signals=None):
        # Access services through context
        result = self.context.ingestion.ingest_local_files(files)
        return result
```

---

## Signal-Based Async Pattern

### Problem It Solves

Qt applications cannot block the UI thread. Long operations must:
1. Run in background threads
2. Safely communicate results back to UI thread
3. Provide real-time progress updates
4. Support cancellation

### Solution: Qt Signals

**Signals** (emitted from worker thread) → **Slots** (received on UI thread)

### Implementation

```python
class WorkerSignals(QtCore.QObject):
    """Signals emitted by background tasks."""
    progress = QtCore.Signal(int)              # 0-100%
    message = QtCore.Signal(str)               # Status message
    error = QtCore.Signal(str)                 # Error occurred
    finished = QtCore.Signal()                 # Task done
```

### Three-Part Pattern

**Part 1: Event Handler (UI Thread)**

```python
def _on_ingest_files(self) -> None:
    """Handle button click - validate and start task."""
    files, _ = QtWidgets.QFileDialog.getOpenFileNames(...)
    if not files:
        return

    # Setup UI
    self.progress_bar.setVisible(True)
    self.progress_bar.setValue(0)
    self._task_cancelled = False

    # Start background task
    self._start_task(
        self._ingest_files_task,
        [Path(f) for f in files],
        on_progress=self._on_progress,
        on_result=self._on_done,
    )
```

**Part 2: Background Task (Worker Thread)**

```python
def _ingest_files_task(
    self,
    files: Iterable[Path],
    *,
    signals: WorkerSignals | None = None,
) -> IngestionSummary:
    """Execute long operation - emit progress signals."""
    file_list = list(files)

    for idx, file_path in enumerate(file_list):
        # Check cancellation
        if self._task_cancelled:
            return IngestionSummary(documents=0, chunks=0)

        # Emit progress
        if signals:
            signals.progress.emit(int(100 * idx / len(file_list)))
            signals.message.emit(f"Processing {file_path.name}")

        # Do work
        self.context.ingestion.ingest_file(file_path)

    return IngestionSummary(...)
```

**Part 3: Completion Callback (UI Thread)**

```python
def _on_done(self, result: object) -> None:
    """Handle task completion - update UI."""
    # Cleanup
    self.progress_bar.setVisible(False)

    # Check cancellation
    if self._task_cancelled:
        self._set_status("Cancelled")
        return

    # Process result
    if isinstance(result, IngestionSummary):
        self._set_status(f"✓ Ingested {result.documents} documents")
        self._refresh_display()
```

### Flow Diagram

```
UI Thread                  Worker Thread
┌──────────────┐
│ _on_action() │─────────────┐
└──────────────┘             │
       │                      ▼
       │              ┌──────────────────┐
       │              │ _action_task()   │
       │              │ (long operation) │
       │              └──────────────────┘
       │                      │
       │         ┌────────────┴─────────────┐
       │         │                          │
       │   signals.progress.emit() ──────┐  │
       │                              │  │  │
       ▼─────────────────────────────┐  │  │
    _on_progress() ◄────────────────┘  │  │
       │                               │  │
       │         signals.finished.emit()  │
       │                              │  │
       ▼─────────────────────────────┐  │
    _on_done(result) ◄────────────────┘
```

---

## Styling System

### Color Theme Architecture

Colors are centralized in TabContext and accessed via `self.colors` dict:

```python
colors = {
    "text": "#ffffff",           # Foreground text
    "bg": "#000000",             # Background
    "surface": "#1a1a1a",        # Card/panel background
    "input": "#2a2a2a",          # Input field background
    "primary": "#4a9eff",        # Primary action color
    "success": "#22c55e",        # Success indicator
    "warning": "#f9e2af",        # Warning indicator
    "error": "#f38ba8",          # Error indicator
}
```

### StyleSheet Pattern

```python
def _style_button(self, button: QtWidgets.QPushButton) -> None:
    """Apply consistent button styling."""
    button.setStyleSheet(f"""
        QPushButton {{
            background-color: {self.colors['primary']};
            color: {self.colors['text']};
            border: none;
            border-radius: 4px;
            padding: 6px 12px;
            font-weight: 500;
        }}
        QPushButton:hover {{
            background-color: {self.colors['primary_hover']};
        }}
        QPushButton:disabled {{
            opacity: 0.5;
        }}
    """)
```

### Styling Components

**Labels**: Text color + word wrap
**Tables**: Cell padding + alternating row colors
**Buttons**: Hover states + disabled states
**Progress Bars**: Color + value display
**Input Fields**: Background + border + focus

---

## Error Handling Architecture

### Three-Level Error Handling

**Level 1: Validation (Handler)**
```python
def _on_process(self) -> None:
    if not self.input_file.text().strip():
        self._set_status("Select a file", error=True)
        return  # Don't start task
```

**Level 2: Exception Handling (Task)**
```python
def _process_task(self, file, *, signals=None):
    try:
        return self._do_work(file)
    except FileNotFoundError as e:
        if signals:
            signals.error.emit(f"File not found: {e}")
        return {"success": False, "error": str(e)}
```

**Level 3: Result Checking (Callback)**
```python
def _on_done(self, result):
    if isinstance(result, dict) and result.get("success"):
        self._set_status("✓ Complete")
    else:
        error = result.get("error") if isinstance(result, dict) else str(result)
        self._set_status(f"✗ Failed: {error}", error=True)
```

### Error Flow

```
Input Error (Handler)
    ↓
    └─→ _set_status("Error", error=True)

Exception (Task)
    ↓
    ├─→ signals.error.emit(message)
    └─→ return {"success": False, "error": ...}
        ↓
Result Error (Callback)
    ↓
    └─→ _set_status("✗ Failed: ...", error=True)
```

---

## Integration Patterns

### Pattern 1: Ingest → Process → Display

Used by RAGTab:

```
User selects files
    ↓
Handler validates + shows progress
    ↓
Task: ingest_local_files() + emit signals
    ↓
Progress callback: update progress bar
    ↓
Completion: refresh table + update stats
```

### Pattern 2: Process → Export

Used by SDSTab:

```
User selects folder
    ↓
Handler: _on_process_sds()
    ↓
Task: process each SDS file (with cancellation)
    ↓
Intermediate: build matrix from results
    ↓
Export: to Excel/CSV
```

### Pattern 3: Search → Download → Process

Used by AutomationTab:

```
User provides CAS list
    ↓
Handler: validate + start harvest
    ↓
Task:
  - Phase 1 (50%): Search for SDS
  - Phase 2 (50%): Download files
    ↓
Optional: Process each SDS
    ↓
Completion: summarize results
```

### Pattern 4: Review → Edit → Save

Used by ReviewTab:

```
Load data into table
    ↓
User edits cells
    ↓
EditableTableModel tracks changes
    ↓
User confirms save
    ↓
Task: batch update database records
    ↓
Completion: refresh table
```

---

## Data Flow

### Example: RAGTab File Ingestion

```
1. USER ACTION
   └─→ Click "Ingest Files" button

2. HANDLER (_on_ingest_files)
   ├─→ Validate: get file paths
   ├─→ Setup UI: show progress bar, disable button
   ├─→ Reset flag: _task_cancelled = False
   └─→ Start task: _start_task(_ingest_files_task, files, ...)

3. BACKGROUND TASK (_ingest_files_task)
   ├─→ For each file:
   │   ├─→ Check: if _task_cancelled, return early
   │   ├─→ Emit: signals.progress.emit(percentage)
   │   ├─→ Emit: signals.message.emit(filename)
   │   └─→ Execute: self.context.ingestion.ingest_file(file)
   └─→ Return: IngestionSummary(documents, chunks)

4. PROGRESS CALLBACK (_on_ingest_progress)
   ├─→ Update progress bar: setVisible(True), setValue(percentage)
   ├─→ Update message: file_counter.setText(message)
   └─→ Update status: _set_status(message)

5. COMPLETION CALLBACK (_on_ingest_done)
   ├─→ Cleanup: hide progress bar, enable button
   ├─→ Check: if cancelled, show "Cancelled" message
   ├─→ Process: IngestionSummary → extract results
   ├─→ Update: log.append(result.to_message())
   └─→ Refresh: _refresh_sources_table(), _refresh_rag_stats()

6. UI UPDATED
   └─→ User sees completion status + refreshed data
```

---

## Design Decisions

### Decision 1: Modular Tabs over Monolithic Window

**Why**:
- Each feature area is independent
- Easy to test individual tabs
- Features can be added without affecting others
- Users can navigate between features easily

**Trade-off**:
- Requires careful dependency management (solved by TabContext)

### Decision 2: TabContext Injection over Service Imports

**Why**:
- Enables dependency injection for testing
- Services are configured once, used everywhere
- Easier to mock complex dependencies
- Clear interface between tabs and services

**Trade-off**:
- Requires passing context to all tabs

### Decision 3: Signal-Based Async over Callbacks

**Why**:
- Qt-native pattern, well-optimized
- Thread-safe by design
- Clear separation of concerns
- Built-in connection management

**Trade-off**:
- Requires understanding Qt signals
- More verbose than async/await (Python limitation in PyQt5/PySide6)

### Decision 4: EditableTableModel for Change Tracking

**Why**:
- Separates model logic from UI rendering
- Enables undo/discard functionality
- Batch operations more efficient than cell-by-cell saves
- User can review all changes before committing

**Trade-off**:
- More code than direct table updates
- Requires tracking original values

### Decision 5: Cancellation Flag over Thread Interruption

**Why**:
- Safe: allows cleanup before stopping
- Cooperative: task respects cancellation points
- Predictable: no deadlocks or resource leaks
- Debuggable: can see exactly when cancellation occurred

**Trade-off**:
- Task must check flag periodically
- Long operations without checks can't be cancelled

---

## Testing Architecture

### Testing Pyramid

```
        ▲
       /│\
      / │ \
     /  │  \       End-to-End Tests
    /   │   \      (Full app with UI)
   /────┼────\     ─────────────────
  /     │     \
 /  Integration\   Integration Tests
/       │       \  (Mocked services)
────────┼────────  ─────────────────
   │    │    │
Unit Tests    Unit Tests
(Isolated)    (Isolated)
─────────────────
```

### Mock Strategy

**Level 1: Service Mocks in TabContext**

```python
context = TabContext(
    db=MagicMock(),              # Mock database
    ingestion=MagicMock(),        # Mock ingestion service
    ollama=MagicMock(),           # Mock LLM
    # ... other services
)
```

**Level 2: Tab Instantiation with Mocks**

```python
tab = RAGTab(context)  # Tab created with mocked services
tab.url_input.setText("https://example.com")
tab._on_ingest_url()   # Call handler
```

**Level 3: Verification**

```python
assert context.start_task.called              # Task was started
assert tab.progress_bar.isVisible()           # UI was updated
```

### Test Coverage

- **Handler tests**: Verify validation and UI setup
- **Task tests**: Verify business logic and signal emission
- **Callback tests**: Verify UI updates and error handling
- **Integration tests**: Verify complete workflows
- **Cancellation tests**: Verify task can be cancelled
- **Error tests**: Verify error handling at all levels

---

## Summary

RAG SDS Matrix UI architecture achieves:

✅ **Modularity** - 9 independent tabs with minimal coupling
✅ **Consistency** - All tabs follow same patterns
✅ **Testability** - Easy to mock and test all components
✅ **Responsiveness** - No UI blocking via signal-based async
✅ **Maintainability** - Clear separation of concerns
✅ **Extensibility** - New tabs can be added using established patterns

The architecture enables rapid feature development while maintaining code quality and test coverage.

---

## See Also

- [Handler Implementation Guide](HANDLER_IMPLEMENTATION_GUIDE.md)
- [User Guide](USER_GUIDE.md)
- [Project Completion Report](PROJECT_COMPLETION_REPORT.md)
