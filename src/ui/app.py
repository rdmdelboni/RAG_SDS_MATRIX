"""PySide6-based UI for RAG SDS Matrix.

This replaces the previous CustomTkinter UI with a Qt implementation. It keeps
core workflows (knowledge ingestion, SDS processing, matrix export/build, basic
status views) while relying on the existing backend services.
"""

from __future__ import annotations


import os
import ctypes
from ctypes.util import find_library
from pathlib import Path
from typing import Callable

from PySide6 import QtCore, QtGui, QtWidgets

from ..config import get_settings, get_text
from ..config.i18n import set_language
from ..database import get_db_manager
from ..models import get_ollama_client
from ..rag.ingestion_service import KnowledgeIngestionService

from ..sds.heuristics import HeuristicExtractor
from ..sds.extractor import SDSExtractor
from ..sds.profile_router import ProfileRouter
from ..utils.logger import get_logger
from .theme import get_colors
from .components.workers import TaskRunner
from .tabs import TabContext
from .tabs.backup_tab import BackupTab
from .tabs.records_tab import RecordsTab
from .tabs.review_tab import ReviewTab
from .tabs.status_tab import StatusTab
from .tabs.chat_tab import ChatTab
from .tabs.regex_lab_tab import RegexLabTab
from .tabs.automation_tab import AutomationTab
from .tabs.graph_tab import GraphTab
from .tabs.rag_tab import RAGTab
from .tabs.sds_tab import SDSTab
from .tabs.sds_processing_tab import SDSProcessingTab

logger = get_logger(__name__)


class QtInitError(RuntimeError):
    """Raised when the Qt application cannot be initialized."""


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

        self._build_ui()
        # Note: Tab-based UI handles its own initialization and refreshing

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
        self.sds_processing_tab = SDSProcessingTab(tab_context)  # New unified tab
        self.records_tab = RecordsTab(tab_context)
        self.review_tab = ReviewTab(tab_context)
        self.backup_tab = BackupTab(tab_context)
        self.status_tab = StatusTab(tab_context)
        self.chat_tab = ChatTab(tab_context)
        self.automation_tab = AutomationTab(tab_context)
        self.regex_lab_tab = RegexLabTab(tab_context)
        self.graph_tab = GraphTab(tab_context)

        # Add tabs to tab widget
        self.tabs.addTab(self.rag_tab, "RAG")
        self.tabs.addTab(self.sds_processing_tab, "🔬 SDS Processing")  # New unified tab
        self.tabs.addTab(self.sds_tab, "SDS (Legacy)")
        self.tabs.addTab(self.records_tab, "Records")
        self.tabs.addTab(self.review_tab, "Review")
        self.tabs.addTab(self.backup_tab, "Backup")
        self.tabs.addTab(self.status_tab, "Status")
        self.tabs.addTab(self.chat_tab, "Chat")
        self.tabs.addTab(self.automation_tab, "Automation")
        self.tabs.addTab(self.graph_tab, "🕸️ Graph")
        self.tabs.addTab(self.regex_lab_tab, "Regex Lab (Legacy)")

        self.status_bar = self.statusBar()
        self.status_label = QtWidgets.QLabel(get_text("app.ready"))
        self.status_bar.addWidget(self.status_label)

        self.setCentralWidget(central)

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

    def _start_task(
        self,
        fn: Callable,
        *args,
        on_result: Callable | None = None,
        on_progress: Callable | None = None,
        on_data: Callable | None = None,
    ) -> None:
        worker = TaskRunner(fn, *args)
        self._workers.append(worker)

        worker.signals.message.connect(self._set_status)
        worker.signals.error.connect(lambda msg, w=worker: self._on_worker_error(msg, w))
        
        # Connect progress signal if handler provided
        if on_progress:
            worker.signals.progress.connect(on_progress)

        # Connect data signal for granular updates (e.g., per-file status)
        if on_data:
            worker.signals.data.connect(on_data)
        
        # Connect per-file result updates when handler is present in MainWindow (legacy)
        # or if the generic handler is used.
        # Note: Tabs now handle their own file results via their own on_progress/on_result callbacks.
        
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

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        """Handle application closure."""
        # Wait for workers if needed?
        # ideally we should signal them to stop
        event.accept()


