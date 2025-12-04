"""PySide6-based UI for RAG SDS Matrix.

This replaces the previous CustomTkinter UI with a Qt implementation. It keeps
core workflows (knowledge ingestion, SDS processing, matrix export/build, basic
status views) while relying on the existing backend services.
"""

from __future__ import annotations

import subprocess
import traceback
import sys
import json
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterable

from PySide6 import QtCore, QtGui, QtWidgets

from ..config import get_settings, get_text
from ..config.constants import SUPPORTED_FORMATS
from ..config.i18n import set_language
from ..database import get_db_manager
from ..matrix.builder import MatrixBuilder
from ..matrix.exporter import MatrixExporter
from ..models import get_ollama_client
from ..rag.ingestion_service import IngestionSummary, KnowledgeIngestionService
from ..sds.processor import SDSProcessor
from ..sds.heuristics import HeuristicExtractor
from ..sds.extractor import SDSExtractor
from ..sds.profile_router import ProfileRouter
from ..sds.regex_catalog import get_regex_catalog
from ..utils.logger import get_logger
from .theme import get_colors
from .tabs import TabContext, BaseTab
from .tabs.backup_tab import BackupTab
from .tabs.records_tab import RecordsTab
from .tabs.review_tab import ReviewTab
from .tabs.status_tab import StatusTab
from .tabs.chat_tab import ChatTab
from .tabs.regex_lab_tab import RegexLabTab
from .tabs.automation_tab import AutomationTab
from .tabs.rag_tab import RAGTab
from .tabs.sds_tab import SDSTab

logger = get_logger(__name__)


class WorkerSignals(QtCore.QObject):
    """Signals shared by background workers."""

    finished = QtCore.Signal(object)
    error = QtCore.Signal(str)
    message = QtCore.Signal(str)
    progress = QtCore.Signal(int, str)  # percent, label
    file_result = QtCore.Signal(str, str, str, int)  # filename, chemical, status, row_idx


class TaskRunner(QtCore.QRunnable):
    """Generic QRunnable wrapper to execute callables in a thread pool."""

    def __init__(self, fn: Callable, *args, **kwargs) -> None:
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

    @QtCore.Slot()
    def run(self) -> None:  # pragma: no cover - Qt thread dispatch
        try:
            result = self.fn(*self.args, signals=self.signals, **self.kwargs)
            self.signals.finished.emit(result)
        except Exception as exc:  # pragma: no cover - runtime safety
            logger.error("Worker error: %s", exc)
            logger.debug(traceback.format_exc())
            self.signals.error.emit(str(exc))
            self.signals.finished.emit(None)


