"""Review tab for spot-checking extracted SDS data.

Provides a table for reviewing processed documents and validating extracted fields.
"""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from . import BaseTab, TabContext
from ..components import WorkerSignals


class EditableTableModel:
    """Tracks edited cells in a review table."""

    def __init__(self):
        self.original_data: dict[tuple[int, int], str] = {}
        self.edits: dict[tuple[int, int], str] = {}

    def mark_edit(self, row: int, col: int, original: str, new_value: str) -> None:
        """Track an edit to a cell."""
        key = (row, col)
        if key not in self.original_data:
            self.original_data[key] = original
        self.edits[key] = new_value

    def get_changes(self) -> dict[tuple[int, int], tuple[str, str]]:
        """Get all changes (original, new)."""
        return {k: (self.original_data[k], self.edits[k]) for k in self.edits}

    def has_changes(self) -> bool:
        """Check if any edits have been made."""
        return bool(self.edits)

    def clear(self) -> None:
        """Clear edit tracking."""
        self.edits.clear()
        self.original_data.clear()

    def undo_edits(self, table: QtWidgets.QTableWidget) -> None:
        """Revert all edits in the table."""
        for (row, col), original_value in self.original_data.items():
            if row < table.rowCount() and col < table.columnCount():
                item = table.item(row, col)
                if item:
                    item.setText(original_value)
        self.clear()