def _configure_qt_plugins() -> None:
    """Ensure Qt can locate style/platform plugins (e.g., Kvantum)."""
    plugin_candidates = [
        Path("/usr/lib/qt6/plugins"),
        Path("/usr/lib64/qt6/plugins"),
        Path("/usr/lib/plugins"),
    ]
    for candidate in plugin_candidates:
        styles_dir = candidate / "styles"
        if styles_dir.exists() and any(styles_dir.glob("libkvantum*.so")):
            os.environ.setdefault("QT_PLUGIN_PATH", str(candidate))
            QtCore.QCoreApplication.addLibraryPath(str(candidate))
            logger.info(f"Qt plugin path added: {candidate}")
            break


def _ensure_platform() -> bool:
    """Select a safe platform plugin; return True if we forced offscreen."""
    def _has_xcb_cursor() -> bool:
        # Try to locate and load the xcb-cursor library; Qt aborts if it is missing.
        candidates = [
            "xcb-cursor",
            "xcb-cursor0",
            "libxcb-cursor.so.0",
        ]
        for candidate in candidates:
            lib_path = find_library(candidate)
            if not lib_path:
                continue
            try:
                ctypes.CDLL(lib_path)
                return True
            except OSError:
                continue
        return False

    has_display = os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")
    current_platform = os.environ.get("QT_QPA_PLATFORM", "")
    platform_set = bool(current_platform)

    # If multiple platforms are configured (e.g., "wayland;xcb"), pick one
    # deterministically to avoid Qt aborts. Prefer Wayland when available.
    if platform_set and ";" in current_platform:
        if os.environ.get("WAYLAND_DISPLAY"):
            chosen = "wayland"
        elif os.environ.get("DISPLAY"):
            chosen = "xcb"
        else:
            chosen = "offscreen"
        os.environ["QT_QPA_PLATFORM"] = chosen
        logger.warning(
            "Multiple Qt platforms configured (%s); using '%s' to avoid crashes.",
            current_platform,
            chosen,
        )
        return chosen == "offscreen"

    # Some Wayland setups (e.g., Hyperland with missing runtime deps) crash before
    # Python can handle the error. Prefer xcb when Xwayland is available.
    if platform_set and current_platform == "wayland" and os.environ.get("DISPLAY"):
        os.environ["QT_QPA_PLATFORM"] = "xcb"
        logger.warning(
            "Wayland platform requested but may be unstable; using 'xcb' via Xwayland."
        )
        return False

    if not platform_set and not has_display:
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        logger.warning("No display detected. Using Qt offscreen platform plugin.")
        return True

    if not platform_set and not _has_xcb_cursor():
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        logger.warning(
            "Qt xcb cursor dependency missing; using offscreen platform plugin."
        )
        return True

    return False


def _create_qt_app(argv: list[str]) -> QtWidgets.QApplication:
    """Create a QApplication or raise a clear initialization error."""
    try:
        existing = QtWidgets.QApplication.instance()
        return existing or QtWidgets.QApplication(argv)
    except Exception as exc:
        raise QtInitError(
            "Qt platform initialization failed:"
            f" {exc}. Check platform plugins or required system packages."
        ) from exc


def run_app() -> None:
    """Run the application, falling back to CLI when Qt cannot start."""
    import sys

    _configure_qt_plugins()
    forced_offscreen = _ensure_platform()

    # If we forced offscreen (no display server), the UI can't be interacted with.
    # Raise an explicit error so the caller can fall back to the CLI mode.
    if forced_offscreen and os.environ.get("QT_QPA_PLATFORM") == "offscreen":
        raise QtInitError("No display detected for Qt UI (offscreen fallback).")

    app = _create_qt_app(sys.argv)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