class MainWindow(QtWidgets.QMainWindow):
    """Main Qt window."""

    def __init__(self) -> None:
        super().__init__()

        self.settings = get_settings()
        self.project_root = Path(__file__).resolve().parent.parent
        theme_pref = (self.settings.ui.theme or "system").lower()
        if theme_pref == "system":
            theme_pref = "dark" if self._system_prefers_dark() else "light"
        self.colors = get_colors(theme_pref)
        self.db = get_db_manager()
        self.ingestion = KnowledgeIngestionService()
        self.ollama = get_ollama_client()
        self.profile_router = ProfileRouter()
        self.heuristics = HeuristicExtractor()
        self.sds_extractor = SDSExtractor()
        self.thread_pool = QtCore.QThreadPool.globalInstance()
        self._workers: list[TaskRunner] = []
        self._cancel_processing = False

        # Initialize QSettings for persistent storage
        self.app_settings = QtCore.QSettings("RAG_SDS_MATRIX", "RAG_SDS_MATRIX")

        set_language(self.settings.ui.language or "pt")

        self.setWindowTitle(get_text("app.title"))
        self.resize(self.settings.ui.window_width, self.settings.ui.window_height)
        self.setMinimumSize(self.settings.ui.min_width, self.settings.ui.min_height)

        palette = self.palette()
        palette.setColor(QtGui.QPalette.Window, QtGui.QColor(self.colors["bg"]))
        palette.setColor(QtGui.QPalette.WindowText, QtGui.QColor(self.colors["text"]))
        palette.setColor(QtGui.QPalette.Button, QtGui.QColor(self.colors["surface"]))
        palette.setColor(QtGui.QPalette.ButtonText, QtGui.QColor(self.colors["text"]))
        palette.setColor(QtGui.QPalette.Text, QtGui.QColor(self.colors["text"]))
        palette.setColor(QtGui.QPalette.Base, QtGui.QColor(self.colors["input"]))
        palette.setColor(QtGui.QPalette.AlternateBase, QtGui.QColor(self.colors["overlay"]))
        palette.setColor(QtGui.QPalette.ToolTipBase, QtGui.QColor(self.colors["surface"]))
        palette.setColor(QtGui.QPalette.ToolTipText, QtGui.QColor(self.colors["text"]))
        palette.setColor(QtGui.QPalette.Link, QtGui.QColor(self.colors["primary"]))
        palette.setColor(QtGui.QPalette.LinkVisited, QtGui.QColor(self.colors["accent"]))
        palette.setColor(QtGui.QPalette.Highlight, QtGui.QColor(self.colors["accent"]))
        palette.setColor(QtGui.QPalette.HighlightedText, QtGui.QColor(self.colors["bg"]))
        self.setPalette(palette)

        self._selected_sds_folder: Path | None = None

        self._build_ui()
        self._load_last_sds_folder()  # Load last used folder
        self._refresh_rag_stats()
        self._refresh_sources_table()
        self._refresh_db_stats()
        self._on_refresh_records()
        self._on_refresh_review()

    # === UI construction ===

    def _build_ui(self) -> None:
        central = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(central)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        header_row = QtWidgets.QHBoxLayout()
        header_row.setSpacing(6)

        header = QtWidgets.QLabel(get_text("app.title"))
        header.setStyleSheet(
            f"color: {self.colors['text']}; font-size: 18px; font-weight: 700;"
        )
        header_row.addWidget(header)
        header_row.addStretch()

        close_btn = QtWidgets.QPushButton("×")
        close_btn.setFixedSize(24, 24)
        close_btn.setToolTip("Exit application")
        close_btn.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        close_btn.setStyleSheet(
            f"QPushButton {{"
            f"background-color: {self.colors.get('error', '#f38ba8')};"
            f"border: none;"
            f"border-radius: 4px;"
            f"color: {self.colors['bg']};"
            f"font-weight: 700;"
            f"font-size: 14px;"
            f"padding: 0px;"
            f"}}"
            f"QPushButton:hover {{"
            f"background-color: {self.colors.get('warning', '#f9e2af')};"
            f"}}"
            f"QPushButton:pressed {{"
            f"background-color: {self.colors.get('error', '#f38ba8')};"
            f"}}"
        )
        close_btn.clicked.connect(self.close)
        header_row.addWidget(close_btn)

        layout.addLayout(header_row)

        self.tabs = QtWidgets.QTabWidget()
        layout.addWidget(self.tabs)

        # Create TabContext for passing shared services to all tabs
        tab_context = TabContext(
            db=self.db,
            ingestion=self.ingestion,
            ollama=self.ollama,
            profile_router=self.profile_router,
            heuristics=self.heuristics,
            sds_extractor=self.sds_extractor,
            colors=self.colors,
            app_settings=self.app_settings,
            thread_pool=self.thread_pool,
            set_status=self._set_status,
            on_error=self._on_error,
            start_task=self._start_task,
        )

        # Instantiate all tabs with TabContext
        self.rag_tab = RAGTab(tab_context)
        self.sds_tab = SDSTab(tab_context)
        self.records_tab = RecordsTab(tab_context)
        self.review_tab = ReviewTab(tab_context)
        self.backup_tab = BackupTab(tab_context)
        self.status_tab = StatusTab(tab_context)
        self.chat_tab = ChatTab(tab_context)
        self.automation_tab = AutomationTab(tab_context)
        self.regex_lab_tab = RegexLabTab(tab_context)

        # Add tabs to tab widget
        self.tabs.addTab(self.rag_tab, "RAG")
        self.tabs.addTab(self.sds_tab, "SDS")
        self.tabs.addTab(self.records_tab, "Records")
        self.tabs.addTab(self.review_tab, "Review")
        self.tabs.addTab(self.backup_tab, "Backup")
        self.tabs.addTab(self.status_tab, "Status")
        self.tabs.addTab(self.chat_tab, "Chat")
        self.tabs.addTab(self.automation_tab, "Automation")
        self.tabs.addTab(self.regex_lab_tab, "Regex Lab")

        self.status_bar = self.statusBar()
        self.status_label = QtWidgets.QLabel(get_text("app.ready"))
        self.status_bar.addWidget(self.status_label)

        self.setCentralWidget(central)


    # === Styling ===

    def _style_label(self, label: QtWidgets.QLabel, bold: bool = False, color: str | None = None) -> None:
        """Apply consistent styling to a label."""
        c = color or self.colors["text"]
        weight = "font-weight: 700;" if bold else ""
        label.setStyleSheet(f"color: {c}; {weight}")

    def _style_button(self, button: QtWidgets.QPushButton) -> None:
        """Apply consistent styling to a button."""
        button.setStyleSheet(
            f"QPushButton {{"
            f"background-color: {self.colors['primary']};"
            f"border: none;"
            f"border-radius: 4px;"
            f"color: {self.colors['text']};"
            f"padding: 6px 12px;"
            f"font-weight: 500;"
            f"}}"
            f"QPushButton:hover {{"
            f"background-color: {self.colors.get('primary_hover', self.colors['button_hover'])};"
            f"}}"
            f"QPushButton:pressed {{"
            f"background-color: {self.colors['primary']};"
            f"}}"
        )

    def _style_checkbox_symbols(
        self,
        checkbox: QtWidgets.QCheckBox,
        label: str = "",
        *,
        font_size: int = 14,
        spacing: int = 6,
    ) -> None:
        """Render a checkbox as colored ✓/✗ text instead of the default indicator."""
        checked_color = self.colors.get("success", "#22c55e")
        unchecked_color = self.colors.get("subtext", "#9ca3af")

        def apply(state: int) -> None:
            is_checked = state == QtCore.Qt.CheckState.Checked.value
            symbol = "✓" if is_checked else "✗"
            color = checked_color if is_checked else unchecked_color
            text = f"{symbol} {label}".strip()
            checkbox.setText(text)
            checkbox.setStyleSheet(
                "QCheckBox {"
                f"color: {color};"
                "font-weight: 600;"
                f"font-size: {font_size}px;"
                f"spacing: {spacing}px;"
                "}"
                "QCheckBox::indicator {"
                "width: 0px;"
                "height: 0px;"
                "}"
            )

        checkbox._symbolic_update = apply  # type: ignore[attr-defined]
        checkbox.stateChanged.connect(apply)
        apply(checkbox.checkState().value)

    def _refresh_checkbox_symbols(self, checkbox: QtWidgets.QCheckBox) -> None:
        """Re-apply the symbolic checkbox styling after programmatic state changes."""
        updater = getattr(checkbox, "_symbolic_update", None)
        if callable(updater):
            updater(checkbox.checkState().value)

    def _style_table(self, table: QtWidgets.QTableWidget) -> None:
        """Apply consistent styling to a table."""
        table.setStyleSheet(
            f"QTableWidget {{"
            f"background-color: {self.colors['input']};"
            f"color: {self.colors['text']};"
            f"gridline-color: {self.colors['overlay']};"
            f"}}"
            f"QHeaderView::section {{"
            f"background-color: {self.colors['surface']};"
            f"color: {self.colors['text']};"
            f"padding: 4px;"
            f"border: none;"
            f"}}"
            f"QTableWidget::item:selected {{"
            f"background-color: {self.colors['accent']};"
            f"color: {self.colors['bg']};"
            f"}}"
            f"QScrollBar:vertical {{"
            f"background-color: {self.colors['input']};"
            f"width: 12px;"
            f"margin: 0px;"
            f"}}"
            f"QScrollBar::handle:vertical {{"
            f"background-color: {self.colors['overlay']};"
            f"border-radius: 6px;"
            f"min-height: 20px;"
            f"}}"
            f"QScrollBar::handle:vertical:hover {{"
            f"background-color: {self.colors['subtext']};"
            f"}}"
            f"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{"
            f"border: none;"
            f"background: none;"
            f"}}"
            f"QScrollBar:horizontal {{"
            f"background-color: {self.colors['input']};"
            f"height: 12px;"
            f"margin: 0px;"
            f"}}"
            f"QScrollBar::handle:horizontal {{"
            f"background-color: {self.colors['overlay']};"
            f"border-radius: 6px;"
            f"min-width: 20px;"
            f"}}"
            f"QScrollBar::handle:horizontal:hover {{"
            f"background-color: {self.colors['subtext']};"
            f"}}"
            f"QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{"
            f"border: none;"
            f"background: none;"
            f"}}"
        )
        table.verticalHeader().setStyleSheet(
            f"QHeaderView {{"
            f"background-color: {self.colors['surface']};"
            f"color: {self.colors['text']};"
            f"}}"
        )
        # Style the corner button (top-left select all button)
        corner_btn = table.findChild(QtWidgets.QAbstractButton)
        if corner_btn:
            corner_btn.setStyleSheet(
                f"QAbstractButton {{"
                f"background-color: {self.colors['primary']};"
                f"}}"
            )

    def _reset_sds_progress(self) -> None:
        """Reset SDS progress UI elements to their idle state."""
        if hasattr(self, "sds_progress"):
            self.sds_progress.setValue(0)
        if hasattr(self, "sds_file_counter"):
            self.sds_file_counter.setText("")

    def _style_textedit(self, textedit: QtWidgets.QTextEdit) -> None:
        """Apply consistent styling to a text edit."""
        textedit.setStyleSheet(
            f"QTextEdit {{"
            f"background-color: {self.colors['input']};"
            f"color: {self.colors['text']};"
            f"border: 1px solid {self.colors['overlay']};"
            f"border-radius: 4px;"
            f"padding: 4px;"
            f"}}"
        )

    # === Helpers ===

    def _set_status(self, message: str, *, error: bool = False) -> None:
        color = self.colors.get("error" if error else "text", "#ffffff")
        self.status_label.setStyleSheet(f"color: {color};")
        self.status_label.setText(message)
        log_fn = logger.error if error else logger.info
        log_fn(message)

    def _on_error(self, message: str) -> None:
        """Handle error callback from tabs (via TabContext)."""
        self._set_status(message, error=True)

    def _system_prefers_dark(self) -> bool:
        """Heuristic to follow OS theme based on palette brightness."""
        try:
            palette = QtWidgets.QApplication.instance().palette()
            window_color = palette.color(QtGui.QPalette.Window)
            # lightness: 0 (dark) .. 255 (light)
            return window_color.lightness() < 128
        except Exception:
            return False

    def _start_task(self, fn: Callable, *args, on_result: Callable | None = None, on_progress: Callable | None = None) -> None:
        worker = TaskRunner(fn, *args)
        self._workers.append(worker)

        worker.signals.message.connect(self._set_status)
        worker.signals.error.connect(lambda msg, w=worker: self._on_worker_error(msg, w))
        
        # Connect progress signal if handler provided
        if on_progress:
            worker.signals.progress.connect(on_progress)
        # Connect per-file result updates when handler is present
        if hasattr(self, "_on_file_processed"):
            worker.signals.file_result.connect(self._on_file_processed)
        
        if on_result:
            worker.signals.finished.connect(lambda result, w=worker: self._on_worker_finished(w, on_result, result))
        else:
            worker.signals.finished.connect(lambda result, w=worker: self._on_worker_finished(w, None, result))

        self.thread_pool.start(worker)

    def _on_worker_error(self, message: str, worker: TaskRunner) -> None:
        self._set_status(message, error=True)
        self._cleanup_worker(worker)

    def _on_worker_finished(self, worker: TaskRunner, callback: Callable | None, result: object) -> None:
        if callback:
            try:
                callback(result)
            except RuntimeError as e:
                # Ignore signal deletion errors during cleanup
                if "deleted" not in str(e).lower():
                    raise
        self._cleanup_worker(worker)

    def _cleanup_worker(self, worker: TaskRunner) -> None:
        try:
            self._workers.remove(worker)
        except ValueError:
            pass
    
    def _on_stop_processing(self) -> None:
        """Stop SDS processing safely."""
        if not self._cancel_processing:
            reply = QtWidgets.QMessageBox.question(
                self,
                "Stop Processing",
                "Are you sure you want to stop processing? Current file will complete.",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.No
            )
            if reply == QtWidgets.QMessageBox.Yes:
                self._cancel_processing = True
                self.stop_btn.setEnabled(False)
                self._set_status("Stopping after current file...")

    # === RAG ingestion ===

    def _on_ingest_files(self) -> None:
        files, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self,
            "Select knowledge files",
            str(self.settings.paths.input_dir),
            "Supported files (" + " ".join(f"*{ext}" for ext in SUPPORTED_FORMATS) + ")",
        )
        if files:
            self._set_status(f"Ingesting {len(files)} files…")
            self._start_task(self._ingest_files_task, [Path(f) for f in files], on_result=self._on_ingest_done)

    def _on_ingest_folder(self) -> None:
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Select folder", str(self.settings.paths.input_dir))
        if not folder:
            return
        folder_path = Path(folder)
        files: list[Path] = []
        for suffix in SUPPORTED_FORMATS:
            files.extend(folder_path.rglob(f"*{suffix}"))
        if not files:
            QtWidgets.QMessageBox.information(self, "No files", "No supported files found.")
            return
        self._set_status(f"Ingesting {len(files)} files from folder…")
        self._start_task(self._ingest_files_task, files, on_result=self._on_ingest_done)

    def _on_ingest_url(self) -> None:
        url = self.url_input.text().strip()
        if not url:
            QtWidgets.QMessageBox.warning(self, "Missing URL", "Enter a URL to ingest.")
            return
        self._set_status(f"Fetching {url}…")
        self._start_task(self._ingest_url_task, url, on_result=self._on_ingest_done)

    def _ingest_files_task(self, files: Iterable[Path], *, signals: WorkerSignals | None = None) -> IngestionSummary:
        summary = self.ingestion.ingest_local_files(files)
        if signals:
            signals.message.emit(summary.to_message())
        return summary

    def _ingest_url_task(self, url: str, *, signals: WorkerSignals | None = None) -> IngestionSummary:
        summary = self.ingestion.ingest_url(url)
        if signals:
            signals.message.emit(summary.to_message())
        return summary

    def _on_ingest_done(self, result: object) -> None:
        if isinstance(result, IngestionSummary):
            self.rag_log.append(result.to_message())
        self._refresh_sources_table()
        self._refresh_rag_stats()

    def _refresh_rag_stats(self) -> None:
        stats = self.db.get_statistics()
        last_updated = stats.get("rag_last_updated") or "Never"
        text = f"Documents: {stats.get('rag_documents', 0)} | Chunks: {stats.get('rag_chunks', 0)} | Last updated: {last_updated}"
        self.rag_stats_label.setText(text)

    def _refresh_sources_table(self) -> None:
        try:
            sources = self.db.get_rag_documents()
        except Exception as exc:
            logger.error("Failed to load sources: %s", exc)
            self.sources_table.setRowCount(0)
            return

        rows = []
        for doc in sources[:200]:
            ts = doc.get("indexed_at")
            ts_str = ts.strftime("%Y-%m-%d %H:%M") if hasattr(ts, "strftime") else str(ts or "")
            rows.append(
                (
                    ts_str,
                    doc.get("title") or doc.get("source_path") or doc.get("source_url") or "",
                    doc.get("source_type") or "",
                    str(doc.get("chunk_count", 0)),
                )
            )

        self.sources_table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, value in enumerate(row):
                item = QtWidgets.QTableWidgetItem(value)
                self.sources_table.setItem(r, c, item)
        self.sources_table.resizeColumnsToContents()

    # === Records / Review ===

    def _on_refresh_records(self) -> None:
        limit = int(self.records_limit.value())
        self._set_status(f"Loading {limit} records…")
        self._start_task(self._records_task, limit, on_result=self._on_records_loaded)

    def _records_task(self, limit: int, *, signals: WorkerSignals | None = None) -> list[dict]:
        results = self.db.fetch_results(limit=limit)
        if signals:
            signals.message.emit(f"Loaded {len(results)} records")
        return results

    def _on_records_loaded(self, result: object) -> None:
        if not isinstance(result, list):
            return
        self._populate_table(
            self.records_table,
            result,
            columns=[
                ("filename", "File"),
                ("status", "Status"),
                ("product_name", "Product"),
                ("cas_number", "CAS"),
                ("hazard_class", "Hazard"),
                ("avg_confidence", "Confidence"),
                ("processed_at", "Processed"),
            ],
        )
        self.records_info.setText(f"Showing {len(result)} records")
        self._set_status("Records refreshed")

    def _on_refresh_review(self) -> None:
        limit = 100
        self._set_status("Refreshing review table…")
        self._start_task(self._records_task, limit, on_result=self._on_review_loaded)

    def _on_review_loaded(self, result: object) -> None:
        if not isinstance(result, list):
            return
        self._populate_table(
            self.review_table,
            result,
            columns=[
                ("filename", "File"),
                ("status", "Status"),
                ("product_name", "Product"),
                ("cas_number", "CAS"),
                ("un_number", "UN"),
                ("hazard_class", "Hazard"),
            ],
        )
        # Color NOT_FOUND entries in red
        self._colorize_not_found_in_review()
        self._set_status("Review table refreshed")
    # === Automation actions ===

    def _on_select_cas_file(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select CAS list", str(self.project_root))
        if path:
            self.cas_file_input.setText(path)

    def _on_select_harvest_output(self) -> None:
        path = QtWidgets.QFileDialog.getExistingDirectory(self, "Select output folder", str(self.project_root))
        if path:
            self.harvest_output_input.setText(path)

    def _on_select_packet_matrix(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select matrix file", str(self.project_root))
        if path:
            self.packet_matrix_input.setText(path)

    def _on_select_packet_sds_dir(self) -> None:
        path = QtWidgets.QFileDialog.getExistingDirectory(self, "Select SDS folder", str(self.project_root))
        if path:
            self.packet_sds_dir_input.setText(path)

    def _on_select_gen_data(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select JSON data", str(self.project_root))
        if path:
            self.gen_data_input.setText(path)

    def _on_select_gen_output(self) -> None:
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Select output PDF", str(self.project_root / "output/sds_stub.pdf"))
        if path:
            self.gen_out_input.setText(path)

    def _on_run_harvest_process(self) -> None:
        cas_file = self.cas_file_input.text().strip()
        output_dir = self.harvest_output_input.text().strip()
        if not cas_file or not Path(cas_file).exists():
            self._set_status("Select a valid CAS list file", error=True)
            return
        cmd = [
            sys.executable,
            str(self.project_root / "scripts/harvest_and_process.py"),
            "--cas-file",
            cas_file,
            "--output",
            output_dir,
            "--limit",
            str(self.harvest_limit.value()),
        ]
        if self.process_checkbox.isChecked():
            cmd.append("--process")
        if self.no_rag_checkbox.isChecked():
            cmd.append("--no-rag")
        self._run_async_command(cmd, "Harvest + process completed")

    def _on_run_scheduler(self) -> None:
        cas_file = self.cas_file_input.text().strip()
        output_dir = self.harvest_output_input.text().strip()
        if not cas_file or not Path(cas_file).exists():
            self._set_status("Select a valid CAS list file", error=True)
            return
        cmd = [
            sys.executable,
            str(self.project_root / "scripts/harvest_scheduler.py"),
            "--cas-file",
            cas_file,
            "--output",
            output_dir,
            "--interval",
            str(self.interval_spin.value()),
            "--limit",
            str(self.harvest_limit.value()),
            "--iterations",
            str(self.iterations_spin.value()),
        ]
        if self.process_checkbox.isChecked():
            cmd.append("--process")
        if self.no_rag_checkbox.isChecked():
            cmd.append("--no-rag")
        try:
            subprocess.Popen(cmd, cwd=str(self.project_root))
            self._set_status("Scheduler started in background")
        except Exception as exc:
            self._set_status(f"Failed to start scheduler: {exc}", error=True)

    def _on_export_packet(self) -> None:
        matrix = self.packet_matrix_input.text().strip()
        sds_dir = self.packet_sds_dir_input.text().strip()
        cas_raw = self.packet_cas_input.text().strip()
        if not matrix or not Path(matrix).exists():
            self._set_status("Select a valid matrix file", error=True)
            return
        if not sds_dir or not Path(sds_dir).exists():
            self._set_status("Select a valid SDS folder", error=True)
            return
        cas_list = [c.strip() for c in cas_raw.split(",") if c.strip()]
        if not cas_list:
            self._set_status("Enter at least one CAS number", error=True)
            return
        cmd = [
            sys.executable,
            str(self.project_root / "scripts/export_experiment_packet.py"),
            "--matrix",
            matrix,
            "--sds-dir",
            sds_dir,
            "--out",
            str(self.project_root / "packets"),
        ]
        cmd.extend(["--cas", *cas_list])
        self._run_async_command(cmd, "Experiment packet created")

    def _on_generate_sds_pdf(self) -> None:
        data_file = self.gen_data_input.text().strip()
        out_file = self.gen_out_input.text().strip()
        if not data_file or not Path(data_file).exists():
            self._set_status("Select a valid JSON data file", error=True)
            return
        cmd = [
            sys.executable,
            str(self.project_root / "scripts/generate_sds_stub.py"),
            "--data",
            data_file,
            "--out",
            out_file,
        ]
        self._run_async_command(cmd, "SDS PDF generated")

    def _run_async_command(self, cmd: list[str], success_message: str) -> None:
        """Run a CLI command off the UI thread."""

        def task(*, signals: WorkerSignals):
            proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(self.project_root))
            if proc.returncode != 0:
                raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "Command failed")
            signals.message.emit(proc.stdout.strip())
            return success_message

        worker = TaskRunner(task)
        worker.signals.finished.connect(lambda _: self._set_status(success_message))
        worker.signals.error.connect(lambda e: self._set_status(f"Error: {e}", error=True))
        worker.signals.message.connect(lambda m: self._set_status(m))
        self._workers.append(worker)
        self.thread_pool.start(worker)

    def _populate_table(self, table: QtWidgets.QTableWidget, rows: list[dict], *, columns: list[tuple[str, str]]) -> None:
        table.setColumnCount(len(columns))
        table.setHorizontalHeaderLabels([label for _, label in columns])
        table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, (key, _) in enumerate(columns):
                value = row.get(key, "")
                if key == "avg_confidence" and isinstance(value, (int, float)):
                    value = f"{value * 100:.0f}%"
                if key == "processed_at" and hasattr(value, "strftime"):
                    value = value.strftime("%Y-%m-%d %H:%M")
                item = QtWidgets.QTableWidgetItem(str(value))
                table.setItem(r, c, item)
        table.resizeColumnsToContents()

    def _colorize_not_found_in_review(self) -> None:
        """Colorize NOT_FOUND entries in the review table with red text."""
        red_color = self.colors.get("error", "#f38ba8")
        for row in range(self.review_table.rowCount()):
            for col in range(self.review_table.columnCount()):
                item = self.review_table.item(row, col)
                if item and "NOT_FOUND" in item.text():
                    item.setForeground(QtGui.QColor(red_color))

    # === SDS processing ===

    def _load_last_sds_folder(self) -> None:
        """Load and restore the last selected SDS folder from settings."""
        last_folder = self.app_settings.value("sds_last_folder", None)
        if last_folder and Path(last_folder).exists():
            self._selected_sds_folder = Path(last_folder)
            if hasattr(self, 'folder_label'):
                self.folder_label.setText(str(self._selected_sds_folder))
            # Don't auto-load files, just set the path
        else:
            if hasattr(self, 'folder_label'):
                self.folder_label.setText("No folder selected")

    def _save_last_sds_folder(self, folder_path: Path) -> None:
        """Save the selected SDS folder to settings for next run."""
        self.app_settings.setValue("sds_last_folder", str(folder_path))

    def _on_select_folder(self) -> None:
        # Start from last used folder if available, otherwise use default
        start_dir = str(self._selected_sds_folder) if self._selected_sds_folder else str(self.settings.paths.input_dir)
        folder = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Select SDS folder", start_dir
        )
        if folder:
            self._selected_sds_folder = Path(folder)
            self._save_last_sds_folder(self._selected_sds_folder)
            self.folder_label.setText(str(self._selected_sds_folder))
            self._load_sds_files()

    def _load_sds_files(self) -> None:
        if not self._selected_sds_folder:
            return
        # Fresh load: clear progress and any stale processing maps
        self._reset_sds_progress()
        self._processing_file_map = {}
        self._processing_name_map = {}
        self._cancel_processing = False

        files = self._collect_sds_files(self._selected_sds_folder)
        self.sds_table.clearContents()
        self.sds_table.setRowCount(len(files))
        self.sds_selected_files = files.copy()

        # Show the info container now that files are loaded
        self.sds_info_container.setVisible(True)

        # Get processed files for visual indicators
        processed_metadata = self.db.get_processed_files_metadata()
        # Consider a file processed if its filename exists in metadata, regardless of size differences
        processed_names = {name for (name, _size) in processed_metadata.keys()}

        for idx, file_path in enumerate(files):
            # Check if this file was already processed
            # Use filename-only check to avoid false pending due to size changes
            is_processed = file_path.name in processed_names
            # Column 0: Checkbox in a container with gray background
            container = QtWidgets.QWidget()
            container.setStyleSheet(
                f"QWidget {{"
                f"background-color: {self.colors['input']};"
                f"}}"
            )
            container_layout = QtWidgets.QHBoxLayout(container)
            container_layout.setContentsMargins(4, 0, 4, 0)
            container_layout.setSpacing(0)

            checkbox = QtWidgets.QCheckBox()
            checkbox.setChecked(True)
            self._style_checkbox_symbols(checkbox, font_size=16, spacing=0)
            checkbox.stateChanged.connect(self._on_file_selection_changed)
            container_layout.addWidget(checkbox)
            container_layout.addStretch()
            self.sds_table.setCellWidget(idx, 0, container)

            # Column 1: File name (with visual indicator if processed)
            file_display = f"✓ {file_path.name}" if is_processed else file_path.name
            file_item = QtWidgets.QTableWidgetItem(file_display)
            if is_processed:
                file_item.setForeground(QtGui.QColor(self.colors.get('success', '#a6e3a1')))
            self.sds_table.setItem(idx, 1, file_item)
            
            # Column 2: Chemical
            self.sds_table.setItem(idx, 2, QtWidgets.QTableWidgetItem(""))
            
            # Column 3: Status with visual indicator
            process_all = self.process_all_checkbox.isChecked()
            if is_processed:
                if process_all:
                    status_item = QtWidgets.QTableWidgetItem("↻ Will reprocess")
                    status_item.setForeground(QtGui.QColor(self.colors.get('warning', '#f9e2af')))
                else:
                    status_item = QtWidgets.QTableWidgetItem("✓ Processed (skip)")
                    status_item.setForeground(QtGui.QColor(self.colors.get('success', '#a6e3a1')))
            else:
                status_item = QtWidgets.QTableWidgetItem("⏳ Pending")
            self.sds_table.setItem(idx, 3, status_item)

        self.sds_table.resizeColumnsToContents()
        self._update_sds_file_count()

    def _on_process_all_changed(self) -> None:
        """Handle changes to the 'Process all files' checkbox."""
        # Update status indicators in the table
        process_all = self.process_all_checkbox.isChecked()
        
        for idx in range(self.sds_table.rowCount()):
            status_item = self.sds_table.item(idx, 3)
            if status_item:
                # Check if this is a processed file (by checking file name column for ✓)
                name_item = self.sds_table.item(idx, 1)
                is_processed = name_item and name_item.text().startswith("✓ ")
                
                if is_processed:
                    if process_all:
                        # When "process all" is checked, show that it will be reprocessed
                        status_item.setText("↻ Will reprocess")
                        status_item.setForeground(QtGui.QColor(self.colors.get('warning', '#f9e2af')))
                    else:
                        # When unchecked, show it will be skipped
                        status_item.setText("✓ Processed (skip)")
                        status_item.setForeground(QtGui.QColor(self.colors.get('success', '#a6e3a1')))

    def _on_select_pending_files(self) -> None:
        """Select only files that are not yet processed (pending)."""
        total_files = self.sds_table.rowCount()
        for idx in range(total_files):
            # Check the Status column (column 3) to see if it's pending
            status_item = self.sds_table.item(idx, 3)
            if status_item:
                status_text = status_item.text()
                # Select only if status is "Pending" or "Will reprocess"
                is_pending = "Pending" in status_text or "Will reprocess" in status_text

                container = self.sds_table.cellWidget(idx, 0)
                if container:
                    layout = container.layout()
                    if layout and layout.count() > 0:
                        item = layout.itemAt(0)
                        if item:
                            checkbox = item.widget()
                            if isinstance(checkbox, QtWidgets.QCheckBox):
                                checkbox.blockSignals(True)
                                checkbox.setChecked(is_pending)
                                checkbox.blockSignals(False)
                                self._refresh_checkbox_symbols(checkbox)
        self._update_sds_file_count()

    def _on_file_selection_changed(self) -> None:
        """Handle file selection/deselection in the table."""
        self._update_sds_file_count()

    def _update_sds_file_count(self) -> None:
        """Update the info label showing file counts."""
        total_files = self.sds_table.rowCount()
        selected_files = 0
        for idx in range(total_files):
            container = self.sds_table.cellWidget(idx, 0)
            if container:
                # Container has layout with checkbox
                layout = container.layout()
                if layout and layout.count() > 0:
                    checkbox = layout.itemAt(0).widget()
                    if isinstance(checkbox, QtWidgets.QCheckBox) and checkbox.isChecked():
                        selected_files += 1
        self.sds_info.setText(f"Files: {selected_files} selected / {total_files} listed")

    def _on_select_all_files(self) -> None:
        """Select all files in the SDS table."""
        total_files = self.sds_table.rowCount()
        for idx in range(total_files):
            container = self.sds_table.cellWidget(idx, 0)
            if container:
                layout = container.layout()
                if layout and layout.count() > 0:
                    item = layout.itemAt(0)
                    if item:
                        checkbox = item.widget()
                        if isinstance(checkbox, QtWidgets.QCheckBox):
                            checkbox.blockSignals(True)
                            checkbox.setChecked(True)
                            checkbox.blockSignals(False)
                            self._refresh_checkbox_symbols(checkbox)
        self._update_sds_file_count()

    def _on_unselect_all_files(self) -> None:
        """Unselect all files in the SDS table."""
        total_files = self.sds_table.rowCount()
        for idx in range(total_files):
            container = self.sds_table.cellWidget(idx, 0)
            if container:
                layout = container.layout()
                if layout and layout.count() > 0:
                    item = layout.itemAt(0)
                    if item:
                        checkbox = item.widget()
                        if isinstance(checkbox, QtWidgets.QCheckBox):
                            checkbox.blockSignals(True)
                            checkbox.setChecked(False)
                            checkbox.blockSignals(False)
                            self._refresh_checkbox_symbols(checkbox)
        self._update_sds_file_count()

    def _get_selected_sds_files(self) -> list[Path]:
        """Get list of selected files from the table."""
        selected = []
        for idx in range(self.sds_table.rowCount()):
            container = self.sds_table.cellWidget(idx, 0)
            if container:
                layout = container.layout()
                if layout and layout.count() > 0:
                    item = layout.itemAt(0)
                    if item:
                        checkbox = item.widget()
                        if isinstance(checkbox, QtWidgets.QCheckBox) and checkbox.isChecked():
                            file_item = self.sds_table.item(idx, 1)
                            if file_item and self._selected_sds_folder:
                                # Remove any leading status marker (e.g., "✓ ") when resolving the path
                                file_name = file_item.text().replace("✓ ", "").strip()
                                file_path = self._selected_sds_folder / file_name
                                if file_path.exists():
                                    selected.append(file_path)
        return selected

    def _collect_sds_files(self, folder: Path) -> list[Path]:
        files: list[Path] = []
        for suffix in SUPPORTED_FORMATS:
            files.extend(folder.rglob(f"*{suffix}"))
        return sorted(files)

    def _on_process_sds(self) -> None:
        if not self._selected_sds_folder:
            QtWidgets.QMessageBox.warning(self, "No folder", "Select an SDS folder first.")
            return

        # Get selected files from table
        files = self._get_selected_sds_files()
        if not files:
            QtWidgets.QMessageBox.information(self, "No files", "Please select files to process.")
            return

        logger.info("Selected %d SDS files for processing", len(files))

        # Filter out already processed files if checkbox is unchecked
        process_all = self.process_all_checkbox.isChecked()
        original_count = len(files)

        if not process_all:
            self._set_status(f"Checking database for {original_count} files...")
            logger.info("Checking which files have been processed...")

            # Batch load all processed file paths for fast lookup
            processed_paths = self.db.get_processed_file_paths()
            logger.debug("Found %d already processed files in database", len(processed_paths))

            # Filter files - fast set lookup instead of per-file database query
            files = [f for f in files if str(f) not in processed_paths]
            filtered_count = original_count - len(files)

            logger.info("Filtered: %d already processed, %d new files to process", filtered_count, len(files))

            if not files:
                QtWidgets.QMessageBox.information(
                    self, "All processed",
                    f"All {original_count} files have already been processed.\n\n"
                    "Check 'Process all files' to reprocess them."
                )
                return

            if filtered_count > 0:
                self._set_status(f"Filtered: {filtered_count} already processed, {len(files)} new files to process")

        # Setup UI for processing (preserve table, update rows in-place)
        self.sds_progress.setValue(0)
        # Build maps for file -> row index so we can update rows in real-time
        self._processing_file_map: dict[Path, int] = {}
        self._processing_name_map: dict[str, int] = {}
        
        # Find row indices for selected files in the existing table
        for idx in range(self.sds_table.rowCount()):
            file_item = self.sds_table.item(idx, 1)  # File name is in column 1
            if file_item:
                file_name = file_item.text().replace("✓ ", "")  # Remove checkmark if present
                file_path = self._selected_sds_folder / file_name
                if file_path in files:
                    self._processing_file_map[file_path] = idx
                    self._processing_name_map[file_path.name] = idx
                    # Update Status (column 3) to show processing will start
                    status_item = self.sds_table.item(idx, 3)
                    if status_item:
                        status_item.setText("⏳ Processing...")
                        status_item.setForeground(QtGui.QColor(self.colors['text']))

        self._cancel_processing = False
        self.process_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        use_rag = self.use_rag_checkbox.isChecked()

        if process_all:
            status_msg = f"Processing {len(files)} files (force reprocess all)…"
        else:
            status_msg = f"Processing {len(files)} new files…"
        self._set_status(status_msg)
        self._start_task(
            self._process_sds_task,
            files,
            use_rag,
            process_all,
            on_result=self._on_sds_done,
            on_progress=self._on_sds_progress
        )

    def _on_file_processed(self, fname: str, chemical: str, status: str, row_idx: int) -> None:
        """Update table in real-time when a file is processed."""
        status_display = self._format_status(status)
        resolved_row = self._resolve_row_index(fname, row_idx)
        if resolved_row is None:
            return
        # Column 0 has checkbox - don't touch it
        # Column 1: File name - keep it as is (already set)
        # Column 2: Update Chemical
        chemical_item = self.sds_table.item(resolved_row, 2)
        if chemical_item:
            chemical_item.setText(chemical or "-")
        else:
            self.sds_table.setItem(resolved_row, 2, QtWidgets.QTableWidgetItem(chemical or "-"))
        # Column 3: Update Status
        status_item = self.sds_table.item(resolved_row, 3)
        if status_item:
            status_item.setText(status_display)
            # Reset color to default
            status_item.setForeground(QtGui.QColor(self.colors['text']))
        else:
            self.sds_table.setItem(resolved_row, 3, QtWidgets.QTableWidgetItem(status_display))

    def _on_sds_progress(self, percent: int, label: str) -> None:
        """Update progress bar and status during SDS processing."""
        self.sds_progress.setValue(percent)
        self.sds_file_counter.setText(label)
        self._set_status(f"Processing: {label}")

    def _process_sds_task(self, files: list[Path], use_rag: bool, force_reprocess: bool = False, *, signals: WorkerSignals | None = None) -> list[tuple[str, str, str, int]]:
        processor = SDSProcessor()
        results: list[tuple[str, str, str, int]] = []
        total = max(1, len(files))
        for idx, path in enumerate(files, 1):
            # Check for cancellation
            if self._cancel_processing:
                if signals:
                    signals.message.emit("Processing cancelled by user")
                logger.info("Processing cancelled after %d/%d files", idx - 1, total)
                break

            if signals:
                pct = int(idx / total * 100)
                signals.progress.emit(pct, f"{idx}/{total}")
                signals.message.emit(f"Processing {path.name}")
            try:
                res = processor.process(path, use_rag=use_rag, force_reprocess=force_reprocess)
                chemical = ""
                if res.extractions and "product_name" in res.extractions:
                    product = res.extractions.get("product_name", {})
                    chemical = product.get("value") or product.get("normalized_value") or ""
                
                # Emit individual file result for real-time table update
                if signals:
                    status_emoji = "✅" if res.status in ("completed", "success") else "⚠️" if res.status == "partial" else "❌"
                    signals.message.emit(f"{status_emoji} {path.name}: {res.status}")
                    mapped_row = self._processing_file_map.get(path)
                    if mapped_row is None:
                        mapped_row = self._processing_name_map.get(path.name, idx - 1)
                    signals.file_result.emit(path.name, chemical, res.status, mapped_row)
                
                mapped_row = self._processing_file_map.get(path)
                if mapped_row is None:
                    mapped_row = self._processing_name_map.get(path.name, idx - 1)
                results.append((path.name, chemical, res.status, mapped_row))
            except Exception as exc:
                logger.error("Failed to process %s: %s", path, exc)
                if signals:
                    signals.error.emit(f"Failed: {path.name} ({exc})")
                mapped_row = self._processing_file_map.get(path)
                if mapped_row is None:
                    mapped_row = self._processing_name_map.get(path.name, idx - 1)
                results.append((path.name, "", "error", mapped_row))
        return results

    def _on_sds_done(self, result: object) -> None:
        self.process_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

        if not isinstance(result, list):
            return

        # Final update for any files that weren't updated in real-time
        for fname, chemical, status, row_idx in result:
            status_display = self._format_status(status)
            resolved_row = self._resolve_row_index(fname, row_idx)
            if resolved_row is None:
                continue
            # Column 0: checkbox - leave untouched
            # Column 1: file name - already set
            # Column 2: Chemical
            chemical_item = self.sds_table.item(resolved_row, 2)
            if chemical_item:
                chemical_item.setText(chemical or "-")
            # Column 3: Status
            status_item = self.sds_table.item(resolved_row, 3)
            if status_item:
                status_item.setText(status_display)
                status_item.setForeground(QtGui.QColor(self.colors['text']))

        self.sds_table.resizeColumnsToContents()
        self.sds_progress.setValue(100)
        self._refresh_db_stats()
        
        # Clear the processing map
        self._processing_file_map = {}
        self._processing_name_map = {}

        if self._cancel_processing:
            QtWidgets.QMessageBox.information(self, "Processing stopped", f"Processed {len(result)} files before stopping.")
        else:
            QtWidgets.QMessageBox.information(self, "Processing complete", f"Processed {len(result)} files.")
    
    def _format_status(self, status: str) -> str:
        """Format status with emoji for better visual feedback."""
        status_map = {
            "completed": "✅ Success",
            "success": "✅ Success",
            "partial": "⚠️ Partial",
            "failed": "❌ Failed",
            "error": "❌ Error",
            "pending": "⏳ Pending",
            "processing": "🔄 Processing",
        }
        return status_map.get(status.lower(), f"✅ {status}")

    def _resolve_row_index(self, fname: str, preferred_idx: int) -> int | None:
        """
        Resolve the target row for a file using known lookup maps or fallback to the preferred index.
        Returns None if the row cannot be found (e.g., the table changed mid-run).
        """
        if 0 <= preferred_idx < self.sds_table.rowCount():
            return preferred_idx
        if hasattr(self, "_processing_name_map"):
            mapped = self._processing_name_map.get(fname)
            if mapped is not None and 0 <= mapped < self.sds_table.rowCount():
                return mapped
        # Fallback: search by filename in column 1 (with or without leading checkmark)
        for idx in range(self.sds_table.rowCount()):
            item = self.sds_table.item(idx, 1)
            if item:
                name = item.text().replace("✓ ", "")
                if name == fname:
                    return idx
        return None

    def _on_build_matrix(self) -> None:
        self._set_status("Building matrices…")
        self._start_task(self._build_matrix_task, on_result=self._on_matrix_built)

    def _build_matrix_task(self, *, signals: WorkerSignals | None = None) -> dict:
        builder = MatrixBuilder()
        incomp_matrix = builder.build_incompatibility_matrix()
        hazard_matrix = builder.build_hazard_matrix()
        stats = builder.get_matrix_statistics()
        dangerous = builder.get_dangerous_chemicals()
        if signals:
            signals.message.emit("Matrices built")
        return {
            "incompatibility": incomp_matrix,
            "hazard": hazard_matrix,
            "stats": stats,
            "dangerous": dangerous,
        }

    def _on_matrix_built(self, result: object) -> None:
        if not isinstance(result, dict):
            return
        stats = result.get("stats")
        if stats:
            msg = (
                f"Total products: {stats.total_chemicals}\n"
                f"Incompatibility pairs: {stats.incompatibility_pairs}\n"
                f"Average completeness: {stats.avg_completeness * 100:.1f}%\n"
                f"Average confidence: {stats.avg_confidence * 100:.1f}%"
            )
        else:
            msg = "Matrices built."
        QtWidgets.QMessageBox.information(self, "Matrix", msg)

    def _on_export(self) -> None:
        output_dir = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Select export directory", str(self.settings.paths.output_dir)
        )
        if not output_dir:
            return
        self._set_status(f"Exporting to {output_dir}…")
        self._start_task(self._export_task, Path(output_dir), on_result=self._on_export_done)

    def _export_task(self, output_dir: Path, *, signals: WorkerSignals | None = None) -> dict:
        builder = MatrixBuilder()
        incomp_matrix = builder.build_incompatibility_matrix()
        hazard_matrix = builder.build_hazard_matrix()
        stats = builder.get_matrix_statistics()
        dangerous_chems = builder.get_dangerous_chemicals()

        exporter = MatrixExporter()

        matrices = {}
        if not incomp_matrix.empty:
            matrices["Matriz_Incompatibilidades"] = incomp_matrix
        if not hazard_matrix.empty:
            matrices["Matriz_Classes_de_Perigo"] = hazard_matrix

        stats_dict = {
            "Total de Produtos": stats.total_chemicals,
            "Pares de Incompatibilidade": stats.incompatibility_pairs,
            "Distribuicao de Perigos": stats.hazard_distribution,
            "Status de Processamento": stats.processing_status,
            "Media de Completude (%)": f"{stats.avg_completeness * 100:.1f}%",
            "Media de Confianca (%)": f"{stats.avg_confidence * 100:.1f}%",
        }

        export_results = exporter.export_report(
            matrices=matrices,
            statistics=stats_dict,
            output_dir=output_dir,
            format_type="all",
        )

        if dangerous_chems:
            dangerous_path = Path(output_dir) / "dangerous_chemicals.xlsx"
            exporter.export_dangerous_chemicals_report(dangerous_chems, dangerous_path)
            export_results["dangerous_chemicals"] = True

        if signals:
            signals.message.emit("Export complete")
        return export_results

    def _on_export_done(self, result: object) -> None:
        if isinstance(result, dict):
            QtWidgets.QMessageBox.information(
                self,
                "Export complete",
                f"Exported {len(result)} file(s).",
            )
        self._refresh_db_stats()

    # === Backup ===

    def _on_backup(self) -> None:
        output_dir = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Select backup directory", str(self.settings.paths.output_dir)
        )
        if not output_dir:
            return
        self._set_status(f"Starting backup to {output_dir}…")
        self._start_task(self._backup_task, Path(output_dir), on_result=self._on_backup_done)

    def _backup_task(self, output_dir: Path, *, signals: WorkerSignals | None = None) -> str:
        db_path = str(getattr(self.settings.paths, "duckdb", "data/duckdb/extractions.db"))
        cmd = [
            sys.executable,
            "scripts/rag_backup.py",
            "--output",
            str(output_dir),
            "--db",
            db_path,
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, cwd=Path.cwd())
        log = proc.stdout or ""
        if proc.stderr:
            log += "\n[stderr]\n" + proc.stderr
        if signals:
            signals.message.emit(f"Backup finished (code {proc.returncode})")
        return log

    def _on_backup_done(self, result: object) -> None:
        if isinstance(result, str):
            self.backup_log.setPlainText(result.strip() or "No log output.")
        self._set_status("Backup complete")

    # === Status ===

    def _refresh_db_stats(self) -> None:
        stats = self.db.get_statistics()

        # Database Statistics
        total_docs = stats.get('total_documents', 0)
        processed_docs = stats.get('processed', stats.get('successful_documents', 0))
        failed_docs = stats.get('failed_documents', 0)
        rag_docs = stats.get('rag_documents', 0)

        # Calculate success rate
        success_rate = 0
        if total_docs > 0:
            success_rate = int((processed_docs / total_docs) * 100)

        stats_text = (
            f"📄 Total: {total_docs} | "
            f"✅ Processed: {processed_docs} ({success_rate}%) | "
            f"❌ Failed: {failed_docs} | "
            f"🧠 RAG Indexed: {rag_docs}"
        )
        self.status_stats_label.setText(stats_text)

        # Update Ollama status
        try:
            models = self.ollama.list_models()
            if models:
                status_text = "✓ Connected"
                self._style_label(self.ollama_status_label, color=self.colors.get("success", "#a6e3a1"))
                models_text = f"Available models: {len(models)} - {', '.join(models[:3])}"
                if len(models) > 3:
                    models_text += f" +{len(models)-3} more"
                self.ollama_models_label.setText(models_text)
                self._style_label(self.ollama_models_label, color=self.colors.get("subtext", "#a6adc8"))
            else:
                status_text = "⚠ Connected but no models available"
                self._style_label(self.ollama_status_label, color=self.colors.get("warning", "#f9e2af"))
                self.ollama_models_label.setText("No models installed")
        except Exception as e:
            status_text = "✗ Not connected"
            self._style_label(self.ollama_status_label, color=self.colors.get("error", "#f38ba8"))
            self.ollama_models_label.setText(f"Connection error: {str(e)[:50]}")
            self._style_label(self.ollama_models_label, color=self.colors.get("error", "#f38ba8"))

        self.ollama_status_label.setText(status_text)

        # Update RAG status
        try:
            vector_store = self.ingestion.vector_store
            vector_count = len(vector_store.db.get())  # Approximate count
            if vector_count > 0:
                self.rag_status_label.setText("✓ RAG System Active")
                self._style_label(self.rag_status_label, color=self.colors.get("success", "#a6e3a1"))
            else:
                self.rag_status_label.setText("⚠ RAG System Idle")
                self._style_label(self.rag_status_label, color=self.colors.get("warning", "#f9e2af"))

            self.rag_documents_label.setText(f"Indexed documents: {vector_count}")
            self._style_label(self.rag_documents_label, color=self.colors.get("subtext", "#a6adc8"))
        except Exception as e:
            self.rag_status_label.setText("✗ RAG System Error")
            self._style_label(self.rag_status_label, color=self.colors.get("error", "#f38ba8"))
            self.rag_documents_label.setText(f"Error: {str(e)[:50]}")
            self._style_label(self.rag_documents_label, color=self.colors.get("error", "#f38ba8"))

    def _on_chat_send(self) -> None:
        """Handle chat message sending with RAG context."""
        text = self.chat_input.text().strip()
        if not text:
            return

        # Add user message to display
        self.chat_display.append(f"<b>You:</b> {text}")
        self.chat_input.clear()
        self.chat_input.setEnabled(False)

        # Show thinking status
        self.chat_status.setText("🤔 Thinking...")
        self._style_label(self.chat_status, color=self.colors.get("accent", "#4fd1c5"))

        # Run in background thread
        def chat_task(*, signals: WorkerSignals):
            try:
                # Get RAG context from vector store
                vector_store = self.ingestion.vector_store
                results = vector_store.search_with_context(text, top_k=3)

                context = ""
                if results:
                    context = "\n".join([r.get("context", "") for r in results])
                    signals.message.emit(f"Found {len(results)} relevant documents")
                else:
                    signals.message.emit("No relevant documents found in knowledge base")

                # Get Ollama response with context
                response = self.ollama.chat(message=text, context=context)
                signals.finished.emit(response)
            except Exception as e:
                signals.error.emit(str(e))
                signals.finished.emit(None)

        # Create and run worker
        worker = TaskRunner(chat_task)
        worker.signals.finished.connect(self._on_chat_response)
        worker.signals.error.connect(self._on_chat_error)
        worker.signals.message.connect(self._set_status)
        self._workers.append(worker)
        self.thread_pool.start(worker)

    def _on_chat_response(self, response: object) -> None:
        """Handle chat response from Ollama."""
        self.chat_input.setEnabled(True)

        if response:
            # Format the response nicely
            response_text = str(response).strip()
            self.chat_display.append(f"<b>Assistant:</b> {response_text}")
            self.chat_status.setText("✓ Response received")
            self._style_label(self.chat_status, color=self.colors.get("success", "#22c55e"))
            self._set_status("Chat response received")
        else:
            self.chat_display.append("<i style='color: #f87171;'>Error: Could not generate response</i>")
            self.chat_status.setText("✗ Failed to generate response")
            self._style_label(self.chat_status, color=self.colors.get("error", "#f87171"))
            self._set_status("Chat failed", error=True)

    def _on_chat_error(self, error: str) -> None:
        """Handle chat error."""
        self.chat_input.setEnabled(True)
        self.chat_display.append(f"<i style='color: #f87171;'>⚠️ Error: {error}</i>")
        self.chat_status.setText(f"✗ Error: {error}")
        self._style_label(self.chat_status, color=self.colors.get("error", "#f87171"))
        self._set_status(f"Chat error: {error}", error=True)


def run_app() -> None:
    """Application entry point."""
    app = QtWidgets.QApplication([])
    window = MainWindow()
    window.show()
    app.exec()