class ReviewTab(BaseTab):
    """Tab for reviewing and spot-checking extracted chemical data."""

    def __init__(self, context: TabContext) -> None:
        super().__init__(context)
        self.edit_model = EditableTableModel()
        self.current_data: list[dict] = []
        self.row_id_map: dict[int, str] = {}  # Maps row index to record ID
        self._build_ui()

    def _build_ui(self) -> None:
        """Build the review tab UI."""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(12, 12, 12, 12)

        # Info label
        info = QtWidgets.QLabel(
            "Review and edit extracted chemical data. Changes are tracked and can be saved or discarded. "
            "Click cells to edit."
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
        self.review_table.itemChanged.connect(self._on_cell_changed)
        self._style_table(self.review_table)
        layout.addWidget(self.review_table)

        # Button row: Refresh, Save, Cancel
        button_row = QtWidgets.QHBoxLayout()

        refresh = QtWidgets.QPushButton("🔄 Refresh")
        self._style_button(refresh)
        refresh.clicked.connect(self._on_refresh)
        button_row.addWidget(refresh)

        button_row.addStretch()

        self.save_btn = QtWidgets.QPushButton("💾 Save Changes")
        self.save_btn.setEnabled(False)
        self.save_btn.setStyleSheet(
            f"QPushButton {{\n"
            f"background-color: {self.colors.get('success', '#22c55e')};\n"
            f"border: none; border-radius: 4px;\n"
            f"color: {self.colors['bg']}; padding: 6px 12px; font-weight: 500;\n"
            f"}}\n"
            f"QPushButton:hover {{ background-color: {self.colors.get('success', '#22c55e')}; opacity: 0.9; }}\n"
            f"QPushButton:disabled {{ opacity: 0.5; }}"
        )
        self.save_btn.clicked.connect(self._on_save_changes)
        button_row.addWidget(self.save_btn)

        self.cancel_btn = QtWidgets.QPushButton("↶ Discard Changes")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.setStyleSheet(
            f"QPushButton {{\n"
            f"background-color: {self.colors.get('warning', '#f9e2af')};\n"
            f"border: none; border-radius: 4px;\n"
            f"color: {self.colors['bg']}; padding: 6px 12px; font-weight: 500;\n"
            f"}}\n"
            f"QPushButton:hover {{ background-color: {self.colors.get('warning', '#f9e2af')}; opacity: 0.9; }}\n"
            f"QPushButton:disabled {{ opacity: 0.5; }}"
        )
        self.cancel_btn.clicked.connect(self._on_cancel_changes)
        button_row.addWidget(self.cancel_btn)

        layout.addLayout(button_row)

        # Status label
        self.edit_status = QtWidgets.QLabel("")
        self._style_label(self.edit_status, color=self.colors.get("subtext", "#a6adc8"))
        layout.addWidget(self.edit_status)

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
        self.current_data = result
        self.edit_model.clear()
        self.row_id_map.clear()
        self._update_button_states()
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
            # Track row ID (filename as unique identifier)
            self.row_id_map[row_idx] = str(row_data.get("filename", ""))
            for col_idx, (key, _) in enumerate(columns):
                value = str(row_data.get(key, ""))
                item = QtWidgets.QTableWidgetItem(value)
                # Make cells editable except for filename (column 0)
                if col_idx == 0:
                    item.setFlags(item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)  # Filename read-only
                table.setItem(row_idx, col_idx, item)

    def _colorize_not_found(self) -> None:
        """Color 'NOT_FOUND' status cells red."""
        error_color = self.colors.get("error", "#f38ba8")
        for row in range(self.review_table.rowCount()):
            # Status is in column 1
            item = self.review_table.item(row, 1)
            if item and "NOT_FOUND" in item.text():
                item.setForeground(error_color)

    def _on_cell_changed(self, item: QtWidgets.QTableWidgetItem) -> None:
        """Handle cell content change."""
        if not item:
            return
        row = self.review_table.row(item)
        col = self.review_table.column(item)

        # Skip filename column
        if col == 0:
            return

        # Get original value
        if row < len(self.current_data):
            columns = ["filename", "status", "product_name", "cas_number", "un_number", "hazard_class"]
            if col < len(columns):
                key = columns[col]
                original = str(self.current_data[row].get(key, ""))
                new_value = item.text()

                # Track the edit
                if original != new_value:
                    self.edit_model.mark_edit(row, col, original, new_value)
                    self._update_button_states()

    def _update_button_states(self) -> None:
        """Update save/cancel button states based on edits."""
        has_changes = self.edit_model.has_changes()
        self.save_btn.setEnabled(has_changes)
        self.cancel_btn.setEnabled(has_changes)

        if has_changes:
            changes_count = len(self.edit_model.edits)
            self.edit_status.setText(f"📝 {changes_count} change(s) pending - click Save or Discard")
        else:
            self.edit_status.setText("")

    def _on_save_changes(self) -> None:
        """Handle save button click."""
        if not self.edit_model.has_changes():
            self._set_status("No changes to save")
            return

        # Confirm before saving
        changes = self.edit_model.get_changes()
        reply = QtWidgets.QMessageBox.question(
            self,
            "Confirm Save",
            f"Save {len(changes)} change(s) to the database?",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
        )

        if reply != QtWidgets.QMessageBox.StandardButton.Yes:
            return

        self._set_status("Saving changes…")
        self._start_task(
            self._save_changes_task,
            self.current_data,
            changes,
            on_result=self._on_save_done,
        )

    def _save_changes_task(
        self,
        data: list[dict],
        changes: dict,
        *,
        signals: WorkerSignals | None = None,
    ) -> dict:
        """Execute save changes in background."""
        try:
            columns = ["filename", "status", "product_name", "cas_number", "un_number", "hazard_class"]
            updated_count = 0

            for (row, col), (original, new_value) in changes.items():
                if row < len(data) and col < len(columns):
                    key = columns[col]
                    record_id = data[row].get("id") or data[row].get("filename")

                    # Update the record in database
                    try:
                        self.context.db.update_record(record_id, {key: new_value})
                        updated_count += 1
                        if signals:
                            signals.message.emit(f"Updated {updated_count}/{len(changes)} records")
                    except Exception as e:
                        if signals:
                            signals.message.emit(f"Failed to update {record_id}: {e}")

            if signals:
                signals.message.emit(f"Successfully saved {updated_count} changes")

            return {"success": True, "updated": updated_count}
        except Exception as e:
            if signals:
                signals.error.emit(str(e))
            return {"success": False, "error": str(e)}

    def _on_save_done(self, result: object) -> None:
        """Handle save completion."""
        if isinstance(result, dict) and result.get("success"):
            updated = result.get("updated", 0)
            self._set_status(f"✓ Saved {updated} changes")
            self.edit_model.clear()
            self._update_button_states()
            # Refresh to show latest data
            self._on_refresh()
        else:
            error = result.get("error") if isinstance(result, dict) else str(result)
            self._set_status(f"Save failed: {error}", error=True)

    def _on_cancel_changes(self) -> None:
        """Handle cancel button click."""
        if not self.edit_model.has_changes():
            return

        # Confirm before discarding
        reply = QtWidgets.QMessageBox.question(
            self,
            "Discard Changes?",
            f"Discard {len(self.edit_model.edits)} pending change(s)?",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
        )

        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            self.edit_model.undo_edits(self.review_table)
            self._update_button_states()
            self._set_status("Changes discarded")
