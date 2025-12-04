"""RAG tab for knowledge base ingestion and management.

Provides UI for adding documents, URLs, and managing the vector knowledge base.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from PySide6 import QtCore, QtWidgets

from . import BaseTab, TabContext
from ...config.constants import SUPPORTED_FORMATS
from ...rag.ingestion_service import IngestionSummary
from ..components import WorkerSignals


class RAGTab(BaseTab):
    """Tab for managing RAG knowledge base ingestion."""

    def __init__(self, context: TabContext) -> None:
        super().__init__(context)
        self._build_ui()

    def _build_ui(self) -> None:
        """Build the RAG tab UI."""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(12, 12, 12, 12)

        # Knowledge base stats
        self.rag_stats_label = QtWidgets.QLabel("Knowledge base: --")
        self._style_label(self.rag_stats_label)
        layout.addWidget(self.rag_stats_label)

        # Buttons row
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

        # URL ingestion row
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

        # Progress bar
        progress_row = QtWidgets.QHBoxLayout()
        self.rag_progress = QtWidgets.QProgressBar()
        self.rag_progress.setStyleSheet(
            f"QProgressBar {{"
            f"background-color: {self.colors['input']};"
            f"border: 1px solid {self.colors['overlay']};"
            f"border-radius: 4px;"
            f"height: 20px;"
            f"text-align: center;"
            f"}}"
            f"QProgressBar::chunk {{"
            f"background-color: {self.colors['primary']};"
            f"border-radius: 2px;"
            f"}}"
        )
        self.rag_progress.setTextVisible(True)
        self.rag_progress.setVisible(False)
        progress_row.addWidget(self.rag_progress)

        self.rag_file_counter = QtWidgets.QLabel("")
        self.rag_file_counter.setStyleSheet(
            f"color: {self.colors['text']};"
            f"font-weight: 500;"
        )
        self.rag_file_counter.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
        progress_row.addWidget(self.rag_file_counter, 0, QtCore.Qt.AlignmentFlag.AlignRight)
        layout.addLayout(progress_row)

        # Sources table
        self.sources_table = QtWidgets.QTableWidget(0, 4)
        self.sources_table.setHorizontalHeaderLabels(["Timestamp", "Title", "Type", "Chunks"])
        self.sources_table.horizontalHeader().setStretchLastSection(True)
        self._style_table(self.sources_table)
        layout.addWidget(self.sources_table)

        # Ingestion logs
        self.rag_log = QtWidgets.QTextEdit()
        self.rag_log.setReadOnly(True)
        self.rag_log.setPlaceholderText("Ingestion logs…")
        self._style_textedit(self.rag_log)
        layout.addWidget(self.rag_log)

    # Event handlers
    def _on_ingest_files(self) -> None:
        """Handle file ingestion."""
        files, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self,
            "Select knowledge files",
            "",
            "Supported files (" + " ".join(f"*{ext}" for ext in SUPPORTED_FORMATS) + ")",
        )
        if files:
            self._set_status(f"Ingesting {len(files)} files…")
            self.rag_progress.setVisible(True)
            self.rag_progress.setValue(0)
            self._start_task(
                self._ingest_files_task,
                [Path(f) for f in files],
                on_progress=self._on_ingest_progress,
                on_result=self._on_ingest_done,
            )

    def _on_ingest_folder(self) -> None:
        """Handle folder ingestion."""
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Select folder")
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
        self.rag_progress.setVisible(True)
        self.rag_progress.setValue(0)
        self._start_task(
            self._ingest_files_task,
            files,
            on_progress=self._on_ingest_progress,
            on_result=self._on_ingest_done,
        )

    def _on_ingest_url(self) -> None:
        """Handle URL ingestion."""
        url = self.url_input.text().strip()
        if not url:
            QtWidgets.QMessageBox.warning(self, "Missing URL", "Enter a URL to ingest.")
            return
        self._set_status(f"Fetching {url}…")
        self.url_input.clear()
        self.rag_progress.setVisible(True)
        self.rag_progress.setValue(0)
        self._start_task(
            self._ingest_url_task,
            url,
            on_progress=self._on_ingest_progress,
            on_result=self._on_ingest_done,
        )

    def _ingest_files_task(
        self, files: Iterable[Path], *, signals: WorkerSignals | None = None
    ) -> IngestionSummary:
        """Ingest files into the RAG system."""
        file_list = list(files)
        total = len(file_list)

        for idx, file_path in enumerate(file_list):
            if signals:
                signals.progress.emit(int(100 * idx / total) if total > 0 else 0)
                signals.message.emit(f"Processing {file_path.name}…")

        summary = self.context.ingestion.ingest_local_files(file_list)

        if signals:
            signals.progress.emit(100)
            signals.message.emit(summary.to_message())
        return summary

    def _ingest_url_task(self, url: str, *, signals: WorkerSignals | None = None) -> IngestionSummary:
        """Ingest URL content into the RAG system."""
        if signals:
            signals.progress.emit(50)
            signals.message.emit("Fetching content…")

        summary = self.context.ingestion.ingest_url(url)

        if signals:
            signals.progress.emit(100)
            signals.message.emit(summary.to_message())
        return summary

    def _on_ingest_progress(self, progress: int, message: str) -> None:
        """Handle ingestion progress updates."""
        self.rag_progress.setValue(progress)
        self.rag_file_counter.setText(message)
        self._set_status(message)

    def _on_ingest_done(self, result: object) -> None:
        """Handle ingestion completion."""
        self.rag_progress.setVisible(False)
        if isinstance(result, IngestionSummary):
            self.rag_log.append(result.to_message())
        self._refresh_sources_table()
        self._refresh_rag_stats()

    def _refresh_rag_stats(self) -> None:
        """Update RAG statistics display."""
        stats = self.context.db.get_statistics()
        last_updated = stats.get("rag_last_updated") or "Never"
        text = f"Documents: {stats.get('rag_documents', 0)} | Chunks: {stats.get('rag_chunks', 0)} | Last updated: {last_updated}"
        self.rag_stats_label.setText(text)

    def _refresh_sources_table(self) -> None:
        """Refresh the sources table with current RAG documents."""
        try:
            sources = self.context.db.get_rag_documents()
        except Exception as exc:
            self._set_status(f"Failed to load sources: {exc}", error=True)
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
            for c, cell in enumerate(row):
                item = QtWidgets.QTableWidgetItem(cell)
                item.setFlags(item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)  # Make read-only
                self.sources_table.setItem(r, c, item)

        self._set_status(f"Sources table refreshed ({len(rows)} documents)")
