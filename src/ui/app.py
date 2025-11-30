"""PySide6-based UI for RAG SDS Matrix.

This replaces the previous CustomTkinter UI with a Qt implementation. It keeps
core workflows (knowledge ingestion, SDS processing, matrix export/build, basic
status views) while relying on the existing backend services.
"""

from __future__ import annotations

import subprocess
import traceback
import sys
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
from ..utils.logger import get_logger
from .theme import get_colors

logger = get_logger(__name__)


class WorkerSignals(QtCore.QObject):
    """Signals shared by background workers."""

    finished = QtCore.Signal(object)
    error = QtCore.Signal(str)
    message = QtCore.Signal(str)
    progress = QtCore.Signal(int, str)  # percent, label


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
        theme_pref = (self.settings.ui.theme or "system").lower()
        if theme_pref == "system":
            theme_pref = "dark" if self._system_prefers_dark() else "light"
        self.colors = get_colors(theme_pref)
        self.db = get_db_manager()
        self.ingestion = KnowledgeIngestionService()
        self.ollama = get_ollama_client()
        self.thread_pool = QtCore.QThreadPool.globalInstance()
        self._workers: list[TaskRunner] = []
        self._cancel_processing = False

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

        self.tabs.addTab(self._create_rag_tab(), "RAG")
        self.tabs.addTab(self._create_sds_tab(), "SDS")
        self.tabs.addTab(self._create_records_tab(), "Records")
        self.tabs.addTab(self._create_review_tab(), "Review")
        self.tabs.addTab(self._create_backup_tab(), "Backup")
        self.tabs.addTab(self._create_status_tab(), "Status")
        self.tabs.addTab(self._create_chat_tab(), "Chat")

        self.status_bar = self.statusBar()
        self.status_label = QtWidgets.QLabel(get_text("app.ready"))
        self.status_bar.addWidget(self.status_label)

        self.setCentralWidget(central)

    def _create_rag_tab(self) -> QtWidgets.QWidget:
        tab = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(tab)
        layout.setSpacing(10)
        layout.setContentsMargins(12, 12, 12, 12)

        self.rag_stats_label = QtWidgets.QLabel("Knowledge base: --")
        self._style_label(self.rag_stats_label)
        layout.addWidget(self.rag_stats_label)

        btn_row = QtWidgets.QHBoxLayout()
        add_files_btn = QtWidgets.QPushButton("📁 Add Files")
        self._style_button(add_files_btn)
        add_files_btn.clicked.connect(self._on_ingest_files)
        btn_row.addWidget(add_files_btn)

        add_folder_btn = QtWidgets.QPushButton("📂 Add Folder")
        self._style_button(add_folder_btn)
        add_folder_btn.clicked.connect(self._on_ingest_folder)
        btn_row.addWidget(add_folder_btn)

        refresh_btn = QtWidgets.QPushButton("🔄 Refresh Sources")
        self._style_button(refresh_btn)
        refresh_btn.clicked.connect(self._refresh_sources_table)
        btn_row.addWidget(refresh_btn)

        btn_row.addStretch()
        layout.addLayout(btn_row)

        url_row = QtWidgets.QHBoxLayout()
        self.url_input = QtWidgets.QLineEdit()
        self.url_input.setPlaceholderText("https://example.com/safety-data-sheet")
        self.url_input.setStyleSheet(
            f"QLineEdit {{"
            f"background-color: {self.colors['input']};"
            f"color: {self.colors['text']};"
            f"border: 1px solid {self.colors['overlay']};"
            f"border-radius: 4px;"
            f"padding: 6px;"
            f"}}"
        )
        url_row.addWidget(self.url_input)
        ingest_url_btn = QtWidgets.QPushButton("🌐 Ingest URL")
        self._style_button(ingest_url_btn)
        ingest_url_btn.clicked.connect(self._on_ingest_url)
        url_row.addWidget(ingest_url_btn)
        layout.addLayout(url_row)

        self.sources_table = QtWidgets.QTableWidget(0, 4)
        self.sources_table.setHorizontalHeaderLabels(["Timestamp", "Title", "Type", "Chunks"])
        self.sources_table.horizontalHeader().setStretchLastSection(True)
        self._style_table(self.sources_table)
        layout.addWidget(self.sources_table)

        self.rag_log = QtWidgets.QTextEdit()
        self.rag_log.setReadOnly(True)
        self.rag_log.setPlaceholderText("Ingestion logs…")
        self._style_textedit(self.rag_log)
        layout.addWidget(self.rag_log)

        return tab

    def _create_sds_tab(self) -> QtWidgets.QWidget:
        tab = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(tab)
        layout.setSpacing(10)
        layout.setContentsMargins(12, 12, 12, 12)

        folder_row = QtWidgets.QHBoxLayout()
        self.folder_label = QtWidgets.QLabel("No folder selected")
        self._style_label(self.folder_label)
        folder_row.addWidget(self.folder_label)

        select_btn = QtWidgets.QPushButton("📂 Select Folder")
        self._style_button(select_btn)
        select_btn.clicked.connect(self._on_select_folder)
        folder_row.addWidget(select_btn)

        folder_row.addStretch()
        layout.addLayout(folder_row)

        controls = QtWidgets.QHBoxLayout()
        self.use_rag_checkbox = QtWidgets.QCheckBox("Use RAG enrichment")
        self.use_rag_checkbox.setChecked(True)
        self.use_rag_checkbox.setStyleSheet(
            f"QCheckBox {{"
            f"color: {self.colors['text']};"
            f"}}"
        )
        controls.addWidget(self.use_rag_checkbox)

        self.process_btn = QtWidgets.QPushButton("⚙️ Process SDS")
        self._style_button(self.process_btn)
        self.process_btn.clicked.connect(self._on_process_sds)
        controls.addWidget(self.process_btn)

        self.stop_btn = QtWidgets.QPushButton("⏹️ Stop")
        self.stop_btn.setStyleSheet(
            f"QPushButton {{"
            f"background-color: {self.colors.get('error', '#f38ba8')};"
            f"border: none;"
            f"border-radius: 4px;"
            f"color: {self.colors['bg']};"
            f"padding: 6px 12px;"
            f"font-weight: 500;"
            f"}}"
            f"QPushButton:hover {{"
            f"background-color: {self.colors.get('warning', '#f9e2af')};"
            f"}}"
            f"QPushButton:pressed {{"
            f"background-color: {self.colors.get('error', '#f38ba8')};"
            f"}}"
            f"QPushButton:disabled {{"
            f"background-color: {self.colors['overlay']};"
            f"color: {self.colors['text']};"
            f"opacity: 0.5;"
            f"}}"
        )
        self.stop_btn.clicked.connect(self._on_stop_processing)
        self.stop_btn.setEnabled(False)
        controls.addWidget(self.stop_btn)

        matrix_btn = QtWidgets.QPushButton("📊 Build Matrix")
        self._style_button(matrix_btn)
        matrix_btn.clicked.connect(self._on_build_matrix)
        controls.addWidget(matrix_btn)

        export_btn = QtWidgets.QPushButton("💾 Export")
        self._style_button(export_btn)
        export_btn.clicked.connect(self._on_export)
        controls.addWidget(export_btn)

        controls.addStretch()
        layout.addLayout(controls)

        self.sds_progress = QtWidgets.QProgressBar()
        self.sds_progress.setStyleSheet(
            f"QProgressBar {{"
            f"background-color: {self.colors['input']};"
            f"border: 1px solid {self.colors['overlay']};"
            f"border-radius: 4px;"
            f"}}"
            f"QProgressBar::chunk {{"
            f"background-color: {self.colors['accent']};"
            f"}}"
        )
        layout.addWidget(self.sds_progress)

        self.sds_table = QtWidgets.QTableWidget(0, 3)
        self.sds_table.setHorizontalHeaderLabels(["File", "Chemical", "Status"])
        self.sds_table.horizontalHeader().setStretchLastSection(True)
        self._style_table(self.sds_table)
        layout.addWidget(self.sds_table)

        return tab

    def _create_status_tab(self) -> QtWidgets.QWidget:
        tab = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(tab)
        layout.setSpacing(10)
        layout.setContentsMargins(12, 12, 12, 12)

        # Title
        title = QtWidgets.QLabel("📊 System Status")
        self._style_label(title, bold=True)
        title.setStyleSheet(title.styleSheet() + f"; font-size: 16px;")
        layout.addWidget(title)

        # Database Statistics Section
        db_title = QtWidgets.QLabel("📁 Database Statistics")
        self._style_label(db_title, bold=True)
        db_title.setStyleSheet(db_title.styleSheet() + f"; font-size: 12px;")
        layout.addWidget(db_title)

        db_frame = QtWidgets.QFrame()
        db_frame.setStyleSheet(
            f"QFrame {{"
            f"background-color: {self.colors['surface']};"
            f"border-radius: 6px;"
            f"padding: 12px;"
            f"}}"
        )
        db_layout = QtWidgets.QVBoxLayout(db_frame)
        db_layout.setSpacing(6)

        self.status_stats_label = QtWidgets.QLabel("Stats unavailable")
        self._style_label(self.status_stats_label)
        self.status_stats_label.setWordWrap(True)
        db_layout.addWidget(self.status_stats_label)

        db_frame.setLayout(db_layout)
        layout.addWidget(db_frame)

        # Ollama Status Section
        ollama_title = QtWidgets.QLabel("🤖 Ollama Connection")
        self._style_label(ollama_title, bold=True)
        ollama_title.setStyleSheet(ollama_title.styleSheet() + f"; font-size: 12px;")
        layout.addWidget(ollama_title)

        ollama_frame = QtWidgets.QFrame()
        ollama_frame.setStyleSheet(
            f"QFrame {{"
            f"background-color: {self.colors['surface']};"
            f"border-radius: 6px;"
            f"padding: 12px;"
            f"}}"
        )
        ollama_layout = QtWidgets.QVBoxLayout(ollama_frame)
        ollama_layout.setSpacing(6)

        self.ollama_status_label = QtWidgets.QLabel("Checking connection...")
        self._style_label(self.ollama_status_label)
        ollama_layout.addWidget(self.ollama_status_label)

        self.ollama_models_label = QtWidgets.QLabel("Available models: --")
        self._style_label(self.ollama_models_label, color=self.colors.get("subtext", "#a6adc8"))
        ollama_layout.addWidget(self.ollama_models_label)

        ollama_frame.setLayout(ollama_layout)
        layout.addWidget(ollama_frame)

        # RAG Status Section
        rag_title = QtWidgets.QLabel("🧠 RAG System")
        self._style_label(rag_title, bold=True)
        rag_title.setStyleSheet(rag_title.styleSheet() + f"; font-size: 12px;")
        layout.addWidget(rag_title)

        rag_frame = QtWidgets.QFrame()
        rag_frame.setStyleSheet(
            f"QFrame {{"
            f"background-color: {self.colors['surface']};"
            f"border-radius: 6px;"
            f"padding: 12px;"
            f"}}"
        )
        rag_layout = QtWidgets.QVBoxLayout(rag_frame)
        rag_layout.setSpacing(6)

        self.rag_status_label = QtWidgets.QLabel("RAG Status: Initializing...")
        self._style_label(self.rag_status_label)
        rag_layout.addWidget(self.rag_status_label)

        self.rag_documents_label = QtWidgets.QLabel("Indexed documents: --")
        self._style_label(self.rag_documents_label, color=self.colors.get("subtext", "#a6adc8"))
        rag_layout.addWidget(self.rag_documents_label)

        rag_frame.setLayout(rag_layout)
        layout.addWidget(rag_frame)

        # Refresh Button
        refresh_btn = QtWidgets.QPushButton("🔄 Refresh All Statistics")
        self._style_button(refresh_btn)
        refresh_btn.clicked.connect(self._refresh_db_stats)
        layout.addWidget(refresh_btn)

        layout.addStretch()
        return tab

    def _create_records_tab(self) -> QtWidgets.QWidget:
        tab = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(tab)
        layout.setSpacing(10)
        layout.setContentsMargins(12, 12, 12, 12)

        controls = QtWidgets.QHBoxLayout()
        limit_label = QtWidgets.QLabel("Limit:")
        self._style_label(limit_label)
        controls.addWidget(limit_label)

        self.records_limit = QtWidgets.QSpinBox()
        self.records_limit.setRange(10, 2000)
        self.records_limit.setValue(100)
        self.records_limit.setStyleSheet(
            f"QSpinBox {{"
            f"background-color: {self.colors['input']};"
            f"color: {self.colors['text']};"
            f"border: 1px solid {self.colors['overlay']};"
            f"border-radius: 4px;"
            f"padding: 4px;"
            f"}}"
        )
        controls.addWidget(self.records_limit)

        refresh = QtWidgets.QPushButton("🔄 Refresh")
        self._style_button(refresh)
        refresh.clicked.connect(self._on_refresh_records)
        controls.addWidget(refresh)

        controls.addStretch()
        layout.addLayout(controls)

        self.records_table = QtWidgets.QTableWidget(0, 7)
        self.records_table.setHorizontalHeaderLabels(
            ["File", "Status", "Product", "CAS", "Hazard", "Confidence", "Processed"]
        )
        self.records_table.horizontalHeader().setStretchLastSection(True)
        self._style_table(self.records_table)
        layout.addWidget(self.records_table)

        self.records_info = QtWidgets.QLabel("Ready")
        self._style_label(self.records_info, color=self.colors.get("subtext", "#888888"))
        layout.addWidget(self.records_info)

        return tab

    def _create_review_tab(self) -> QtWidgets.QWidget:
        tab = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(tab)
        layout.setSpacing(10)
        layout.setContentsMargins(12, 12, 12, 12)

        info = QtWidgets.QLabel(
            "Review processed documents and spot-check extracted fields. "
            "Edits are not yet implemented in the Qt port."
        )
        self._style_label(info, color=self.colors.get("subtext", "#888888"))
        info.setWordWrap(True)
        layout.addWidget(info)

        self.review_table = QtWidgets.QTableWidget(0, 6)
        self.review_table.setHorizontalHeaderLabels(
            ["File", "Status", "Product", "CAS", "UN", "Hazard"]
        )
        self.review_table.horizontalHeader().setStretchLastSection(True)
        self._style_table(self.review_table)
        layout.addWidget(self.review_table)

        refresh = QtWidgets.QPushButton("🔄 Refresh")
        self._style_button(refresh)
        refresh.clicked.connect(self._on_refresh_review)
        layout.addWidget(refresh)

        return tab

    def _create_backup_tab(self) -> QtWidgets.QWidget:
        tab = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(tab)
        layout.setSpacing(10)
        layout.setContentsMargins(12, 12, 12, 12)

        desc = QtWidgets.QLabel(
            "Run the backup script to export RAG data (incompatibilities, hazards, documents)."
        )
        self._style_label(desc, color=self.colors.get("subtext", "#888888"))
        desc.setWordWrap(True)
        layout.addWidget(desc)

        run_btn = QtWidgets.QPushButton("💾 Start Backup")
        self._style_button(run_btn)
        run_btn.clicked.connect(self._on_backup)
        layout.addWidget(run_btn)

        self.backup_log = QtWidgets.QTextEdit()
        self.backup_log.setReadOnly(True)
        self.backup_log.setPlaceholderText("Backup logs will appear here…")
        self._style_textedit(self.backup_log)
        layout.addWidget(self.backup_log)

        return tab

    def _create_chat_tab(self) -> QtWidgets.QWidget:
        """Create the Chat tab for interacting with the Ollama LLM."""
        tab = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(tab)
        layout.setSpacing(10)
        layout.setContentsMargins(12, 12, 12, 12)

        # Title
        title = QtWidgets.QLabel("Chat with RAG System")
        self._style_label(title, bold=True)
        title.setStyleSheet(title.styleSheet() + f"; font-size: 14px;")
        layout.addWidget(title)

        # Info
        info = QtWidgets.QLabel(
            "Ask questions about your knowledge base. The system uses RAG to retrieve "
            "relevant documents and Ollama to generate responses."
        )
        self._style_label(info, color=self.colors.get("subtext", "#888888"))
        info.setWordWrap(True)
        layout.addWidget(info)

        # Chat display
        self.chat_display = QtWidgets.QTextEdit()
        self.chat_display.setReadOnly(True)
        self._style_textedit(self.chat_display)
        layout.addWidget(self.chat_display)

        # Input row
        input_row = QtWidgets.QHBoxLayout()
        self.chat_input = QtWidgets.QLineEdit()
        self.chat_input.setPlaceholderText("Ask a question about your knowledge base...")
        self.chat_input.returnPressed.connect(self._on_chat_send)  # Allow Enter to send
        self.chat_input.setStyleSheet(
            f"QLineEdit {{"
            f"background-color: {self.colors['input']};"
            f"color: {self.colors['text']};"
            f"border: 1px solid {self.colors['overlay']};"
            f"border-radius: 4px;"
            f"padding: 8px;"
            f"font-size: 11px;"
            f"}}"
        )
        self.chat_input.setMinimumHeight(36)
        input_row.addWidget(self.chat_input)

        send_btn = QtWidgets.QPushButton("📤 Send")
        self._style_button(send_btn)
        send_btn.clicked.connect(self._on_chat_send)
        send_btn.setMinimumHeight(36)
        input_row.addWidget(send_btn)

        layout.addLayout(input_row)

        # Status indicator
        self.chat_status = QtWidgets.QLabel("Ready")
        self._style_label(self.chat_status, color=self.colors.get("subtext", "#888888"))
        self.chat_status.setStyleSheet(self.chat_status.styleSheet() + "; font-size: 10px;")
        layout.addWidget(self.chat_status)

        return tab

    def _create_placeholder_tab(self, text: str) -> QtWidgets.QWidget:
        """Create a placeholder tab for future functionality."""
        tab = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(tab)
        layout.setContentsMargins(12, 12, 12, 12)

        title = QtWidgets.QLabel(text)
        self._style_label(title, bold=True)
        title.setStyleSheet(title.styleSheet() + f"; font-size: 14px;")
        layout.addWidget(title)

        label = QtWidgets.QLabel(f"{text} tab will be ported in a future update.")
        self._style_label(label, color=self.colors.get("subtext", "#888888"))
        layout.addWidget(label)

        layout.addStretch()
        return tab

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

    def _style_table(self, table: QtWidgets.QTableWidget) -> None:
        """Apply consistent styling to a table."""
        table.setStyleSheet(
            f"QTableWidget {{"
            f"background-color: {self.colors['input']};"
            f"color: {self.colors['text']};"
            f"gridline-color: {self.colors['overlay']};"
            f"}}"
            f"QHeaderView::section {{"
            f"background-color: {self.colors['header']};"
            f"color: {self.colors['text']};"
            f"padding: 4px;"
            f"border: none;"
            f"}}"
            f"QTableWidget::item:selected {{"
            f"background-color: {self.colors['accent']};"
            f"color: {self.colors['bg']};"
            f"}}"
        )
        table.verticalHeader().setStyleSheet(
            f"QHeaderView {{"
            f"background-color: {self.colors['header']};"
            f"color: {self.colors['text']};"
            f"}}"
        )

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
        self._set_status("Review table refreshed")

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

    # === SDS processing ===

    def _on_select_folder(self) -> None:
        folder = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Select SDS folder", str(self.settings.paths.input_dir)
        )
        if folder:
            self._selected_sds_folder = Path(folder)
            self.folder_label.setText(str(self._selected_sds_folder))
            self._load_sds_files()

    def _load_sds_files(self) -> None:
        if not self._selected_sds_folder:
            return
        files = self._collect_sds_files(self._selected_sds_folder)
        self.sds_table.setRowCount(len(files))
        for idx, file_path in enumerate(files):
            self.sds_table.setItem(idx, 0, QtWidgets.QTableWidgetItem(file_path.name))
            self.sds_table.setItem(idx, 1, QtWidgets.QTableWidgetItem(""))
            self.sds_table.setItem(idx, 2, QtWidgets.QTableWidgetItem("Pending"))
        self.sds_table.resizeColumnsToContents()

    def _collect_sds_files(self, folder: Path) -> list[Path]:
        files: list[Path] = []
        for suffix in SUPPORTED_FORMATS:
            files.extend(folder.rglob(f"*{suffix}"))
        return sorted(files)

    def _on_process_sds(self) -> None:
        if not self._selected_sds_folder:
            QtWidgets.QMessageBox.warning(self, "No folder", "Select an SDS folder first.")
            return
        files = self._collect_sds_files(self._selected_sds_folder)
        if not files:
            QtWidgets.QMessageBox.information(self, "No files", "No supported SDS files found.")
            return
        
        # Setup UI for processing
        self.sds_progress.setValue(0)
        self.sds_table.setRowCount(len(files))
        for idx in range(len(files)):
            self.sds_table.setItem(idx, 0, QtWidgets.QTableWidgetItem(files[idx].name))
            self.sds_table.setItem(idx, 1, QtWidgets.QTableWidgetItem("-"))
            self.sds_table.setItem(idx, 2, QtWidgets.QTableWidgetItem("⏳ Pending"))
        
        self._cancel_processing = False
        self.process_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        use_rag = self.use_rag_checkbox.isChecked()
        self._set_status(f"Processing {len(files)} files…")
        self._start_task(
            self._process_sds_task,
            files,
            use_rag,
            on_result=self._on_sds_done,
            on_progress=self._on_sds_progress
        )

    def _on_sds_progress(self, percent: int, label: str) -> None:
        """Update progress bar and status during SDS processing."""
        self.sds_progress.setValue(percent)
        self._set_status(f"Processing: {label}")

    def _process_sds_task(self, files: list[Path], use_rag: bool, *, signals: WorkerSignals | None = None) -> list[tuple[str, str, str, int]]:
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
                signals.progress.emit(pct, f"{path.name} ({idx}/{total})")
                signals.message.emit(f"Processing {path.name}")
            try:
                res = processor.process(path, use_rag=use_rag)
                chemical = ""
                if res.extractions and "product_name" in res.extractions:
                    product = res.extractions.get("product_name", {})
                    chemical = product.get("value") or product.get("normalized_value") or ""
                
                # Emit individual file result for real-time table update
                if signals:
                    status_emoji = "✅" if res.status == "completed" else "⚠️" if res.status == "partial" else "❌"
                    signals.message.emit(f"{status_emoji} {path.name}: {res.status}")
                
                results.append((path.name, chemical, res.status, idx - 1))
            except Exception as exc:
                logger.error("Failed to process %s: %s", path, exc)
                if signals:
                    signals.error.emit(f"Failed: {path.name} ({exc})")
                results.append((path.name, "", "error", idx - 1))
        return results

    def _on_sds_done(self, result: object) -> None:
        self.process_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        
        if not isinstance(result, list):
            return
        
        # Update table with final results
        for fname, chemical, status, row_idx in result:
            status_display = self._format_status(status)
            self.sds_table.setItem(row_idx, 0, QtWidgets.QTableWidgetItem(fname))
            self.sds_table.setItem(row_idx, 1, QtWidgets.QTableWidgetItem(chemical or "-"))
            self.sds_table.setItem(row_idx, 2, QtWidgets.QTableWidgetItem(status_display))
        
        self.sds_table.resizeColumnsToContents()
        self.sds_progress.setValue(100)
        self._refresh_db_stats()
        
        if self._cancel_processing:
            QtWidgets.QMessageBox.information(self, "Processing stopped", f"Processed {len(result)} files before stopping.")
        else:
            QtWidgets.QMessageBox.information(self, "Processing complete", f"Processed {len(result)} files.")
    
    def _format_status(self, status: str) -> str:
        """Format status with emoji for better visual feedback."""
        status_map = {
            "completed": "✅ Completed",
            "partial": "⚠️ Partial",
            "failed": "❌ Failed",
            "error": "❌ Error",
            "pending": "⏳ Pending",
            "processing": "🔄 Processing",
        }
        return status_map.get(status.lower(), f"❓ {status}")

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
                status_text = f"✓ Connected"
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
            status_text = f"✗ Not connected"
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
