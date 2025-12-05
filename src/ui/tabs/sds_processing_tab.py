"""Unified SDS Processing tab combining batch processing and single SDS testing.

This tab merges functionality from both sds_tab.py and regex_lab_tab.py,
providing a seamless workflow for testing extraction patterns and batch processing.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets

from . import BaseTab, TabContext
from ...config.constants import SUPPORTED_FORMATS
from ...sds.regex_catalog import get_regex_catalog
from ...sds.profile_router import ProfileRouter
from ..components import WorkerSignals


from ...utils.logger import get_logger

logger = get_logger(__name__)


class SDSProcessingTab(BaseTab):
    """Unified tab for SDS extraction testing and batch processing."""

    def __init__(self, context: TabContext) -> None:
        super().__init__(context)
        self.project_root = Path.cwd()
        self.selected_folder: Path | None = None
        self.last_folder_path: Path | None = None
        self._processing = False
        self.failed_files: dict[str, str] = {}  # filename -> failure timestamp
        self._load_persistent_config()
        self._build_ui()

    def _load_persistent_config(self) -> None:
        """Load persistent configuration from QSettings."""
        try:
            last_path = self.context.app_settings.value("sds_processing/last_folder")
            if last_path and Path(last_path).exists():
                self.last_folder_path = Path(last_path)
        except Exception as e:
            print(f"Error loading persistent config: {e}")

    def _save_persistent_config(self) -> None:
        """Save persistent configuration to QSettings."""
        try:
            val = str(self.last_folder_path) if self.last_folder_path else ""
            self.context.app_settings.setValue("sds_processing/last_folder", val)
        except Exception as e:
            print(f"Error saving persistent config: {e}")

    def _build_ui(self) -> None:
        """Build the unified SDS processing UI."""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(12, 12, 12, 12)

        # Mode selector at the top
        mode_group = QtWidgets.QGroupBox("Processing Mode")
        mode_layout = QtWidgets.QHBoxLayout(mode_group)
        
        self.mode_batch_radio = QtWidgets.QRadioButton("📁 Batch Processing")
        self.mode_batch_radio.setChecked(True)
        self.mode_batch_radio.toggled.connect(self._on_mode_changed)
        
        self.mode_test_radio = QtWidgets.QRadioButton("🔬 Single SDS Test")
        self.mode_test_radio.toggled.connect(self._on_mode_changed)
        
        mode_layout.addWidget(self.mode_batch_radio)
        mode_layout.addWidget(self.mode_test_radio)
        mode_layout.addStretch()
        
        layout.addWidget(mode_group)

        # Stacked widget to switch between modes
        self.mode_stack = QtWidgets.QStackedWidget()
        
        # Page 0: Batch Processing Mode
        self.batch_widget = self._build_batch_mode()
        self.mode_stack.addWidget(self.batch_widget)
        
        # Page 1: Single SDS Test Mode
        self.test_widget = self._build_test_mode()
        self.mode_stack.addWidget(self.test_widget)
        
        layout.addWidget(self.mode_stack)

    def _build_batch_mode(self) -> QtWidgets.QWidget:
        """Build the batch processing mode UI."""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setSpacing(10)
        layout.setContentsMargins(0, 0, 0, 0)

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
            "Include processed files",
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
        self.batch_progress = QtWidgets.QProgressBar()
        self.batch_progress.setStyleSheet(
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
        self.batch_progress.setTextVisible(True)
        progress_row.addWidget(self.batch_progress)

        self.batch_file_counter = QtWidgets.QLabel("")
        self.batch_file_counter.setStyleSheet(
            f"color: {self.colors['text']};"
            f"font-weight: 500;"
        )
        self.batch_file_counter.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
        progress_row.addWidget(self.batch_file_counter, 0, QtCore.Qt.AlignmentFlag.AlignRight)
        layout.addLayout(progress_row)

        # File table
        self.batch_table = QtWidgets.QTableWidget(0, 4)
        self.batch_table.setHorizontalHeaderLabels(["", "File", "Chemical", "Status"])
        self.batch_table.setColumnWidth(0, 30)
        self.batch_table.horizontalHeader().setStretchLastSection(True)
        self._style_table(self.batch_table)
        layout.addWidget(self.batch_table)

        # Info container
        self.batch_info_container = QtWidgets.QWidget()
        info_row = QtWidgets.QHBoxLayout(self.batch_info_container)

        self.batch_info = QtWidgets.QLabel("")
        self.batch_info.setStyleSheet(
            f"color: {self.colors['text']};"
            f"font-size: 12px;"
        )
        info_row.addWidget(self.batch_info)

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

        unselect_all_btn = QtWidgets.QPushButton("Unselect All")
        unselect_all_btn.setMaximumWidth(100)
        unselect_all_btn.setStyleSheet(select_all_btn.styleSheet())
        unselect_all_btn.clicked.connect(self._on_unselect_all_files)
        info_row.addWidget(unselect_all_btn)

        select_pending_btn = QtWidgets.QPushButton("All Pending")
        select_pending_btn.setMaximumWidth(100)
        select_pending_btn.setStyleSheet(select_all_btn.styleSheet())
        select_pending_btn.clicked.connect(self._on_select_pending_files)
        info_row.addWidget(select_pending_btn)

        info_row.addStretch()
        layout.addWidget(self.batch_info_container)
        self.batch_info_container.hide()

        return widget

    def _build_test_mode(self) -> QtWidgets.QWidget:
        """Build the single SDS test mode UI."""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setSpacing(10)
        layout.setContentsMargins(0, 0, 0, 0)

        # File picker
        file_row = QtWidgets.QHBoxLayout()
        self.test_file_input = QtWidgets.QLineEdit()
        self.test_file_input.setPlaceholderText("Select an SDS file to test extraction...")
        file_btn = QtWidgets.QPushButton("📄 Browse SDS")
        self._style_button(file_btn)
        file_btn.clicked.connect(self._on_select_test_file)
        file_row.addWidget(self.test_file_input, 3)
        file_row.addWidget(file_btn, 1)
        layout.addLayout(file_row)

        # Controls row
        ctrl_row = QtWidgets.QHBoxLayout()
        
        # Profile selector
        ctrl_row.addWidget(QtWidgets.QLabel("Profile:"))
        self.profile_combo = QtWidgets.QComboBox()
        self.profile_combo.setMinimumWidth(150)
        self.profile_combo.addItem("Auto-detect")
        for name in self.context.profile_router.list_profiles():
            self.profile_combo.addItem(name)
        ctrl_row.addWidget(self.profile_combo)

        # Field filter
        ctrl_row.addWidget(QtWidgets.QLabel("Fields (optional):"))
        self.fields_input = QtWidgets.QLineEdit()
        self.fields_input.setPlaceholderText("e.g., product_name,cas_number")
        self.fields_input.setMinimumWidth(250)
        ctrl_row.addWidget(self.fields_input)

        # RAG toggle in test mode
        self.test_use_rag_checkbox = QtWidgets.QCheckBox()
        self.test_use_rag_checkbox.setChecked(True)
        self._style_checkbox_symbols(self.test_use_rag_checkbox, "Use RAG", font_size=13)
        ctrl_row.addWidget(self.test_use_rag_checkbox)

        # Run button
        run_btn = QtWidgets.QPushButton("🔍 Extract & Test")
        self._style_button(run_btn)
        run_btn.clicked.connect(self._on_run_test)
        ctrl_row.addWidget(run_btn)
        
        # Switch to batch button
        switch_btn = QtWidgets.QPushButton("→ Use in Batch")
        switch_btn.setToolTip("Apply tested settings to batch processing")
        self._style_button(switch_btn)
        switch_btn.clicked.connect(self._on_switch_to_batch)
        ctrl_row.addWidget(switch_btn)

        ctrl_row.addStretch()
        layout.addLayout(ctrl_row)

        # Results table
        self.test_table = QtWidgets.QTableWidget()
        self.test_table.setColumnCount(4)
        self.test_table.setHorizontalHeaderLabels(["Field", "Value", "Confidence", "Source"])
        self.test_table.horizontalHeader().setStretchLastSection(True)
        self._style_table(self.test_table)
        layout.addWidget(self.test_table, 2)

        # Pattern editor section (collapsible)
        self.pattern_editor = QtWidgets.QGroupBox("Pattern Editor")
        self.pattern_editor.setCheckable(True)
        self.pattern_editor.setChecked(False)
        e_layout = QtWidgets.QGridLayout(self.pattern_editor)
        
        row = 0
        e_layout.addWidget(QtWidgets.QLabel("Profile:"), row, 0)
        self.edit_profile_input = QtWidgets.QLineEdit()
        self.edit_profile_input.setPlaceholderText("Profile name (or use selected above)")
        e_layout.addWidget(self.edit_profile_input, row, 1)
        
        row += 1
        e_layout.addWidget(QtWidgets.QLabel("Field:"), row, 0)
        self.edit_field_input = QtWidgets.QLineEdit()
        self.edit_field_input.setPlaceholderText("Field name (e.g., product_name)")
        e_layout.addWidget(self.edit_field_input, row, 1)
        
        row += 1
        e_layout.addWidget(QtWidgets.QLabel("Pattern:"), row, 0)
        self.edit_pattern_input = QtWidgets.QLineEdit()
        self.edit_pattern_input.setPlaceholderText("Regex pattern")
        e_layout.addWidget(self.edit_pattern_input, row, 1)
        
        row += 1
        e_layout.addWidget(QtWidgets.QLabel("Flags:"), row, 0)
        self.edit_flags_input = QtWidgets.QLineEdit("im")
        self.edit_flags_input.setPlaceholderText("im (case-insensitive, multiline)")
        e_layout.addWidget(self.edit_flags_input, row, 1)
        
        row += 1
        save_btn = QtWidgets.QPushButton("💾 Save Pattern")
        self._style_button(save_btn)
        save_btn.clicked.connect(self._on_save_pattern)
        reload_btn = QtWidgets.QPushButton("🔄 Reload Profiles")
        self._style_button(reload_btn)
        reload_btn.clicked.connect(self._on_reload_profiles)
        e_layout.addWidget(save_btn, row, 0)
        e_layout.addWidget(reload_btn, row, 1)
        
        layout.addWidget(self.pattern_editor, 1)

        # Status label
        self.test_status = QtWidgets.QLabel("Ready - Select a file to test extraction")
        self._style_label(self.test_status, color=self.colors.get("subtext", "#a6adc8"))
        layout.addWidget(self.test_status)

        return widget

    def _on_mode_changed(self, checked: bool) -> None:
        """Handle mode switch between batch and test."""
        if not checked:
            return
        
        if self.mode_batch_radio.isChecked():
            self.mode_stack.setCurrentIndex(0)
            self._set_status("Switched to Batch Processing mode")
        else:
            self.mode_stack.setCurrentIndex(1)
            self._set_status("Switched to Pattern Testing mode")

    # ========== Batch Processing Mode Methods ==========

    def _on_select_folder(self) -> None:
        """Handle folder selection for batch processing."""
        # Start from last selected folder or home directory
        start_dir = str(self.last_folder_path) if self.last_folder_path else str(Path.home())
        
        folder = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            "Select SDS folder",
            start_dir
        )
        if folder:
            self.selected_folder = Path(folder)
            self.last_folder_path = self.selected_folder  # Remember this path
            self._save_persistent_config()  # Persist to disk
            self.folder_label.setText(str(self.selected_folder))
            self._set_status(f"Selected folder: {self.selected_folder.name}")
            self._load_folder_contents()

    def _load_folder_contents(self) -> None:
        """Load SDS files from selected folder."""
        if not self.selected_folder:
            return
        
        files: list[Path] = []
        for suffix in SUPPORTED_FORMATS:
            files.extend(self.selected_folder.rglob(f"*{suffix}"))

        # Clear table and populate
        self.batch_table.clearContents()
        self.batch_table.setRowCount(len(files))

        # Get processed files metadata
        try:
            processed_metadata = self.context.db.get_processed_files_metadata()
            processed_names = {name for (name, _size) in processed_metadata.keys()}
        except Exception:
            processed_names = set()

        for idx, file_path in enumerate(files):
            is_processed = file_path.name in processed_names
            is_failed = file_path.name in self.failed_files

            # Column 0: Checkbox
            checkbox = QtWidgets.QCheckBox()
            checkbox.setChecked(True)
            self._style_checkbox_symbols(checkbox, font_size=16, spacing=0)
            self.batch_table.setCellWidget(idx, 0, checkbox)

            # Column 1: File name
            if is_failed:
                file_display = f"❌ {file_path.name}"
                file_item = QtWidgets.QTableWidgetItem(file_display)
                file_item.setForeground(QtGui.QColor(self.colors.get("error", "#f38ba8")))
            elif is_processed:
                file_display = f"✓ {file_path.name}"
                file_item = QtWidgets.QTableWidgetItem(file_display)
                file_item.setForeground(QtGui.QColor(self.colors.get("success", "#a6e3a1")))
            else:
                file_item = QtWidgets.QTableWidgetItem(file_path.name)
            
            # Store full path for robust retrieval
            file_item.setData(QtCore.Qt.ItemDataRole.UserRole, str(file_path))
            self.batch_table.setItem(idx, 1, file_item)

            # Column 2: Chemical (placeholder)
            self.batch_table.setItem(idx, 2, QtWidgets.QTableWidgetItem(""))

            # Column 3: Status
            if is_failed:
                status_text = f"❌ Process attempt failed on {self.failed_files[file_path.name]}"
                status_color = self.colors.get("error", "#f38ba8")
            elif is_processed:
                status_text = "✓ Processed" if not self.process_all_checkbox.isChecked() else "↻ Will reprocess"
                status_color = self.colors.get("success", "#a6e3a1") if not self.process_all_checkbox.isChecked() else self.colors.get("warning", "#f9e2af")
            else:
                status_text = "⏳ Pending"
                status_color = self.colors.get("text", "#ffffff")
            status_item = QtWidgets.QTableWidgetItem(status_text)
            status_item.setForeground(QtGui.QColor(status_color))
            self.batch_table.setItem(idx, 3, status_item)

        self.batch_table.resizeColumnsToContents()
        self.batch_info_container.show()
        self.batch_info.setText(f"Found {len(files)} files | {len(processed_names)} processed")
        self._set_status(f"Loaded {len(files)} SDS files")

    def _on_process_all_changed(self, state: int) -> None:
        """Handle process all checkbox change - only updates status display."""
        if state == QtCore.Qt.CheckState.Checked:
            self._set_status("Will reprocess selected files (including already processed)")
        else:
            self._set_status("Will skip already processed files in selection")
        
        # Update status column for processed files without changing selection
        for idx in range(self.batch_table.rowCount()):
            file_item = self.batch_table.item(idx, 1)
            status_item = self.batch_table.item(idx, 3)
            
            if file_item and status_item:
                # Check if file is processed (has ✓ marker)
                is_processed = file_item.text().startswith("✓ ")
                
                if is_processed and status_item.text().startswith("✓ "):
                    # Update status text only
                    if state == QtCore.Qt.CheckState.Checked:
                        status_item.setText("↻ Will reprocess")
                        status_item.setForeground(QtGui.QColor(self.colors.get("warning", "#f9e2af")))
                    else:
                        status_item.setText("✓ Processed")
                        status_item.setForeground(QtGui.QColor(self.colors.get("success", "#a6e3a1")))


    def _on_process_sds(self) -> None:
        """Handle SDS batch processing."""
        if not self.selected_folder:
            self._set_status("Select a folder first", error=True)
            return

        # Get selected files BEFORE starting worker thread (can't access UI from thread)
        selected_files = []
        row_count = self.batch_table.rowCount()
        logger.info(f"Scanning {row_count} rows for selection...")
        
        for idx in range(row_count):
            checkbox = self.batch_table.cellWidget(idx, 0)
            if checkbox and isinstance(checkbox, QtWidgets.QCheckBox):
                if checkbox.isChecked():
                    file_item = self.batch_table.item(idx, 1)
                    if file_item:
                        # Try retrieving from UserRole first (robust method)
                        stored_path = file_item.data(QtCore.Qt.ItemDataRole.UserRole)
                        if stored_path:
                            file_path = Path(stored_path)
                            if file_path.exists():
                                selected_files.append(file_path)
                                logger.info(f"Row {idx}: Added {file_path.name}")
                            else:
                                logger.warning(f"Row {idx}: File not found at {file_path}")
                        else:
                            # Fallback: Remove status markers from filename (fragile)
                            raw_text = file_item.text()
                            filename = raw_text.replace("✓ ", "").replace("❌ ", "")
                            file_path = self.selected_folder / filename
                            
                            if file_path.exists():
                                selected_files.append(file_path)
                                logger.info(f"Row {idx}: Added {filename} (legacy fallback)")
                            else:
                                logger.warning(f"Row {idx}: File not found at {file_path}")
                    else:
                        logger.warning(f"Row {idx}: No file item found")
                else:
                    # logger.info(f"Row {idx}: Checkbox not checked")
                    pass
            else:
                logger.warning(f"Row {idx}: Checkbox widget missing or invalid")

        if len(selected_files) == 0:
            logger.error(f"Selection failed. {row_count} rows, {len(selected_files)} selected.")
            self._set_status("Select at least one file to process", error=True)
            return

        self._set_status(f"Starting SDS processing ({len(selected_files)} files)…")
        self._processing = True
        self.process_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.batch_progress.setValue(0)

        use_rag = self.use_rag_checkbox.isChecked()
        force_reprocess = self.process_all_checkbox.isChecked()
        self._start_task(
            self._process_sds_task,
            selected_files,
            use_rag,
            force_reprocess,
            on_progress=self._on_batch_progress,
            on_result=self._on_batch_done,
        )

    def _process_sds_task(
        self, selected_files: list[Path], use_rag: bool, force_reprocess: bool, *, signals: WorkerSignals | None = None
    ) -> dict:
        """Process SDS files with error tracking."""
        from ...sds.processor import SDSProcessor
        
        processed_count = 0
        failed_count = 0
        failed_files = []
        
        total = len(selected_files)
        processor = SDSProcessor()
        
        for i, file_path in enumerate(selected_files):
            if not self._processing:
                break
            
            try:
                if signals:
                    progress = int((i / total) * 100) if total > 0 else 0
                    signals.progress.emit(progress, f"Processing {file_path.name} ({i+1}/{total})...")
                
                # Attempt to process the file using SDSProcessor with force_reprocess flag
                result = processor.process(file_path=file_path, use_rag=use_rag, force_reprocess=force_reprocess)
                
                if result and result.extractions:
                    processed_count += 1
                    # Remove from failed list if it was there
                    if file_path.name in self.failed_files:
                        del self.failed_files[file_path.name]
                    
                    # Emit success signal for UI update
                    if signals:
                        signals.data.emit({
                            'type': 'file_processed',
                            'filename': file_path.name,
                            'success': True
                        })
                else:
                    raise ValueError("No data extracted")
                    
            except Exception as e:
                failed_count += 1
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self.failed_files[file_path.name] = timestamp
                failed_files.append(f"{file_path.name} ({str(e)})")
                
                # Emit failure signal for UI update
                if signals:
                    signals.data.emit({
                        'type': 'file_processed',
                        'filename': file_path.name,
                        'success': False,
                        'error': str(e),
                        'timestamp': timestamp
                    })
                    signals.error.emit(f"Failed to process {file_path.name}: {str(e)}")
        
        if signals:
            signals.progress.emit(100, f"Complete: {processed_count} processed, {failed_count} failed")
        
        return {
            "processed": processed_count,
            "failed": failed_count,
            "failed_files": failed_files,
            "message": f"Processed {processed_count} files, {failed_count} failed"
        }

    def _on_batch_progress(self, progress: int, message: str) -> None:
        """Handle batch processing progress updates."""
        self.batch_progress.setValue(progress)
        self.batch_file_counter.setText(message)
        self._set_status(message)

    def _on_file_processed(self, data: dict) -> None:
        """Handle individual file processing completion (real-time UI update)."""
        if data.get('type') != 'file_processed':
            return
        
        filename = data.get('filename')
        success = data.get('success', False)
        
        # Find the row with this filename and update its status
        for idx in range(self.batch_table.rowCount()):
            file_item = self.batch_table.item(idx, 1)
            if file_item:
                # Check if this is the file (with or without markers)
                item_text = file_item.text().replace("✓ ", "").replace("❌ ", "")
                if item_text == filename:
                    if success:
                        # Update to success
                        file_item.setText(f"✓ {filename}")
                        file_item.setForeground(QtGui.QColor(self.colors.get("success", "#a6e3a1")))
                        
                        status_item = self.batch_table.item(idx, 3)
                        if status_item:
                            status_item.setText("✓ Processed")
                            status_item.setForeground(QtGui.QColor(self.colors.get("success", "#a6e3a1")))
                    else:
                        # Update to failed
                        file_item.setText(f"❌ {filename}")
                        file_item.setForeground(QtGui.QColor(self.colors.get("error", "#f38ba8")))
                        
                        timestamp = data.get('timestamp', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                        status_item = self.batch_table.item(idx, 3)
                        if status_item:
                            status_item.setText(f"❌ Process attempt failed on {timestamp}")
                            status_item.setForeground(QtGui.QColor(self.colors.get("error", "#f38ba8")))
                    break

    def _on_batch_done(self, result: object) -> None:
        """Handle batch processing completion."""
        self._processing = False
        self.process_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        if isinstance(result, dict):
            processed = result.get('processed', 0)
            failed = result.get('failed', 0)
            msg = f"Completed: {processed} processed, {failed} failed"
            self._set_status(msg, error=(failed > 0))
            
            # Show detailed error for failed files
            if failed > 0 and 'failed_files' in result:
                error_details = "\n".join(result['failed_files'][:5])  # Show first 5
                if len(result['failed_files']) > 5:
                    error_details += f"\n... and {len(result['failed_files']) - 5} more"
                print(f"Failed files:\n{error_details}")
        self._load_folder_contents()

    def _on_stop_processing(self) -> None:
        """Handle processing stop."""
        self._processing = False
        self.process_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self._set_status("Processing stopped by user")

    def _on_build_matrix(self) -> None:
        """Handle matrix building."""
        self._set_status("Building compatibility matrix…")
        self._start_task(self._build_matrix_task, on_result=self._on_matrix_done)

    def _build_matrix_task(self, *, signals: WorkerSignals | None = None) -> dict:
        """Build compatibility matrix in background."""
        try:
            from ...matrix.builder import MatrixBuilder
            builder = MatrixBuilder(self.context.db)
            matrix = builder.build()
            if signals:
                signals.message.emit("Matrix built successfully")
            return {"success": True, "matrix": matrix}
        except Exception as e:
            if signals:
                signals.error.emit(str(e))
            return {"success": False, "error": str(e)}

    def _on_matrix_done(self, result: object) -> None:
        """Handle matrix building completion."""
        if isinstance(result, dict) and result.get("success"):
            self._set_status("Compatibility matrix built successfully")
        else:
            self._set_status("Matrix building failed", error=True)

    def _on_export(self) -> None:
        """Handle data export."""
        path, format_filter = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export data", "", "Excel (*.xlsx);;JSON (*.json);;HTML (*.html)"
        )
        if path:
            self._set_status(f"Exporting to {Path(path).name}…")
            self._start_task(self._export_task, path, format_filter, on_result=self._on_export_done)

    def _export_task(self, path: str, format_filter: str, *, signals: WorkerSignals | None = None) -> dict:
        """Export data in background."""
        try:
            from ...matrix.exporter import MatrixExporter
            exporter = MatrixExporter(self.context.db)
            if "Excel" in format_filter:
                exporter.export_xlsx(path)
            elif "JSON" in format_filter:
                exporter.export_json(path)
            elif "HTML" in format_filter:
                exporter.export_html(path)
            if signals:
                signals.message.emit(f"Exported to {Path(path).name}")
            return {"success": True, "path": path}
        except Exception as e:
            if signals:
                signals.error.emit(str(e))
            return {"success": False, "error": str(e)}

    def _on_export_done(self, result: object) -> None:
        """Handle export completion."""
        if isinstance(result, dict) and result.get("success"):
            self._set_status(f"Export complete: {result.get('path')}")
        else:
            self._set_status("Export failed", error=True)

    def _on_select_all_files(self) -> None:
        """Select all files in the table."""
        for idx in range(self.batch_table.rowCount()):
            checkbox = self.batch_table.cellWidget(idx, 0)
            if checkbox and isinstance(checkbox, QtWidgets.QCheckBox):
                checkbox.setChecked(True)
        self._set_status("Selected all files")

    def _on_unselect_all_files(self) -> None:
        """Unselect all files in the table."""
        for idx in range(self.batch_table.rowCount()):
            checkbox = self.batch_table.cellWidget(idx, 0)
            if checkbox and isinstance(checkbox, QtWidgets.QCheckBox):
                checkbox.setChecked(False)
        self._set_status("Unselected all files")

    def _on_select_pending_files(self) -> None:
        """Select only pending (unprocessed) files."""
        for idx in range(self.batch_table.rowCount()):
            name_item = self.batch_table.item(idx, 1)
            is_processed = name_item and name_item.text().startswith("✓ ")
            checkbox = self.batch_table.cellWidget(idx, 0)
            if checkbox and isinstance(checkbox, QtWidgets.QCheckBox):
                checkbox.setChecked(not is_processed)
        self._set_status("Selected pending files")

    # ========== Single SDS Test Mode Methods ==========

    def _on_select_test_file(self) -> None:
        """Handle file selection for single SDS testing."""
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Select SDS for testing", str(self.project_root), "PDF Files (*.pdf);;All Files (*.*)"
        )
        if path:
            self.test_file_input.setText(path)
            self._set_status(f"Selected: {Path(path).name}")

    def _on_run_test(self) -> None:
        """Handle pattern test execution."""
        file_path = self.test_file_input.text().strip()
        if not file_path or not Path(file_path).exists():
            self._set_status("Select a valid SDS file first", error=True)
            self.test_status.setText("❌ No file selected")
            return

        profile_choice = self.profile_combo.currentText()
        if profile_choice == "Auto-detect":
            profile_choice = "Auto"
        
        fields_raw = self.fields_input.text().strip()
        fields = [f.strip() for f in fields_raw.split(",") if f.strip()] if fields_raw else None
        
        use_rag = self.test_use_rag_checkbox.isChecked()

        self.test_status.setText("🔄 Extracting data...")
        self._set_status(f"Testing extraction on {Path(file_path).name}…")
        
        self._start_task(
            self._test_extraction_task,
            Path(file_path),
            profile_choice,
            fields,
            use_rag,
            on_result=self._on_test_done,
        )

    def _test_extraction_task(
        self,
        file_path: Path,
        profile_choice: str,
        fields: list[str] | None,
        use_rag: bool,
        *,
        signals: WorkerSignals | None = None,
    ) -> dict:
        """Execute extraction test in background."""
        try:
            # Extract document
            doc = self.context.sds_extractor.extract_document(file_path)
            text = doc.get("text", "")
            sections = doc.get("sections", {})
            
            # Identify profile
            if profile_choice and profile_choice != "Auto":
                profile = self.context.profile_router.identify_profile(text, preferred=profile_choice)
            else:
                profile = self.context.profile_router.identify_profile(text)
            
            # Extract fields using heuristics
            results = self.context.heuristics.extract_all_fields(text, sections, profile=profile)
            
            # Filter fields if specified
            if fields:
                results = {k: v for k, v in results.items() if k in fields}
            
            if signals:
                signals.message.emit(f"Detected profile: {profile.name} | Extracted {len(results)} fields")
            
            return {
                "success": True,
                "profile": profile.name,
                "results": results,
                "file": file_path.name,
            }
        except Exception as e:
            if signals:
                signals.error.emit(str(e))
            return {"success": False, "error": str(e)}

    def _on_test_done(self, result: object) -> None:
        """Handle extraction test completion."""
        if not isinstance(result, dict):
            self.test_status.setText("❌ No results")
            return

        if not result.get("success"):
            error = result.get("error", "Unknown error")
            self.test_status.setText(f"❌ Extraction failed: {error}")
            self._set_status(f"Test failed: {error}", error=True)
            return

        profile = result.get("profile", "Unknown")
        results = result.get("results", {}) or {}
        file_name = result.get("file", "")

        # Populate results table
        rows = []
        for field, data in results.items():
            rows.append({
                "field": field,
                "value": str(data.get("value", ""))[:100],  # Truncate long values
                "confidence": f"{data.get('confidence', 0.0):.2f}",
                "source": data.get("source", ""),
            })

        self.test_table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            # Apply color coding based on confidence
            confidence_val = float(row["confidence"])
            if confidence_val >= 0.8:
                color = QtGui.QColor(self.colors.get("success", "#a6e3a1"))
            elif confidence_val >= 0.5:
                color = QtGui.QColor(self.colors.get("warning", "#f9e2af"))
            else:
                color = QtGui.QColor(self.colors.get("error", "#f38ba8"))

            field_item = QtWidgets.QTableWidgetItem(row["field"])
            value_item = QtWidgets.QTableWidgetItem(row["value"])
            conf_item = QtWidgets.QTableWidgetItem(row["confidence"])
            conf_item.setForeground(color)
            source_item = QtWidgets.QTableWidgetItem(row["source"])

            self.test_table.setItem(r, 0, field_item)
            self.test_table.setItem(r, 1, value_item)
            self.test_table.setItem(r, 2, conf_item)
            self.test_table.setItem(r, 3, source_item)

        self.test_table.resizeColumnsToContents()
        self.test_status.setText(f"✓ Profile: {profile} | {len(rows)} fields extracted from {file_name}")
        self._set_status(f"Test complete: {len(rows)} fields extracted using profile '{profile}'")

    def _on_switch_to_batch(self) -> None:
        """Switch to batch mode and apply tested settings."""
        # Get the tested file's directory
        file_path = self.test_file_input.text().strip()
        if file_path and Path(file_path).exists():
            folder = Path(file_path).parent
            self.selected_folder = folder
            self.folder_label.setText(str(folder))
            
        # Apply RAG setting from test mode
        self.use_rag_checkbox.setChecked(self.test_use_rag_checkbox.isChecked())
        
        # Switch to batch mode
        self.mode_batch_radio.setChecked(True)
        
        # Load folder contents if folder was set
        if self.selected_folder:
            self._load_folder_contents()
            self._set_status(f"Switched to batch mode with folder: {self.selected_folder.name}")
        else:
            self._set_status("Switched to batch mode - select a folder to continue")

    def _on_save_pattern(self) -> None:
        """Save regex pattern to catalog."""
        profile = self.edit_profile_input.text().strip() or self.profile_combo.currentText()
        field = self.edit_field_input.text().strip()
        pattern = self.edit_pattern_input.text().strip()
        flags = self.edit_flags_input.text().strip() or "im"

        if not profile or profile == "Auto-detect" or not field or not pattern:
            self._set_status("Profile, field, and pattern are required", error=True)
            self.test_status.setText("❌ Missing required fields for pattern save")
            return

        try:
            catalog_path = self.project_root / "data/regex/regexes.json"
            if not catalog_path.exists():
                raise FileNotFoundError(f"Catalog not found at {catalog_path}")

            with open(catalog_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            profiles = data.get("profiles", [])
            target = next((p for p in profiles if p.get("name", "").lower() == profile.lower()), None)
            
            if not target:
                target = {"name": profile, "identifiers": [], "regexes": {}}
                profiles.append(target)

            target.setdefault("regexes", {})
            target["regexes"][field] = {"pattern": pattern, "flags": flags}
            data["profiles"] = profiles
            data["version"] = f"ui-edit-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

            with open(catalog_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

            self._set_status(f"✓ Saved pattern for {profile}.{field}")
            self.test_status.setText("✓ Pattern saved to catalog")
            
            # Clear the editor fields
            self.edit_field_input.clear()
            self.edit_pattern_input.clear()
            
        except Exception as exc:
            self._set_status(f"Failed to save pattern: {exc}", error=True)
            self.test_status.setText(f"❌ Save failed: {exc}")

    def _on_reload_profiles(self) -> None:
        """Reload profiles from catalog."""
        try:
            get_regex_catalog.cache_clear()
            new_router = ProfileRouter()
            
            current = self.profile_combo.currentText()
            self.profile_combo.clear()
            self.profile_combo.addItem("Auto-detect")
            for name in new_router.list_profiles():
                self.profile_combo.addItem(name)
            
            idx = self.profile_combo.findText(current)
            if idx >= 0:
                self.profile_combo.setCurrentIndex(idx)
            
            self._set_status("✓ Profiles reloaded from catalog")
            self.test_status.setText(f"✓ Reloaded {len(new_router.list_profiles())} profiles")
            
        except Exception as exc:
            self._set_status(f"Failed to reload profiles: {exc}", error=True)
            self.test_status.setText(f"❌ Reload failed: {exc}")
