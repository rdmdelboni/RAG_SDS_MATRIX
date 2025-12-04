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
        """Color status cells based on status value (SUCCESS, FAILED, NOT_FOUND)."""
        success_color = QtGui.QColor(self.colors.get("success", "#a6e3a1"))  # Catppuccin Mocha green
        error_color = QtGui.QColor(self.colors.get("error", "#f38ba8"))  # Catppuccin Mocha red

        for row in range(table.rowCount()):
            # Status is in column 1
            item = table.item(row, 1)
            if item:
                status = item.text().upper()
                if "SUCCESS" in status:
                    item.setForeground(success_color)
                elif "FAILED" in status or "NOT_FOUND" in status:
                    item.setForeground(error_color)
