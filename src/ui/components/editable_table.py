"""
Enhanced editable table widget that uses tkintertable for reliable column resizing.
"""

from __future__ import annotations

from typing import Any, Callable, Iterable, Sequence
import tkinter as tk

import customtkinter as ctk

# Attempt to import tkintertable; if it fails (known bug using sys before import),
# provide a safe fallback that keeps the UI working.
try:
    from tkintertable import TableCanvas  # type: ignore
    from tkintertable.TableModels import TableModel  # type: ignore
    _TKINTERTABLE_AVAILABLE = True
except Exception:
    TableCanvas = None  # type: ignore
    _TKINTERTABLE_AVAILABLE = False
    # Provide a minimal stub so class definitions succeed
    
    class TableModel:  # type: ignore
        def __init__(self, *args, **kwargs):
            pass

from .simple_table import SimpleTable


class CallbackTableModel(TableModel):
    """TableModel that forwards edits to a callback."""

    def __init__(
        self,
        data: dict | None = None,
        on_cell_edit: Callable[[int, int, Any], None] | None = None,
    ) -> None:
        # Predefine attributes expected by tkintertable.TableModel.setupModel
        # before invoking the base initializer to avoid AttributeError.
        self.columnNames: list[str] = []
        self.columnlabels: dict[str, str] = {}
        self.rows: int = 0
        self.columns: int = 0
        super().__init__(newdict=data)
        self._on_cell_edit = on_cell_edit

    def setValueAt(self, value, rowIndex, columnIndex):  # noqa: N802 (library signature)
        """Invoke the base setter and then notify the edit callback."""
        super().setValueAt(value, rowIndex, columnIndex)
        if self._on_cell_edit:
            try:
                self._on_cell_edit(rowIndex, columnIndex, value)
            except Exception:
                # Keep the table responsive even if the callback fails
                pass


