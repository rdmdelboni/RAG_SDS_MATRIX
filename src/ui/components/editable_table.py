"""
Enhanced editable table widget with features inspired by tkintertable.

Features:
- Row selection (single and multiple)
- Cell selection and editing
- Keyboard navigation (arrow keys, Tab, Enter)
- Row highlighting
- Sortable columns (click header to sort)
- Right-click context menu
- Double-click to edit cells
- Copy/paste support
"""

from __future__ import annotations

from typing import Any, Callable, Iterable, Sequence

import customtkinter as ctk
from tkinter import Canvas, Frame, Label, Entry, Menu, END


class EditableTable(ctk.CTkFrame):
    """Enhanced table with editing, selection, and sorting capabilities."""

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

        # Colors
        self.text_color = text_color
        self.header_color = header_color
        self.accent_color = accent_color
        self.selected_color = selected_color
        self.fg_color = fg_color

        # Fonts
        self.font = font
        self.header_font = header_font

        # Dimensions
        self.row_height = row_height
        self.min_col_width = min_col_width

        # Data
        self.headers: list[str] = list(headers) if headers else []
        self.rows: list[list[Any]] = []
        self.original_rows: list[list[Any]] = []  # For sorting
        self.col_widths: dict[int, int] = {}  # Persisted column widths
        self.user_col_widths: dict[int, int] = {}  # User-resized widths (override auto)
        
        # Resizing state
        self.resizing_col: int | None = None
        self.resize_start_x: int | None = None
        self.resize_start_width: int | None = None

        # Selection state
        self.selected_row: int | None = None
        self.selected_rows: list[int] = []
        self.selected_cell: tuple[int, int] | None = None

        # Sorting state
        self.sort_column: int | None = None
        self.sort_reverse: bool = False

        # Editing state
        self.editable = editable
        self.editing_cell: tuple[int, int] | None = None
        self.cell_entry: Entry | None = None

        # Callbacks
        self.on_cell_edit = on_cell_edit
        self.on_row_select = on_row_select
        self.on_row_double_click = on_row_double_click

        # Widgets
        self.row_widgets: dict[int, Frame] = {}

        self._create_widgets()

    def _create_widgets(self) -> None:
        """Create the table structure."""
        # Main scrollable container
        canvas_frame = ctk.CTkFrame(self, fg_color=self.fg_color)
        canvas_frame.pack(fill="both", expand=True, padx=0, pady=0)

        # Create canvas
        self.canvas = Canvas(
            canvas_frame,
            bg=self.fg_color,
            highlightthickness=0,
        )
        self.canvas.pack(side="left", fill="both", expand=True)

        # Scrollbar
        scrollbar = ctk.CTkScrollbar(canvas_frame, command=self.canvas.yview)
        scrollbar.pack(side="right", fill="y")
        self.canvas.configure(yscrollcommand=scrollbar.set)

        # Table frame
        self.table_frame = Frame(self.canvas, bg=self.fg_color)
        self.canvas.create_window(0, 0, window=self.table_frame, anchor="nw")

        # Bind events
        self.canvas.bind("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind("<Button-4>", self._on_mousewheel)
        self.canvas.bind("<Button-5>", self._on_mousewheel)
        self.table_frame.bind("<Configure>", self._on_frame_configure)

        # Keyboard bindings - bind to the frame itself, not bind_all
        self.bind("<Up>", lambda e: self._handle_arrow_key("up"))
        self.bind("<Down>", lambda e: self._handle_arrow_key("down"))
        self.bind("<Return>", self._handle_enter_key)
        self.bind("<Escape>", self._cancel_edit)
        
        # Set focus to enable keyboard events
        self.focus_set()

    def _on_frame_configure(self, event=None) -> None:
        """Update scroll region when frame changes."""
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_mousewheel(self, event) -> None:
        """Handle mouse wheel scrolling."""
        if event.num == 5 or event.delta < 0:
            self.canvas.yview_scroll(2, "units")
        elif event.num == 4 or event.delta > 0:
            self.canvas.yview_scroll(-2, "units")

    def set_data(
        self,
        headers: Sequence[str],
        rows: Iterable[Sequence[Any]],
        *,
        accent_color: str | None = None,
    ) -> None:
        """Set table data and render."""
        self.headers = [str(h) for h in headers]
        self.rows = [[cell for cell in row] for row in rows]
        self.original_rows = [row[:] for row in self.rows]  # Deep copy

        if accent_color:
            self.accent_color = accent_color

        # Clear existing
        for widget in self.table_frame.winfo_children():
            widget.destroy()
        self.row_widgets.clear()

        if not self.headers:
            return

        # Calculate widths
        self._calculate_column_widths()

        # Create header
        self._create_header_row()

        # Create rows
        for row_idx, row_data in enumerate(self.rows):
            self._create_data_row(row_idx, row_data)

    def _calculate_column_widths(self) -> None:
        """Calculate optimal column widths, preserving user resizes."""
        col_count = len(self.headers)
        content_widths = {}

        # Header widths
        for i, header in enumerate(self.headers):
            content_widths[i] = len(header) * 8

        # Content widths (sample first 50 rows)
        for row in self.rows[:50]:
            for i, cell in enumerate(row[:col_count]):
                cell_width = len(str(cell)) * 7
                if cell_width > content_widths.get(i, 0):
                    content_widths[i] = cell_width

        # Apply min/max constraints, but preserve user-resized columns
        for i in range(col_count):
            # If user manually resized this column, keep their width
            if i in self.user_col_widths:
                self.col_widths[i] = self.user_col_widths[i]
            else:
                # Otherwise calculate from content
                width = content_widths.get(i, self.min_col_width) + 20
                self.col_widths[i] = max(width, self.min_col_width)
                self.col_widths[i] = min(self.col_widths[i], 400)

    def _create_header_row(self) -> None:
        """Create sortable header row."""
        header_frame = Frame(
            self.table_frame,
            bg=self.header_color,
            height=self.row_height,
        )
        header_frame.pack(fill="x", padx=0, pady=0)

        for i, header in enumerate(self.headers):
            col_width = self.col_widths.get(i, self.min_col_width)

            col_frame = Frame(
                header_frame,
                bg=self.header_color,
                width=col_width,
                height=self.row_height,
            )
            col_frame.pack(side="left", fill="both", expand=False)
            col_frame.pack_propagate(False)

            # Header label with sort indicator
            header_text = header
            if self.sort_column == i:
                header_text += " ▼" if self.sort_reverse else " ▲"

            label = Label(
                col_frame,
                text=header_text,
                bg=self.header_color,
                fg=self.text_color,
                font=self.header_font,
                anchor="w",
                padx=10,
                cursor="hand2",
            )
            label.pack(side="left", fill="both", expand=True)

            # Click to sort
            label.bind("<Button-1>", lambda e, col=i: self._sort_by_column(col))
            
            # Resize handle (right edge of column) - wider for easier grabbing
            resize_handle = Label(
                col_frame,
                text="|",
                bg=self.accent_color,
                fg=self.text_color,
                width=1,
                cursor="sb_h_double_arrow",
                font=("Arial", 10),
            )
            resize_handle.pack(side="right", fill="y", padx=2)
            resize_handle.bind("<Button-1>", lambda e, col=i: self._start_resize(e, col))
            resize_handle.bind("<B1-Motion>", lambda e, col=i: self._do_resize(e, col))
            resize_handle.bind("<ButtonRelease-1>", lambda e: self._end_resize(e))

    def _create_data_row(self, row_idx: int, row_data: list[Any]) -> None:
        """Create a data row with selection and editing support."""
        # Alternate row colors
        row_bg = self.fg_color if row_idx % 2 == 0 else "#0a0f1b"

        row_frame = Frame(
            self.table_frame,
            bg=row_bg,
            height=self.row_height,
        )
        row_frame.pack(fill="x", padx=0, pady=0)
        self.row_widgets[row_idx] = row_frame

        # Row selection on click
        row_frame.bind("<Button-1>", lambda e, r=row_idx: self._select_row(r))
        row_frame.bind("<Double-Button-1>", lambda e, r=row_idx: self._on_double_click(r))
        row_frame.bind("<Button-3>", lambda e, r=row_idx: self._show_context_menu(e, r))

        for col_idx, cell_data in enumerate(row_data[:len(self.headers)]):
            col_width = self.col_widths.get(col_idx, self.min_col_width)

            col_frame = Frame(
                row_frame,
                bg=row_bg,
                width=col_width,
                height=self.row_height,
            )
            col_frame.pack(side="left", fill="both", expand=False)
            col_frame.pack_propagate(False)

            # Cell label
            cell_text = str(cell_data) if cell_data is not None else ""
            if len(cell_text) > 40:
                cell_text = cell_text[:37] + "…"

            label = Label(
                col_frame,
                text=cell_text,
                bg=row_bg,
                fg=self.text_color,
                font=self.font,
                anchor="w",
                padx=10,
            )
            label.pack(fill="both", expand=True)

            # Propagate events to row
            label.bind("<Button-1>", lambda e, r=row_idx: self._select_row(r))
            label.bind("<Double-Button-1>", lambda e, r=row_idx, c=col_idx: self._start_edit(r, c))
            label.bind("<Button-3>", lambda e, r=row_idx: self._show_context_menu(e, r))

    def _select_row(self, row_idx: int) -> None:
        """Select a row and highlight it."""
        # Clear previous selection
        if self.selected_row is not None and self.selected_row in self.row_widgets:
            self._unhighlight_row(self.selected_row)

        self.selected_row = row_idx
        self.selected_rows = [row_idx]

        # Highlight new selection
        self._highlight_row(row_idx)

        # Callback
        if self.on_row_select:
            self.on_row_select(row_idx)

    def _highlight_row(self, row_idx: int) -> None:
        """Highlight a row."""
        if row_idx not in self.row_widgets:
            return

        row_frame = self.row_widgets[row_idx]
        row_frame.configure(bg=self.selected_color)

        # Update all child widgets
        for child in row_frame.winfo_children():
            try:
                if hasattr(child, 'configure'):
                    child.configure(bg=self.selected_color)  # type: ignore
            except Exception:
                pass
            for subchild in child.winfo_children():
                if isinstance(subchild, Label):
                    subchild.configure(bg=self.selected_color)  # type: ignore

    def _unhighlight_row(self, row_idx: int) -> None:
        """Remove highlight from a row."""
        if row_idx not in self.row_widgets:
            return

        row_bg = self.fg_color if row_idx % 2 == 0 else "#0a0f1b"
        row_frame = self.row_widgets[row_idx]
        row_frame.configure(bg=row_bg)

        # Update all child widgets
        for child in row_frame.winfo_children():
            try:
                # Try fg_color for CTkFrame widgets, bg for standard tkinter widgets
                if hasattr(child, 'configure'):
                    if 'fg_color' in child.configure():
                        child.configure(fg_color=row_bg)  # type: ignore
                    elif 'bg' in child.configure():
                        child.configure(bg=row_bg)  # type: ignore
            except Exception:
                pass
            for subchild in child.winfo_children():
                if isinstance(subchild, Label):
                    try:
                        subchild.configure(bg=row_bg)  # type: ignore
                    except Exception:
                        pass

    def _on_double_click(self, row_idx: int) -> None:
        """Handle double-click on row."""
        if self.on_row_double_click:
            self.on_row_double_click(row_idx)

    def _start_edit(self, row_idx: int, col_idx: int) -> None:
        """Start editing a cell in a popup window."""
        if not self.editable:
            return

        self.editing_cell = (row_idx, col_idx)
        current_value = self.rows[row_idx][col_idx]
        header = self.headers[col_idx] if col_idx < len(self.headers) else f"Column {col_idx}"

        # Create popup editor window
        from tkinter import Toplevel, Button
        
        editor_window = Toplevel(self)
        editor_window.title(f"Edit {header}")
        editor_window.geometry("450x180")
        editor_window.configure(bg=self.header_color)
        editor_window.transient(self.winfo_toplevel())
        
        # Position near the table
        x = self.winfo_rootx() + 100
        y = self.winfo_rooty() + 100
        editor_window.geometry(f"+{x}+{y}")
        
        # Label
        Label(
            editor_window,
            text=f"Editing: {header}",
            bg=self.header_color,
            fg=self.text_color,
            font=self.header_font,
            pady=10,
        ).pack(fill="x")
        
        # Entry field in frame
        entry_frame = Frame(editor_window, bg=self.fg_color)
        entry_frame.pack(fill="both", expand=True, padx=15, pady=10)
        
        self.cell_entry = Entry(
            entry_frame,
            font=("JetBrains Mono", 12),
            bg="#ffffff",
            fg="#000000",
            relief="solid",
            borderwidth=2,
        )
        self.cell_entry.insert(0, str(current_value))
        self.cell_entry.select_range(0, END)
        self.cell_entry.pack(fill="both", expand=True, padx=5, pady=5, ipady=8)
        
        # Buttons
        button_frame = Frame(editor_window, bg=self.header_color)
        button_frame.pack(fill="x", padx=15, pady=10)
        
        Button(
            button_frame,
            text="✓ Save (Enter)",
            command=lambda: self._save_edit_popup(editor_window),
            bg=self.accent_color,
            fg="#000000",
            font=("JetBrains Mono", 11, "bold"),
            relief="flat",
            padx=20,
            pady=8,
            cursor="hand2",
        ).pack(side="left", padx=5)
        
        Button(
            button_frame,
            text="✗ Cancel (Esc)",
            command=lambda: self._cancel_edit_popup(editor_window),
            bg="#666666",
            fg="#ffffff",
            font=("JetBrains Mono", 11),
            relief="flat",
            padx=20,
            pady=8,
            cursor="hand2",
        ).pack(side="left", padx=5)
        
        # Bind events
        self.cell_entry.bind("<Return>", lambda e: self._save_edit_popup(editor_window))
        self.cell_entry.bind("<Escape>", lambda e: self._cancel_edit_popup(editor_window))
        
        # Update window to make it viewable, then grab focus
        editor_window.update_idletasks()
        self.cell_entry.focus_set()
        editor_window.grab_set()
        
        # Store reference
        self.editor_window = editor_window

    def _save_edit_popup(self, window) -> None:
        """Save cell edit from popup."""
        if not self.editing_cell or not self.cell_entry:
            return

        row_idx, col_idx = self.editing_cell
        new_value = self.cell_entry.get()

        # Update data
        self.rows[row_idx][col_idx] = new_value

        # Callback
        if self.on_cell_edit:
            self.on_cell_edit(row_idx, col_idx, new_value)

        # Close and refresh
        window.destroy()
        self.cell_entry = None
        self.editing_cell = None
        self._refresh_cell(row_idx, col_idx, new_value)
    
    def _cancel_edit_popup(self, window) -> None:
        """Cancel cell edit from popup."""
        window.destroy()
        self.cell_entry = None
        self.editing_cell = None

    def _save_edit(self, event=None) -> None:
        """Save cell edit (legacy)."""
        if hasattr(self, 'editor_window') and self.editor_window:
            self._save_edit_popup(self.editor_window)

    def _cancel_edit(self, event=None) -> None:
        """Cancel cell edit (legacy)."""
        if hasattr(self, 'editor_window') and self.editor_window:
            self._cancel_edit_popup(self.editor_window)
        elif self.cell_entry:
            self.cell_entry.destroy()
            self.cell_entry = None
        self.editing_cell = None

    def _refresh_cell(self, row_idx: int, col_idx: int, new_value: Any) -> None:
        """Refresh a single cell display."""
        if row_idx not in self.row_widgets:
            return

        row_frame = self.row_widgets[row_idx]
        children = [w for w in row_frame.winfo_children()]

        if col_idx >= len(children):
            return

        col_frame = children[col_idx]

        # Update label
        for child in col_frame.winfo_children():
            if isinstance(child, Label):
                cell_text = str(new_value) if new_value is not None else ""
                if len(cell_text) > 40:
                    cell_text = cell_text[:37] + "…"
                child.configure(text=cell_text)

    def _sort_by_column(self, col_idx: int) -> None:
        """Sort table by column."""
        if not self.rows:
            return

        # Toggle sort direction if same column
        if self.sort_column == col_idx:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_column = col_idx
            self.sort_reverse = False

        # Sort rows
        try:
            self.rows.sort(
                key=lambda row: (str(row[col_idx]) if row[col_idx] is not None else ""),
                reverse=self.sort_reverse,
            )
        except (IndexError, TypeError):
            pass  # Skip sorting if issues

        # Redraw
        self.set_data(self.headers, self.rows)

    def _start_resize(self, event, col_idx: int) -> None:
        """Start column resize operation."""
        self.resizing_col = col_idx
        self.resize_start_x = event.x_root
        
        # Get current width from user_col_widths or calculate default
        if col_idx in self.user_col_widths:
            self.resize_start_width = self.user_col_widths[col_idx]
        else:
            # Calculate current width based on column content
            header = self.headers[col_idx]
            max_len = len(str(header))
            for row in self.rows:
                if col_idx < len(row) and row[col_idx] is not None:
                    max_len = max(max_len, len(str(row[col_idx])))
            self.resize_start_width = min(max(max_len * 8, 80), 500)

    def _do_resize(self, event, col_idx: int) -> None:
        """Update column width during resize."""
        if self.resizing_col != col_idx:
            return
        
        # Calculate new width
        delta = event.x_root - self.resize_start_x
        new_width = max(50, self.resize_start_width + delta)  # Minimum 50px
        
        # Update user widths
        self.user_col_widths[col_idx] = new_width
        
        # Redraw to apply new width
        self.set_data(self.headers, self.rows)

    def _end_resize(self, event) -> None:
        """End column resize operation."""
        self.resizing_col = None
        self.resize_start_x = None
        self.resize_start_width = None

    def _handle_arrow_key(self, direction: str) -> None:
        """Handle arrow key navigation."""
        if self.selected_row is None:
            return

        new_row = self.selected_row

        if direction == "up" and new_row > 0:
            new_row -= 1
        elif direction == "down" and new_row < len(self.rows) - 1:
            new_row += 1

        if new_row != self.selected_row:
            self._select_row(new_row)
            # Scroll to make visible
            self._scroll_to_row(new_row)

    def _handle_enter_key(self, event=None) -> None:
        """Handle Enter key - move to next row."""
        if self.editing_cell:
            self._save_edit()
        elif self.selected_row is not None and self.selected_row < len(self.rows) - 1:
            self._select_row(self.selected_row + 1)

    def _scroll_to_row(self, row_idx: int) -> None:
        """Scroll to make a row visible."""
        if row_idx not in self.row_widgets:
            return

        row_frame = self.row_widgets[row_idx]
        row_y = row_frame.winfo_y()

        # Calculate fraction
        total_height = self.table_frame.winfo_height()
        if total_height > 0:
            fraction = row_y / total_height
            self.canvas.yview_moveto(max(0, fraction - 0.1))

    def _show_context_menu(self, event, row_idx: int) -> None:
        """Show right-click context menu."""
        self._select_row(row_idx)

        menu = Menu(self, tearoff=0)
        menu.add_command(label="Edit Row", command=lambda: self._on_double_click(row_idx))
        menu.add_separator()
        menu.add_command(label="Copy Row", command=lambda: self._copy_row(row_idx))
        menu.add_separator()
        menu.add_command(label="Select All", command=self._select_all)

        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _copy_row(self, row_idx: int) -> None:
        """Copy row data to clipboard."""
        if 0 <= row_idx < len(self.rows):
            row_text = "\t".join(str(cell) for cell in self.rows[row_idx])
            self.clipboard_clear()
            self.clipboard_append(row_text)

    def _select_all(self) -> None:
        """Select all rows."""
        self.selected_rows = list(range(len(self.rows)))
        # Highlight all
        for row_idx in self.selected_rows:
            self._highlight_row(row_idx)

    def get_selected_row_data(self) -> list[Any] | None:
        """Get data from selected row."""
        if self.selected_row is not None and 0 <= self.selected_row < len(self.rows):
            return self.rows[self.selected_row]
        return None

    def get_all_data(self) -> list[list[Any]]:
        """Get all table data."""
        return [row[:] for row in self.rows]
