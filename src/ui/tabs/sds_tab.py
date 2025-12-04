"""SDS tab for batch document processing.

Provides UI for processing Safety Data Sheets, building compatibility matrices,
and exporting results.
"""

from __future__ import annotations

from pathlib import Path

from PySide6 import QtCore, QtWidgets

from . import BaseTab, TabContext


class SDSTab(BaseTab):
    """Tab for processing SDS documents and managing chemical data."""

    def __init__(self, context: TabContext) -> None:
        super().__init__(context)
        self.selected_folder: Path | None = None
        self._processing = False
        self._build_ui()

    def _build_ui(self) -> None:
        """Build the SDS tab UI."""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(12, 12, 12, 12)

        # Folder selection
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

        # Controls
        controls = QtWidgets.QHBoxLayout()
        self.use_rag_checkbox = QtWidgets.QCheckBox()
        self.use_rag_checkbox.setChecked(True)
        self._style_checkbox_symbols(self.use_rag_checkbox, "Use RAG enrichment", font_size=13)
        controls.addWidget(self.use_rag_checkbox)

        self.process_all_checkbox = QtWidgets.QCheckBox()
        self.process_all_checkbox.setChecked(False)
        self._style_checkbox_symbols(
            self.process_all_checkbox,
            "Check to include all files (skip processed by default)",
            font_size=13,
        )
        self.process_all_checkbox.stateChanged.connect(self._on_process_all_changed)
        controls.addWidget(self.process_all_checkbox)

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

        # Progress bar
        progress_row = QtWidgets.QHBoxLayout()
        self.sds_progress = QtWidgets.QProgressBar()
        self.sds_progress.setStyleSheet(
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
        self.sds_progress.setTextVisible(True)
        progress_row.addWidget(self.sds_progress)

        self.sds_file_counter = QtWidgets.QLabel("")
        self.sds_file_counter.setStyleSheet(
            f"color: {self.colors['text']};"
            f"font-weight: 500;"
        )
        self.sds_file_counter.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
        progress_row.addWidget(self.sds_file_counter, 0, QtCore.Qt.AlignmentFlag.AlignRight)
        layout.addLayout(progress_row)

        # File table
        self.sds_table = QtWidgets.QTableWidget(0, 4)
        self.sds_table.setHorizontalHeaderLabels(["", "File", "Chemical", "Status"])
        self.sds_table.setColumnWidth(0, 30)
        self.sds_table.horizontalHeader().setStretchLastSection(True)
        self._style_table(self.sds_table)
        layout.addWidget(self.sds_table)

        # Info container
        self.sds_info_container = QtWidgets.QWidget()
        info_row = QtWidgets.QHBoxLayout(self.sds_info_container)

        self.sds_info = QtWidgets.QLabel("")
        self.sds_info.setStyleSheet(
            f"color: {self.colors['text']};"
            f"font-size: 12px;"
        )
        info_row.addWidget(self.sds_info)

        select_all_btn = QtWidgets.QPushButton("Select All")
        select_all_btn.setMaximumWidth(100)
        select_all_btn.setStyleSheet(
            f"QPushButton {{"
            f"background-color: {self.colors['primary']};"
            f"border: none;"
            f"border-radius: 4px;"
            f"color: {self.colors['text']};"
            f"padding: 4px 8px;"
            f"font-weight: 500;"
            f"font-size: 11px;"
            f"}}"
            f"QPushButton:hover {{"
            f"background-color: {self.colors.get('primary_hover', self.colors['button_hover'])};"
            f"}}"
            f"QPushButton:pressed {{"
            f"background-color: {self.colors['primary']};"
            f"}}"
        )
        select_all_btn.clicked.connect(self._on_select_all_files)
        info_row.addWidget(select_all_btn)

        select_pending_btn = QtWidgets.QPushButton("All Pending")
        select_pending_btn.setMaximumWidth(100)
        select_pending_btn.setStyleSheet(select_all_btn.styleSheet().replace("primary", "warning"))
        select_pending_btn.clicked.connect(self._on_select_pending_files)
        info_row.addWidget(select_pending_btn)

        info_row.addStretch()
        layout.addWidget(self.sds_info_container)
        self.sds_info_container.hide()

    # Event handlers
    def _on_select_folder(self) -> None:
        """Handle folder selection."""
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Select SDS folder")
        if folder:
            self.selected_folder = Path(folder)
            self.folder_label.setText(str(self.selected_folder))
            self._set_status(f"Selected folder: {self.selected_folder.name}")
            self._load_folder_contents()

    def _load_folder_contents(self) -> None:
        """Load SDS files from selected folder."""
        # TODO: Implement folder content loading
        self._set_status("Loading folder contents…")

    def _on_process_all_changed(self, state: int) -> None:
        """Handle process all checkbox change."""
        if state == QtCore.Qt.CheckState.Checked:
            self._set_status("Will process all files (including processed)")
        else:
            self._set_status("Will skip already processed files")

    def _on_process_sds(self) -> None:
        """Handle SDS processing."""
        if not self.selected_folder:
            self._set_status("Select a folder first", error=True)
            return
        self._set_status("Starting SDS processing…")
        self._processing = True
        self.process_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        # TODO: Implement processing task

    def _on_stop_processing(self) -> None:
        """Handle processing stop."""
        self._processing = False
        self.process_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self._set_status("Processing stopped by user")

    def _on_build_matrix(self) -> None:
        """Handle matrix building."""
        self._set_status("Building compatibility matrix…")
        # TODO: Implement matrix building

    def _on_export(self) -> None:
        """Handle data export."""
        path = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export data", "", "Excel (*.xlsx);;JSON (*.json);;HTML (*.html)"
        )
        if path[0]:
            self._set_status(f"Exporting to {Path(path[0]).name}…")
            # TODO: Implement export

    def _on_select_all_files(self) -> None:
        """Select all files in the table."""
        # TODO: Implement select all
        self._set_status("Selected all files")

    def _on_select_pending_files(self) -> None:
        """Select only pending (unprocessed) files."""
        # TODO: Implement select pending
        self._set_status("Selected pending files")
