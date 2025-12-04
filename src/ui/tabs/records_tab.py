"""Records tab for viewing extracted chemical data.

Provides a searchable table of processed SDS documents with extracted chemical information.
"""

from __future__ import annotations

from typing import Any

from PySide6 import QtCore, QtGui, QtWidgets

from . import BaseTab, TabContext
from ..components import WorkerSignals


class RecordsTab(BaseTab):
    """Tab for viewing extracted chemical records from processed SDS documents."""

    def __init__(self, context: TabContext) -> None:
        super().__init__(context)
        self._build_ui()

    def _build_ui(self) -> None:
        """Build the records tab UI."""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(12, 12, 12, 12)

        # Controls row
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
        refresh.clicked.connect(self._on_refresh)
        controls.addWidget(refresh)

        controls.addStretch()
        layout.addLayout(controls)

        # Records table
        self.records_table = QtWidgets.QTableWidget(0, 7)
        self.records_table.setHorizontalHeaderLabels(
            ["File", "Status", "Product", "CAS", "Hazard", "Confidence", "Processed"]
        )
        self.records_table.horizontalHeader().setStretchLastSection(True)
        self._style_table(self.records_table)
        layout.addWidget(self.records_table)

        # Status label
        self.records_info = QtWidgets.QLabel("Ready")
        self._style_label(self.records_info, color=self.colors.get("subtext", "#888888"))
        layout.addWidget(self.records_info)

    def _on_refresh(self) -> None:
        """Handle refresh button click."""
        limit = int(self.records_limit.value())
        self._set_status(f"Loading {limit} records…")
        self._start_task(self._records_task, limit, on_result=self._on_records_loaded)

    def _records_task(self, limit: int, *, signals: WorkerSignals | None = None) -> list[dict]:
        """Fetch records from database."""
        results = self.context.db.fetch_results(limit=limit)
        if signals:
            signals.message.emit(f"Loaded {len(results)} records")
        return results

    def _on_records_loaded(self, result: object) -> None:
        """Populate table with loaded records."""
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
        self._colorize_status_column(self.records_table)
        self.records_info.setText(f"Showing {len(result)} records")
        self._set_status("Records refreshed")

    def _populate_table(
        self,
        table: QtWidgets.QTableWidget,
        data: list[dict],
        columns: list[tuple[str, str]],
    ) -> None:
        """Populate a table with data.

        Args:
            table: The table widget to populate.
            data: List of dictionaries with data.
            columns: List of (key, header) tuples for columns.
        """
        table.setRowCount(0)
        for row_idx, row_data in enumerate(data):
            table.insertRow(row_idx)
            for col_idx, (key, _) in enumerate(columns):
                value = str(row_data.get(key, ""))
                item = QtWidgets.QTableWidgetItem(value)
                item.setFlags(item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)  # Make read-only
                table.setItem(row_idx, col_idx, item)

    def _colorize_status_column(self, table: QtWidgets.QTableWidget) -> None:
        """Color cells based on status values and missing data across ALL columns.

        Status column (col 1): Color SUCCESS green, FAILED/NOT_FOUND red
        All columns: Color "None" values (missing data) red

        Handles various status formats with case-insensitivity and whitespace normalization.
        """
        success_color = QtGui.QColor(self.colors.get("success", "#a6e3a1"))  # Catppuccin Mocha green
        error_color = QtGui.QColor(self.colors.get("error", "#f38ba8"))  # Catppuccin Mocha red

        for row in range(table.rowCount()):
            # First, color the Status column (column 1) based on status values
            status_item = table.item(row, 1)
            if status_item:
                status_text = status_item.text().strip().upper()  # Normalize: strip whitespace and uppercase

                # Check for success statuses
                if status_text in ("SUCCESS", "✓ SUCCESS", "OK", "PROCESSED"):
                    status_item.setForeground(success_color)
                # Check for error/failed statuses
                elif status_text in ("FAILED", "NOT_FOUND", "ERROR", "✗ FAILED", "✗ NOT_FOUND"):
                    status_item.setForeground(error_color)
                # Fallback: check for keywords if exact match didn't work
                elif "SUCCESS" in status_text or "OK" in status_text or "PROCESSED" in status_text:
                    status_item.setForeground(success_color)
                elif "FAILED" in status_text or "NOT_FOUND" in status_text or "ERROR" in status_text:
                    status_item.setForeground(error_color)

            # Second, color all cells in other columns that contain error indicators or missing data
            for col in range(table.columnCount()):
                # Skip Status column (already processed above)
                if col == 1:
                    continue
                item = table.item(row, col)
                if item:
                    cell_text = item.text().strip().upper()
                    # Color cells with None, empty values, or error keywords
                    if (cell_text == "NONE" or
                        cell_text == "" or
                        "NOT_FOUND" in cell_text or
                        "FAILED" in cell_text or
                        "ERROR" in cell_text):
                        item.setForeground(error_color)