class EditableTable(ctk.CTkFrame):
    """Editable table widget with tkintertable backend and robust fallback.

    If tkintertable cannot be imported, falls back to `SimpleTable` with
    a compatible API for the parts used by the app.
    """

    def __init__(
        self,
        master,
        headers: Sequence[str] | None = None,
        rows: Iterable[Sequence[Any]] | None = None,
        *,
        fg_color: str = "#0f172a",
        text_color: str = "#e2e8f0",
        header_color: str = "#1e293b",
        accent_color: str = "#4fd1c5",
        selected_color: str = "#334155",
        font: tuple = ("JetBrains Mono", 11),
        header_font: tuple = ("JetBrains Mono", 11, "bold"),
        row_height: int = 30,
        min_col_width: int = 80,
        editable: bool = True,
        on_cell_edit: Callable[[int, int, Any], None] | None = None,
        on_row_select: Callable[[int], None] | None = None,
        on_row_double_click: Callable[[int], None] | None = None,
        **kwargs,
    ) -> None:
        super().__init__(master, fg_color=fg_color, **kwargs)

        self.font = font
        self.header_font = header_font
        self.on_cell_edit = on_cell_edit
        self.on_row_select = on_row_select
        self.on_row_double_click = on_row_double_click

        self.fg_color = fg_color
        self.text_color = text_color
        self.header_color = header_color
        self.selected_color = selected_color or accent_color
        self.min_col_width = min_col_width

        headers_list = list(headers) if headers else []
        rows_list = [list(r) for r in rows] if rows else []

        # CustomTkinter restricts bind_all, which tkintertable uses.
        # To avoid runtime errors, use tkintertable only when not hosted
        # under a CustomTkinter widget hierarchy.
        using_ctk = isinstance(master, ctk.CTkBaseClass) if hasattr(ctk, "CTkBaseClass") else isinstance(master, ctk.CTkFrame)
        use_tkintertable = _TKINTERTABLE_AVAILABLE and not using_ctk
        self._use_tkintertable = use_tkintertable

        if use_tkintertable:
            self.model = self._build_model(headers_list, rows_list)

            # Use a native tkinter Frame to host TableCanvas to avoid
            # customtkinter's bind_all restriction.
            self._tk_frame = tk.Frame(self)
            self._tk_frame.pack(fill="both", expand=True)

            self.table = TableCanvas(
                self._tk_frame,
                model=self.model,
                read_only=not editable,
                rowheight=row_height,
                cellwidth=self.min_col_width,
                thefont=self.font,
                rowheaderwidth=50,
                cellbackgr=self.fg_color,
                entrybackgr=self.fg_color,
                rowselectedcolor=self.selected_color,
                colselectedcolor=self.selected_color,
                selectedcolor=self.selected_color,
                grid_color=self.header_color,
            )

            self.table.show()
            self.table.thefont = self.font
            self.table.tablecolheader.thefont = self.header_font
            self._apply_theme()
            self._bind_events()

            if headers_list or rows_list:
                self._auto_resize_columns()
        else:
            # Fallback: use SimpleTable with a similar interface
            self.model = None  # type: ignore
            self.table = SimpleTable(
                self,
                headers=headers_list,
                rows=rows_list,
                fg_color=fg_color,
                text_color=text_color,
                header_color=header_color,
                accent_color=accent_color,
                font=font,
                header_font=header_font,
                row_height=row_height,
                on_row_double_click=self.on_row_double_click,
                on_cell_edit=self.on_cell_edit,
            )
            self.table.pack(fill="both", expand=True)

    def _build_model(
        self,
        headers: Sequence[str],
        rows: Sequence[Sequence[Any]],
    ) -> CallbackTableModel:
        """Create a model with the provided data and callbacks wired up."""
        if not _TKINTERTABLE_AVAILABLE:
            # No model backend when falling back to SimpleTable
            return None  # type: ignore

        formatted = self._format_data(headers, rows)
        model = CallbackTableModel(
            formatted if formatted else None,
            on_cell_edit=self._handle_cell_edit if self.on_cell_edit else None,
        )

        if not formatted and headers:
            for header in headers:
                model.addColumn(header)

        if headers:
            model.columnNames = list(headers)
            model.columnlabels = {header: header for header in headers}

        return model

    def _bind_events(self) -> None:
        """Attach selection and double-click callbacks without overriding defaults."""
        if self._use_tkintertable:
            self.table.bind("<ButtonRelease-1>", self._handle_row_click, add="+")
            self.table.bind("<Double-Button-1>", self._handle_double_click, add="+")
            self._bind_row_header_event()

    def _bind_row_header_event(self) -> None:
        """Keep row-header clicks in sync with the selection callback."""
        if _TKINTERTABLE_AVAILABLE and hasattr(self.table, "tablerowheader"):
            self.table.tablerowheader.bind("<ButtonRelease-1>", self._handle_row_click, add="+")

    def _apply_theme(self) -> None:
        """Apply basic coloring to match the surrounding CTk theme."""
        if _TKINTERTABLE_AVAILABLE:
            try:
                self.table.configure(bg=self.fg_color)
                self.table.tablecolheader.configure(bg=self.header_color)
                self.table.tablerowheader.configure(bg=self.header_color)
            except Exception:
                pass

            self.table.rowselectedcolor = self.selected_color
            self.table.colselectedcolor = self.selected_color
            self.table.selectedcolor = self.selected_color
            self.table.grid_color = self.header_color
            self.table.cellbackgr = self.fg_color
            self.table.entrybackgr = self.fg_color

    def _format_data(
        self,
        headers: Sequence[str] | None,
        rows: Iterable[Sequence[Any]] | None,
    ) -> dict:
        """Convert headers and rows to the dict format required by tkintertable."""
        if not headers or not rows:
            return {}

        data = {}
        for i, row in enumerate(rows):
            data[f"rec{i}"] = {header: cell for header, cell in zip(headers, row)}
        return data

    def _auto_resize_columns(self) -> None:
        """Resize columns to fit their content using tkintertable helpers."""
        if _TKINTERTABLE_AVAILABLE:
            try:
                self.table.autoResizeColumns()
                for col_name in self.model.columnNames:
                    current = self.model.columnwidths.get(col_name, self.table.cellwidth)
                    self.model.columnwidths[col_name] = max(current, self.min_col_width)
                self.table.redraw()
            except Exception:
                # Fail silently to keep the UI responsive
                pass

    def set_data(
        self,
        headers: Sequence[str],
        rows: Iterable[Sequence[Any]],
        *,
        accent_color: str | None = None,
    ) -> None:
        """Replace table data and refresh sizing."""
        if accent_color:
            self.selected_color = accent_color

        rows_list = [list(r) for r in rows] if rows else []
        if self._use_tkintertable:
            self.model = self._build_model(list(headers), rows_list)
            self.table.updateModel(self.model)
            self.table.thefont = self.font
            self.table.tablecolheader.thefont = self.header_font
            self._bind_row_header_event()
            self._apply_theme()
            self._auto_resize_columns()
        else:
            # Fallback path delegates to SimpleTable
            self.table.set_data(headers=list(headers), rows=rows_list)

    def get_selected_row_data(self) -> list[Any] | None:
        """Get data from the currently selected row."""
        if _TKINTERTABLE_AVAILABLE:
            selected_row_index = self.table.getSelectedRow()
            if selected_row_index is None or selected_row_index < 0:
                return None

            return [
                self.model.getValueAt(selected_row_index, col_idx)
                for col_idx in range(self.model.getColumnCount())
            ]
        else:
            return self.table.get_selected_row_data()

    def get_all_data(self) -> list[list[Any]]:
        """Get all table data in display order."""
        if _TKINTERTABLE_AVAILABLE:
            data: list[list[Any]] = []
            for row_idx in range(self.model.getRowCount()):
                data.append(
                    [
                        self.model.getValueAt(row_idx, col_idx)
                        for col_idx in range(self.model.getColumnCount())
                    ]
                )
            return data
        else:
            return self.table.get_all_data()

    def bind_column_double_click(self, col_idx: int, callback: Callable[[int], None]) -> None:
        """Bind double-click handler for a specific column.

        Works in SimpleTable fallback; no-op in tkintertable mode (already handles row double-clicks).
        """
        if getattr(self, "_use_tkintertable", False):
            # Rely on on_row_double_click provided at construction
            return
        # SimpleTable: attach handler to cells in the given column
        try:
            cell_labels = getattr(self.table, "_cell_labels", {})
            for (row, col), label in list(cell_labels.items()):
                if col == col_idx:
                    try:
                        def _handler(_event=None, r=row):
                            try:
                                callback(r)
                            except Exception:
                                pass
                        label.bind("<Double-Button-1>", _handler)
                        label.bind("<Button-1>", _handler)  # single click fallback
                    except Exception:
                        continue
        except Exception:
            pass

    def _handle_row_click(self, event) -> None:
        """Handle row selection callback without breaking default behavior."""
        if not self.on_row_select:
            return

        if _TKINTERTABLE_AVAILABLE:
            row = self.table.getSelectedRow()
            if row is not None and 0 <= row < self.model.getRowCount():
                self.on_row_select(row)
        else:
            # SimpleTable handles selection callbacks internally
            pass

    def _handle_double_click(self, event) -> None:
        """Handle double click for editing or callback."""
        if not self.on_row_double_click:
            return

        if _TKINTERTABLE_AVAILABLE:
            row = self.table.get_row_clicked(event)
            if row is not None and 0 <= row < self.model.getRowCount():
                self.on_row_double_click(row)
        else:
            # SimpleTable handles double-clicks internally when supported
            pass

    def _handle_cell_edit(self, row: int, col: int, new_value: Any) -> None:
        """Callback when a cell is edited."""
        if self.on_cell_edit:
            self.on_cell_edit(row, col, new_value)
