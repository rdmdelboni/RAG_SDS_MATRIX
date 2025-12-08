# Handler Implementation Guide
## Building Event Handlers for RAG SDS Matrix UI Tabs

**Last Updated:** December 4, 2025
**Target Audience:** UI Developers, Contributors
**Difficulty Level:** Intermediate

---

## Table of Contents
1. [Overview](#overview)
2. [Handler Pattern](#handler-pattern)
3. [Implementation Walkthrough](#implementation-walkthrough)
4. [Progress Tracking](#progress-tracking)
5. [Cancellation Support](#cancellation-support)
6. [Error Handling](#error-handling)
7. [Best Practices](#best-practices)
8. [Common Patterns](#common-patterns)
9. [Testing Handlers](#testing-handlers)

---

## Overview

Handlers in RAG SDS Matrix follow a **signal-based async pattern** using Qt's thread pool. This guide teaches you how to implement handlers that:
- Execute long-running operations in background threads
- Update UI with real-time progress
- Support task cancellation
- Handle errors gracefully
- Maintain responsive user interface

### Handler Architecture

```
User Action (Button Click)
    ↓
Handler Method (_on_action)
    ├─ Validation
    ├─ UI Setup (disable buttons, show progress)
    └─ Start Background Task
        ↓
    Background Task Method (_action_task)
    ├─ Execute operation
    ├─ Emit signals (progress, message)
    └─ Return result
        ↓
    Completion Callback (_on_action_done)
    ├─ Update UI
    ├─ Refresh data
    └─ Clean up
```

---

## Handler Pattern

### 1. Handler Method (UI Thread)

**Purpose:** Validate input and initiate background task

**Signature:**
```python
def _on_action(self) -> None:
    """Handle action triggered by user."""
    # Validation
    # UI Setup
    # Start task
```

**Responsibilities:**
- ✓ Validate user input
- ✓ Show progress indicators
- ✓ Enable/disable buttons
- ✓ Call `_start_task()`

**Example:**
```python
def _on_ingest_files(self) -> None:
    """Handle file ingestion."""
    files, _ = QtWidgets.QFileDialog.getOpenFileNames(...)
    if files:
        # Validation passed
        self._set_status(f"Ingesting {len(files)} files…")
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.cancel_btn.setEnabled(True)
        self._task_cancelled = False

        # Start background task
        self._start_task(
            self._ingest_files_task,
            [Path(f) for f in files],
            on_progress=self._on_progress,
            on_result=self._on_done,
        )
```

### 2. Background Task Method (Worker Thread)

**Purpose:** Execute long-running operation and emit signals

**Signature:**
```python
def _action_task(
    self,
    param1: Type1,
    param2: Type2,
    *,
    signals: WorkerSignals | None = None,
) -> ResultType:
    """Execute action in background."""
    # Check cancellation
    # Emit progress signals
    # Execute operation
    # Return result
```

**Responsibilities:**
- ✓ Check cancellation flag periodically
- ✓ Emit progress signals
- ✓ Emit status messages
- ✓ Handle exceptions
- ✓ Return structured result

**Example:**
```python
def _ingest_files_task(
    self,
    files: Iterable[Path],
    *,
    signals: WorkerSignals | None = None,
) -> IngestionSummary:
    """Ingest files into RAG system."""
    file_list = list(files)
    total = len(file_list)

    # Check cancellation at key points
    for idx, file_path in enumerate(file_list):
        if self._task_cancelled:
            return IngestionSummary(
                documents=0,
                chunks=0,
                message="Ingestion cancelled"
            )

        # Emit progress
        if signals:
            progress = int(100 * idx / total) if total > 0 else 0
            signals.progress.emit(progress)
            signals.message.emit(f"Processing {file_path.name}…")

    # Check before actual operation
    if self._task_cancelled:
        return IngestionSummary(documents=0, chunks=0)

    # Execute operation
    summary = self.context.ingestion.ingest_local_files(file_list)

    # Emit completion
    if signals:
        signals.progress.emit(100)
        signals.message.emit(summary.to_message())

    return summary
```

### 3. Progress Callback (UI Thread)

**Purpose:** Update UI with progress updates

**Signature:**
```python
def _on_progress(self, progress: int, message: str) -> None:
    """Handle progress updates."""
    # Update progress bar
    # Update status label
    # Update main status
```

**Responsibilities:**
- ✓ Update progress bar value
- ✓ Update progress label
- ✓ Update status messages

**Example:**
```python
def _on_ingest_progress(self, progress: int, message: str) -> None:
    """Handle ingestion progress updates."""
    self.progress_bar.setValue(progress)
    self.file_counter.setText(message)
    self._set_status(message)
```

### 4. Completion Callback (UI Thread)

**Purpose:** Handle task completion and update UI

**Signature:**
```python
def _on_action_done(self, result: object) -> None:
    """Handle action completion."""
    # Hide progress
    # Check for cancellation
    # Process result
    # Update UI
```

**Responsibilities:**
- ✓ Hide progress indicators
- ✓ Disable cancel button
- ✓ Check cancellation status
- ✓ Process results
- ✓ Refresh data

**Example:**
```python
def _on_ingest_done(self, result: object) -> None:
    """Handle ingestion completion."""
    self.progress_bar.setVisible(False)
    self.cancel_btn.setEnabled(False)

    # Check if cancelled
    if self._task_cancelled:
        self._set_status("Ingestion cancelled")
        return

    # Process result
    if isinstance(result, IngestionSummary):
        self.log.append(result.to_message())

    # Refresh data
    self._refresh_sources_table()
    self._refresh_rag_stats()
```

---

## Implementation Walkthrough

### Step 1: Create Handler Method

```python
def _on_process_data(self) -> None:
    """Handle process data button click."""
    # Get input from UI
    input_file = self.input_path.text().strip()

    # Validate
    if not input_file:
        self._set_status("Select an input file", error=True)
        return

    if not Path(input_file).exists():
        self._set_status("File not found", error=True)
        return

    # Setup UI
    self._set_status("Processing…")
    self.progress_bar.setVisible(True)
    self.progress_bar.setValue(0)
    self.cancel_btn.setEnabled(True)
    self._task_cancelled = False

    # Start task
    self._start_task(
        self._process_task,
        Path(input_file),
        on_progress=self._on_process_progress,
        on_result=self._on_process_done,
    )
```

### Step 2: Create Task Method

```python
def _process_task(
    self,
    input_file: Path,
    *,
    signals: WorkerSignals | None = None,
) -> dict:
    """Process file in background."""
    try:
        # Check cancellation
        if self._task_cancelled:
            return {"success": False, "error": "Cancelled"}

        # Emit start message
        if signals:
            signals.message.emit("Starting processing…")
            signals.progress.emit(25)

        # Do work
        with open(input_file, 'r') as f:
            data = json.load(f)

        # Check cancellation again
        if self._task_cancelled:
            return {"success": False, "error": "Cancelled"}

        if signals:
            signals.progress.emit(50)
            signals.message.emit("Processing data…")

        # Process
        result = self._process_data(data)

        # Check cancellation before final step
        if self._task_cancelled:
            return {"success": False, "error": "Cancelled"}

        # Final update
        if signals:
            signals.progress.emit(100)
            signals.message.emit("Processing complete")

        return {"success": True, "result": result}

    except Exception as e:
        if signals:
            signals.error.emit(str(e))
        return {"success": False, "error": str(e)}
```

### Step 3: Create Progress Callback

```python
def _on_process_progress(self, progress: int, message: str) -> None:
    """Handle process progress updates."""
    self.progress_bar.setValue(progress)
    self.progress_label.setText(message)
    self._set_status(message)
```

### Step 4: Create Completion Callback

```python
def _on_process_done(self, result: object) -> None:
    """Handle process completion."""
    # Cleanup UI
    self.progress_bar.setVisible(False)
    self.cancel_btn.setEnabled(False)

    # Check cancellation
    if self._task_cancelled:
        self._set_status("Processing cancelled")
        return

    # Check result
    if isinstance(result, dict) and result.get("success"):
        self._set_status("✓ Processing complete")
        # Use result
        data = result.get("result")
        self._display_result(data)
    else:
        error = result.get("error") if isinstance(result, dict) else str(result)
        self._set_status(f"Processing failed: {error}", error=True)
```

---

## Progress Tracking

### Basic Progress Pattern

```python
# In task method
total_items = len(items_to_process)

for idx, item in enumerate(items_to_process):
    # Calculate progress as percentage
    progress_pct = int(100 * idx / total_items) if total_items > 0 else 0

    if signals:
        signals.progress.emit(progress_pct)
        signals.message.emit(f"Processing item {idx + 1}/{total_items}")

    # Do work on item
    process_item(item)
```

### Two-Phase Progress (Search + Process)

```python
# Phase 1: Search (0-50%)
for idx, cas in enumerate(cas_numbers, 1):
    if signals:
        signals.progress.emit(int(50 * idx / len(cas_numbers)))
        signals.message.emit(f"Searching {cas}…")

    results = search(cas)

# Phase 2: Process (50-100%)
for idx, item in enumerate(downloaded_items, 1):
    if signals:
        signals.progress.emit(50 + int(50 * idx / len(downloaded_items)))
        signals.message.emit(f"Processing {item}…")

    process(item)
```

---

## Cancellation Support

### Add Cancellation Flag

```python
def __init__(self, context: TabContext) -> None:
    super().__init__(context)
    self._task_cancelled = False  # Add this
    self._build_ui()
```

### Reset Flag at Start

```python
def _on_action(self) -> None:
    # ... validation ...
    self._task_cancelled = False  # Reset before task
    self._start_task(...)
```

### Check Flag in Task

```python
def _action_task(self, ..., *, signals: WorkerSignals | None = None) -> dict:
    # Check at entry
    if self._task_cancelled:
        return {"success": False, "error": "Cancelled"}

    # Check at loops
    for item in items:
        if self._task_cancelled:
            return {"success": False, "error": "Cancelled"}
        # Process item

    # Check before final operation
    if self._task_cancelled:
        return {"success": False, "error": "Cancelled"}

    # Final operation
    return result
```

### Add Cancel Button Handler

```python
def _on_cancel_action(self) -> None:
    """Handle action cancellation."""
    self._task_cancelled = True
    self.cancel_btn.setEnabled(False)
    self._set_status("Cancelling…")
```

---

## Error Handling

### Try-Except Pattern in Tasks

```python
def _action_task(self, ..., *, signals: WorkerSignals | None = None) -> dict:
    """Execute action with error handling."""
    try:
        # Main operation
        result = self._do_work()

        # Emit success
        if signals:
            signals.message.emit("Complete")

        return {"success": True, "data": result}

    except FileNotFoundError as e:
        if signals:
            signals.error.emit(f"File not found: {e}")
        return {"success": False, "error": str(e)}

    except ValueError as e:
        if signals:
            signals.error.emit(f"Invalid data: {e}")
        return {"success": False, "error": str(e)}

    except Exception as e:
        if signals:
            signals.error.emit(f"Unexpected error: {e}")
        return {"success": False, "error": str(e)}
```

### Handle in Completion

```python
def _on_action_done(self, result: object) -> None:
    """Handle completion with error checking."""
    if isinstance(result, dict):
        if result.get("success"):
            self._set_status("✓ Success")
            self._use_result(result)
        else:
            error = result.get("error", "Unknown error")
            self._set_status(f"Failed: {error}", error=True)
    else:
        self._set_status("Unexpected result type", error=True)
```

---

## Best Practices

### ✅ DO

- **Validate early:** Check inputs in handler before starting task
- **Emit signals frequently:** Update UI at least every 1-2 seconds
- **Check cancellation:** At loop entry and before expensive operations
- **Handle exceptions:** Try-except with specific error types
- **Clean up UI:** Always hide progress bar and disable buttons on completion
- **Return structured data:** Use dicts with `success` flag
- **Document parameters:** Type hints on all method parameters
- **Test handlers:** Write integration tests for each handler

### ❌ DON'T

- **Block UI thread:** Never do long operations in handler methods
- **Ignore signals:** Always pass signals to emit progress
- **Forget cancellation:** Always check `_task_cancelled` flag
- **Bare exceptions:** Catch specific exception types
- **Leave UI dirty:** Always clean up buttons/progress on exit
- **Return raw data:** Always wrap results in structured format
- **Skip validation:** Always validate before starting task
- **Hardcode magic numbers:** Use constants or parameters

---

## Common Patterns

### Pattern 1: File Processing

```python
def _on_process_files(self) -> None:
    files = self._get_selected_files()
    if files:
        self._start_task(
            self._process_files_task,
            files,
            on_progress=self._on_progress,
            on_result=self._on_done,
        )

def _process_files_task(self, files, *, signals=None):
    results = []
    for idx, file in enumerate(files):
        if self._task_cancelled:
            return {"success": False, "error": "Cancelled"}

        try:
            result = process_file(file)
            results.append(result)

            if signals:
                signals.progress.emit(int(100 * idx / len(files)))
                signals.message.emit(f"Processed {file.name}")
        except Exception as e:
            if signals:
                signals.message.emit(f"Failed: {e}")

    return {"success": True, "results": results}
```

### Pattern 2: Iterative Harvesting

```python
def _harvest_task(self, cas_numbers, *, signals=None):
    downloaded = []
    total = len(cas_numbers)

    for idx, cas in enumerate(cas_numbers, 1):
        if self._task_cancelled:
            break

        if signals:
            signals.progress.emit(int(100 * idx / total))
            signals.message.emit(f"Searching {cas}…")

        # Search
        results = harvester.search(cas)

        # Download
        for result in results:
            if self._task_cancelled:
                break

            path = harvester.download(result)
            if path:
                downloaded.append(path)

    return {
        "success": True,
        "downloaded": len(downloaded),
        "files": downloaded
    }
```

### Pattern 3: Batch Database Updates

```python
def _save_changes_task(self, changes, *, signals=None):
    updated = 0

    for idx, (record_id, updates) in enumerate(changes.items(), 1):
        if self._task_cancelled:
            break

        try:
            self.db.update(record_id, updates)
            updated += 1

            if signals:
                signals.progress.emit(int(100 * idx / len(changes)))
                signals.message.emit(
                    f"Updated {updated}/{len(changes)}"
                )
        except Exception as e:
            if signals:
                signals.message.emit(f"Failed {record_id}: {e}")

    return {
        "success": updated > 0,
        "updated": updated,
        "total": len(changes)
    }
```

---

## Testing Handlers

### Basic Handler Test

```python
def test_handler_with_mocks():
    # Setup
    context = create_mock_context()
    tab = RAGTab(context)

    # Trigger handler
    tab.url_input.setText("https://example.com")
    tab._on_ingest_url()

    # Verify
    assert context.start_task.called
    assert tab.progress_bar.isVisible()

def test_task_execution():
    # Setup
    context = create_mock_context()
    tab = RAGTab(context)

    # Execute task
    result = tab._ingest_files_task([Path(__file__)])

    # Verify
    assert hasattr(result, "to_message")
    assert result.documents >= 0

def test_cancellation():
    # Setup
    context = create_mock_context()
    tab = RAGTab(context)

    # Start and cancel
    tab._task_cancelled = True
    result = tab._ingest_files_task([Path(__file__)])

    # Verify cancellation
    assert result.documents == 0
```

---

## Summary

Handlers in RAG SDS Matrix follow a consistent pattern:
1. **Validate** inputs in handler method
2. **Setup** UI and start background task
3. **Execute** long operation with progress signals
4. **Callback** with completion and result handling
5. **Cleanup** UI state

This pattern ensures:
- ✅ Responsive UI (no blocking)
- ✅ Real-time feedback (progress signals)
- ✅ Graceful cancellation (flag checking)
- ✅ Error recovery (exception handling)
- ✅ Clean code (separation of concerns)

---

## See Also

- [Architecture Patterns Documentation](ARCHITECTURE_PATTERNS.md)
- [UI User Guide](USER_GUIDE.md)
- [Integration Test Guide](test_integration_complete.py)
