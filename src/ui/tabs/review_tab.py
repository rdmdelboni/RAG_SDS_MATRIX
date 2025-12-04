"""Review tab for spot-checking extracted SDS data.

Provides a table for reviewing processed documents and validating extracted fields.
"""

from __future__ import annotations

from PySide6 import QtWidgets

from . import BaseTab, TabContext
from ..components import WorkerSignals


class ReviewTab(BaseTab):
    """Tab for reviewing and spot-checking extracted chemical data."""

    def __init__(self, context: TabContext) -> None:
        super().__init__(context)
        self._build_ui()

    def _build_ui(self) -> None:
        """Build the review tab UI."""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(12, 12, 12, 12)

        # Info label
        info = QtWidgets.QLabel(
            "Review processed documents and spot-check extracted fields. "
            "Edits are not yet implemented in the Qt port."
        )
        self._style_label(info, color=self.colors.get("subtext", "#888888"))
        info.setWordWrap(True)
        layout.addWidget(info)

        # Review table
        self.review_table = QtWidgets.QTableWidget(0, 6)
        self.review_table.setHorizontalHeaderLabels(
            ["File", "Status", "Product", "CAS", "UN", "Hazard"]
        )
        self.review_table.horizontalHeader().setStretchLastSection(True)
        self._style_table(self.review_table)
        layout.addWidget(self.review_table)

        # Refresh button
        refresh = QtWidgets.QPushButton("🔄 Refresh")
        self._style_button(refresh)
        refresh.clicked.connect(self._on_refresh)
        layout.addWidget(refresh)

    def _on_refresh(self) -> None:
        """Handle refresh button click."""
        limit = 100
        self._set_status("Refreshing review table…")
        self._start_task(self._records_task, limit, on_result=self._on_review_loaded)

    def _records_task(self, limit: int, *, signals: WorkerSignals | None = None) -> list[dict]:
        """Fetch records from database."""
        results = self.context.db.fetch_results(limit=limit)
        if signals:
            signals.message.emit(f"Loaded {len(results)} records")
        return results

    def _on_review_loaded(self, result: object) -> None:
        """Populate review table with loaded records."""
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
        self._colorize_not_found()
        self._set_status("Review table refreshed")

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
                item.setFlags(item.flags() & ~1)  # Make read-only
                table.setItem(row_idx, col_idx, item)

    def _colorize_not_found(self) -> None:
        """Color 'NOT_FOUND' status cells red."""
        error_color = self.colors.get("error", "#f38ba8")
        for row in range(self.review_table.rowCount()):
            # Status is in column 1
            item = self.review_table.item(row, 1)
            if item and "NOT_FOUND" in item.text():
                item.setForeground(error_color)
