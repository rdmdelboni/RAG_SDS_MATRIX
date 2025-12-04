"""RAG tab for knowledge base ingestion and management.

Provides UI for adding documents, URLs, and managing the vector knowledge base.
"""

from __future__ import annotations

from pathlib import Path

from PySide6 import QtWidgets

from . import BaseTab, TabContext


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
            self, "Select documents", "", "All Files (*);;PDF (*.pdf);;Text (*.txt);;Markdown (*.md)"
        )
        if files:
            self._set_status(f"Ingesting {len(files)} files…")
            # TODO: Implement file ingestion task

    def _on_ingest_folder(self) -> None:
        """Handle folder ingestion."""
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Select folder to ingest")
        if folder:
            self._set_status(f"Ingesting folder: {folder}")
            # TODO: Implement folder ingestion task

    def _on_ingest_url(self) -> None:
        """Handle URL ingestion."""
        url = self.url_input.text().strip()
        if url:
            self._set_status(f"Ingesting URL: {url}")
            self.url_input.clear()
            # TODO: Implement URL ingestion task

    def _refresh_sources_table(self) -> None:
        """Refresh the sources table."""
        self._set_status("Refreshing sources table…")
        # TODO: Implement table refresh logic
