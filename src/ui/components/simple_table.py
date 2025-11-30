"""
Simple, stable table widget with excellent readability.

Features:
- Large, readable fonts (16pt)
- Vertical scrollbar (auto-hide when not needed)
- Dynamic text wrapping that adapts to column width changes
- Clean, stable rendering
- No window resets
"""

from __future__ import annotations

from typing import Iterable, Sequence, Callable, List

import customtkinter as ctk
from tkinter import Canvas, Frame, Scrollbar, Label


class SimpleTable(ctk.CTkFrame):
    """Simple table with scrolling and large fonts."""

    def __init__(
        self,
        master,
        headers: Sequence[str] | None = None,
        rows: Iterable[Sequence[str]] | None = None,
        *,
        fg_color: str = "#0f172a",
        text_color: str = "#e2e8f0",
        header_color: str = "#1e293b",
        accent_color: str = "#4fd1c5",
        font: tuple = ("JetBrains Mono", 16),
        header_font: tuple = ("JetBrains Mono", 16, "bold"),
        row_height: int = 50,
        min_col_width: int = 80,
        checkbox_column: bool = False,
        on_selection_change: Callable[[List[str]], None] | None = None,
        on_row_double_click: Callable[[int], None] | None = None,
        on_cell_edit: Callable[[int, int, str], None] | None = None,
        **kwargs,
    ) -> None:
        super().__init__(master, fg_color=fg_color, **kwargs)

        self.text_color = text_color
        self.header_color = header_color
        self.accent_color = accent_color
        self.fg_color = fg_color
        self.font = font
        self.header_font = header_font
        self.row_height = row_height
        self.min_col_width = min_col_width

        self.headers: list[str] = list(headers) if headers else []
        self.rows: list[list[str]] = []
        self.col_widths: dict[int, int] = {}
        self._v_scrollbar_visible = False
        self._resizing = False
        self._resize_column_idx: int | None = None
        self._resize_start_x: int | None = None
        self._resize_start_width: int | None = None
        # Store all cell labels for dynamic updates during resize
        self._cell_labels: dict[tuple[int, int], Label] = {}  # (row, col) -> Label widget

        # Selection related
        self.checkbox_column = checkbox_column
        self.on_selection_change = on_selection_change
        self._row_selection_vars: list[ctk.BooleanVar] = []
        self._selection_suspended = False  # Prevent callback storm during bulk ops

        self.on_row_double_click = on_row_double_click
        self.on_cell_edit = on_cell_edit
        self._create_widgets()
        self._last_total_width: int | None = None

    def _create_widgets(self) -> None:
        """Create the table structure with smart scrollbars."""
        self.configure(fg_color=self.fg_color)

        # Canvas with scrollbar for content
        canvas_frame = ctk.CTkFrame(self, fg_color=self.fg_color)
        canvas_frame.pack(side="left", fill="both", expand=True, padx=0, pady=0)

        # Create canvas
        self.canvas = Canvas(
            canvas_frame,
            bg=self.fg_color,
            highlightthickness=0,
            cursor="arrow",
        )
        self.canvas.pack(side="left", fill="both", expand=True)

        # Vertical scrollbar (initially hidden)
        self.v_scrollbar = Scrollbar(
            canvas_frame,
            orient="vertical",
            command=self.canvas.yview,
            bg=self.header_color,
            troughcolor=self.fg_color,
        )
        self.canvas.configure(yscrollcommand=self._on_v_scroll)

        # Frame to hold table content
        self.table_frame = Frame(
            self.canvas,
            bg=self.fg_color,
        )
        self.canvas_window = self.canvas.create_window(
            0,
            0,
            window=self.table_frame,
            anchor="nw",
        )

        # Bind mouse wheel for scrolling
        self.canvas.bind("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind("<Button-4>", self._on_mousewheel)
        self.canvas.bind("<Button-5>", self._on_mousewheel)

        # Configure canvas scroll region
        self.table_frame.bind("<Configure>", self._on_frame_configure)

    def _on_v_scroll(self, *args) -> None:
        """Handle vertical scrollbar visibility and position updates."""
        if args and len(args) >= 2:
            start, end = float(args[0]), float(args[1])
            needs_scrollbar = start > 0 or end < 1
            if needs_scrollbar and not self._v_scrollbar_visible:
                self.v_scrollbar.pack(side="right", fill="y")
                self._v_scrollbar_visible = True
            elif not needs_scrollbar and self._v_scrollbar_visible:
                self.v_scrollbar.pack_forget()
                self._v_scrollbar_visible = False
            # Update scrollbar position
            self.v_scrollbar.set(*args)

    def _on_frame_configure(self, event=None) -> None:
        """Update scroll region when frame changes."""
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_mousewheel(self, event) -> None:
        """Handle mouse wheel scrolling."""
        try:
            if event.num == 5 or event.delta < 0:
                self.canvas.yview_scroll(1, "units")
            elif event.num == 4 or event.delta > 0:
                self.canvas.yview_scroll(-1, "units")
        except Exception:
            # Ignore scrolling errors when canvas not yet configured
            pass

    def set_data(
        self,
        headers: Sequence[str],
        rows: Iterable[Sequence[str]],
        *,
        accent_color: str | None = None,
    ) -> None:
        """Render table with headers and rows."""
        self.headers = [str(h) for h in headers]
        self.rows = [[str(cell) if cell is not None else "" for cell in row] for row in rows]

        if accent_color:
            self.accent_color = accent_color

        # Clear existing widgets and cell label references
        for widget in self.table_frame.winfo_children():
            widget.destroy()
        self._cell_labels.clear()

        if not self.headers:
            return

        # Calculate column widths
        self._calculate_column_widths()

        # Create header row
        self._create_header_row()

        # Prepare selection vars if checkbox column
        self._row_selection_vars.clear()

        # Create data rows
        for idx, row in enumerate(self.rows):
            self._create_data_row(idx, row)

        # Default: all selected when checkbox column enabled
        if self.checkbox_column and self._row_selection_vars:
            self._selection_suspended = True
            for var in self._row_selection_vars:
                var.set(True)
            self._selection_suspended = False
            self._emit_selection_change()
        # Track initial width baseline
        try:
            self._last_total_width = self.winfo_width()
        except Exception:
            self._last_total_width = None

    def _calculate_column_widths(self) -> None:
        """Calculate optimal column widths based on content."""
        col_count = len(self.headers)
        self.col_widths = {}

        content_widths = {}

        # Analyze headers
        for i, header in enumerate(self.headers):
            content_widths[i] = len(header) * 12

        # Analyze row content (sample for performance)
        for row in self.rows[:100]:
            for i, cell in enumerate(row[:col_count]):
                cell_width = len(str(cell)) * 10
                if cell_width > content_widths.get(i, 0):
                    content_widths[i] = cell_width

        # Apply minimum widths and add padding - auto-expand to content
        for i in range(col_count):
            base_width = content_widths.get(i, self.min_col_width)
            self.col_widths[i] = max(base_width + 40, self.min_col_width)
            # Special handling: checkbox column should be narrow
            if self.checkbox_column and i == 0:
                self.col_widths[i] = 70

    def _create_header_row(self) -> None:
        """Create the header row with resizable columns."""
        header_frame = Frame(
            self.table_frame,
            bg=self.header_color,
            height=self.row_height,
        )
        header_frame.pack(fill="x", padx=0, pady=0)
        self.header_frame = header_frame

        for i, header in enumerate(self.headers):
            col_width = self.col_widths.get(i, self.min_col_width)

            col_frame = Frame(
                header_frame,
                bg=self.header_color,
                width=col_width,
                height=self.row_height,
            )
            col_frame.pack(side="left", fill="both", expand=False, padx=0, pady=0)
            col_frame.pack_propagate(False)
            col_frame.col_index = i  # type: ignore[attr-defined]

            if self.checkbox_column and i == 0:
                # Master select/unselect all as a button-like label
                master_label = Label(
                    col_frame,
                    text=header or "Sel",
                    bg=self.header_color,
                    fg=self.text_color,
                    font=self.header_font,
                    anchor="w",
                    padx=12,
                    pady=8,
                    wraplength=col_width - 24,
                    cursor="hand2",
                )
                master_label.pack(side="left", fill="both", expand=True)

                def toggle_master(event=None):  # type: ignore[unused-ignore]
                    if not self._row_selection_vars:
                        return
                    all_selected = all(var.get() for var in self._row_selection_vars)
                    self._selection_suspended = True
                    for var in self._row_selection_vars:
                        var.set(not all_selected)
                    self._selection_suspended = False
                    self._emit_selection_change()

                master_label.bind("<Button-1>", toggle_master)
            else:
                header_label = Label(
                    col_frame,
                    text=header,
                    bg=self.header_color,
                    fg=self.text_color,
                    font=self.header_font,
                    anchor="w",
                    padx=12,
                    pady=8,
                    wraplength=col_width - 24,
                )
                header_label.pack(side="left", fill="both", expand=True)

            # Resize handle for all columns
            resize_handle = Label(
                col_frame,
                text="",
                bg=self.accent_color,
                width=1,
                cursor="sb_h_double_arrow",
            )
            resize_handle.pack(side="right", fill="y", padx=0)
            # Store reference for double-click detection
            resize_handle.click_count = 0  # type: ignore[attr-defined]
            resize_handle.column_idx = i  # type: ignore[attr-defined]
            resize_handle.bind("<Button-1>", self._on_handle_click)
            resize_handle.bind("<B1-Motion>", lambda e: self._on_resize_motion(e))
            resize_handle.bind("<ButtonRelease-1>", lambda e: self._end_resize(e))

    def _create_data_row(self, row_index: int, row: list[str]) -> None:
        """Create a data row."""
        row_frame = Frame(
            self.table_frame,
            bg=self.fg_color,
            height=self.row_height,
        )
        row_frame.pack(fill="x", padx=0, pady=0)

        # Alternate row colors
        row_index = len([w for w in self.table_frame.winfo_children()])
        if row_index % 2 == 0:
            row_bg = self.fg_color
        else:
            row_bg = "#0a0f1b"

        # Get the current row number (for storing in _cell_labels)
        current_row_num = len(self.rows) - len([w for w in self.table_frame.winfo_children() if w != self.header_frame])

        for i, cell in enumerate(row[: len(self.headers)]):
            col_width = self.col_widths.get(i, self.min_col_width)

            col_frame = Frame(
                row_frame,
                bg=row_bg,
                width=col_width,
                height=self.row_height,
            )
            col_frame.pack(side="left", fill="both", expand=False, padx=0, pady=0)
            col_frame.pack_propagate(False)

            if self.checkbox_column and i == 0:
                var = ctk.BooleanVar(value=False)
                cb = ctk.CTkCheckBox(
                    col_frame,
                    text="",
                    variable=var,
                    fg_color=self.accent_color,
                    text_color=self.text_color,
                    font=(self.font[0], self.font[1] - 2),
                    checkbox_width=28,
                    checkbox_height=28,
                )
                cb.pack(anchor="center", padx=4, pady=4)
                self._row_selection_vars.append(var)

                def on_var_change(*_):  # pragma: no cover - UI callback
                    if self._selection_suspended:
                        return
                    self._emit_selection_change()

                var.trace_add("write", on_var_change)
            else:
                cell_text = str(cell)
                if len(cell_text) > 100:
                    cell_text = cell_text[:97] + "…"

                cell_label = Label(
                    col_frame,
                    text=cell_text,
                    bg=row_bg,
                    fg=self.text_color,
                    font=self.font,
                    anchor="nw",
                    padx=12,
                    pady=8,
                    wraplength=max(col_width - 24, 20),
                    justify="left",
                )
                cell_label.pack(fill="both", expand=True)

                # Create unified double-click handler that prioritizes row callback over inline edit
                def _unified_double_click(_event=None, parent=col_frame, label_ref=cell_label, r=current_row_num, c=i, idx=row_index):
                    # If row double-click callback exists, prioritize it (for edit dialogs)
                    if self.on_row_double_click:
                        try:
                            self.on_row_double_click(idx)
                        except Exception:
                            pass
                    # Only do inline edit if no row callback or if it's an editable column and no row callback consumed the event
                    elif self.on_cell_edit and c >= 3 and c <= 6:
                        try:
                            current_val = label_ref.cget("text")
                            entry = ctk.CTkEntry(
                                parent,
                                font=(self.font[0], max(self.font[1]-2, 10)),
                                fg_color=self.fg_color,
                                text_color=self.text_color,
                            )
                            entry.insert(0, current_val)
                            label_ref.pack_forget()
                            entry.pack(fill="x", expand=True)

                            def _commit(_e=None):
                                new_val = entry.get()
                                # Update internal rows
                                if 0 <= r < len(self.rows) and 0 <= c < len(self.rows[r]):
                                    self.rows[r][c] = new_val
                                # Restore label
                                try:
                                    entry.pack_forget()
                                    label_ref.configure(text=new_val)
                                    label_ref.pack(fill="both", expand=True)
                                except Exception:
                                    pass
                                # Callback
                                try:
                                    if self.on_cell_edit:
                                        self.on_cell_edit(r, c, new_val)
                                except Exception:
                                    pass

                            entry.bind("<Return>", _commit)
                            entry.bind("<FocusOut>", _commit)
                            try:
                                entry.focus_set()
                                entry.icursor(len(current_val))
                            except Exception:
                                pass
                        except Exception:
                            pass

                try:
                    cell_label.bind("<Double-Button-1>", _unified_double_click)
                except Exception:
                    pass

                # Store reference to cell label for dynamic updates during resize
                self._cell_labels[(current_row_num, i)] = cell_label

    # === Selection Helpers ===
    def _emit_selection_change(self) -> None:
        if not self.checkbox_column:
            return
        if not self.on_selection_change:
            return
        selected_values = self.get_selected_values()
        try:
            self.on_selection_change(selected_values)
        except Exception:
            pass

    def get_selected_values(self) -> list[str]:
        if not self.checkbox_column:
            return []
        # File name assumed to be second column (index 1) when checkbox column enabled
        values: list[str] = []
        for idx, var in enumerate(self._row_selection_vars):
            if var.get() and idx < len(self.rows):
                # Safely get file name
                if len(self.rows[idx]) > 1:
                    values.append(self.rows[idx][1])
        return values

    def select_all(self) -> None:
        if not self.checkbox_column:
            return
        self._selection_suspended = True
        for var in self._row_selection_vars:
            var.set(True)
        self._selection_suspended = False
        self._emit_selection_change()

    def unselect_all(self) -> None:
        if not self.checkbox_column:
            return
        self._selection_suspended = True
        for var in self._row_selection_vars:
            var.set(False)
        self._selection_suspended = False
        self._emit_selection_change()

    # === Auto-fit on parent resize ===
    def auto_fit_columns(self) -> None:  # pragma: no cover - UI only
        """Adjust column widths proportionally when table width changes."""
        try:
            current_width = self.winfo_width()
            if not self.col_widths or not current_width or current_width <= 1:
                return
                
            # Initialize baseline on first call
            if self._last_total_width is None:
                self._last_total_width = current_width
                return
                
            delta = abs(current_width - self._last_total_width)
            # Ignore tiny changes to reduce unnecessary redraws
            if delta < 40:
                return
                
            ratio = current_width / max(self._last_total_width, 1)
            # Clamp ratio to reasonable bounds to avoid extreme scaling
            ratio = max(0.5, min(ratio, 2.0))
            
            # Calculate total available width (excluding checkbox column if present)
            available_width = current_width - 40  # Account for padding/scrollbar
            if self.checkbox_column:
                available_width -= 70  # Fixed checkbox column width
            
            # Update widths proportionally (skip checkbox column fixed width)
            total_flexible_width = sum(
                w for i, w in self.col_widths.items()
                if not (self.checkbox_column and i == 0)
            )
            
            if total_flexible_width > 0:
                for i, w in list(self.col_widths.items()):
                    if self.checkbox_column and i == 0:
                        continue  # Keep checkbox column fixed at 70px
                    
                    # Distribute available width proportionally
                    proportion = w / total_flexible_width
                    new_w = int(available_width * proportion)
                    
                    # Clamp to reasonable bounds
                    new_w = max(self.min_col_width, min(new_w, int(current_width * 0.7)))
                    self.col_widths[i] = new_w
            
            self._last_total_width = current_width

            # Apply updated widths - only update wraplength, not frame width
            self._update_column_wraplengths()
            
        except Exception:
            pass

    def _update_column_wraplengths(self) -> None:
        """Update wraplength for all cell labels based on current column widths."""
        try:
            # Update header labels
            if hasattr(self, 'header_frame') and self.header_frame.winfo_exists():
                header_children = self.header_frame.winfo_children()
                for i, col_frame in enumerate(header_children):
                    if i in self.col_widths:
                        new_wraplength = max(self.col_widths[i] - 24, 20)
                        for child in col_frame.winfo_children():
                            if isinstance(child, Label):
                                child.configure(wraplength=new_wraplength)
            
            # Update data row labels
            if hasattr(self, 'table_frame') and self.table_frame.winfo_exists():
                for row_frame in [
                    w for w in self.table_frame.winfo_children()
                    if w != getattr(self, 'header_frame', None)
                ]:
                    if not row_frame.winfo_exists():
                        continue
                    row_children = row_frame.winfo_children()
                    for i, col_frame in enumerate(row_children):
                        if i in self.col_widths:
                            new_wraplength = max(self.col_widths[i] - 24, 20)
                            for child in col_frame.winfo_children():
                                if isinstance(child, Label):
                                    child.configure(wraplength=new_wraplength)
        except Exception:
            pass

    def _on_handle_click(self, event) -> None:
        """Handle click on resize handle - detect double-click for auto-expand."""
        handle = event.widget
        col_idx = handle.column_idx

        # Increment click count
        handle.click_count += 1

        if handle.click_count == 1:
            # First click - schedule check for double-click
            # Cancel any previous timer
            if hasattr(handle, '_click_timer'):
                try:
                    self.after_cancel(handle._click_timer)
                except Exception:
                    pass

            # Set timer to detect if this is a single or double click
            def check_click():
                if handle.click_count >= 2:
                    # Double-click detected
                    self._auto_expand_column(col_idx)
                    handle.click_count = 0
                else:
                    # Single click - start resize
                    self._start_resize(col_idx, event)
                    handle.click_count = 0

            handle._click_timer = self.after(250, check_click)

    def _start_resize(self, col_idx: int, event) -> None:
        """Start column resize operation."""
        self._resizing = True
        self._resize_column_idx = col_idx
        self._resize_start_x = event.x_root
        self._resize_start_width = self.col_widths.get(col_idx, self.min_col_width)

    def _on_resize_motion(self, event) -> None:
        """Handle column resize motion - update width without full redraw."""
        try:
            # Only proceed if we're actively resizing
            if not self._resizing or self._resize_column_idx is None or self._resize_start_x is None:
                return

            # Prevent resize updates that are too rapid
            delta = event.x_root - self._resize_start_x

            # Only update if delta is significant (at least 2 pixels)
            if abs(delta) < 2:
                return

            new_width = max(
                self.min_col_width,
                self._resize_start_width + delta
            )
            self.col_widths[self._resize_column_idx] = new_width

            # Calculate new wraplength for text
            new_wraplength = max(new_width - 24, 20)

            # Update header column frame
            if hasattr(self, 'header_frame') and self.header_frame.winfo_exists():
                try:
                    header_children = self.header_frame.winfo_children()
                    if self._resize_column_idx < len(header_children):
                        col_frame = header_children[self._resize_column_idx]
                        if col_frame.winfo_exists():
                            # Skip direct width configure to prevent Tk callback errors
                            # Update header label wraplength
                            for child in col_frame.winfo_children():
                                if isinstance(child, Label) and child.winfo_exists():
                                    child.configure(wraplength=new_wraplength)
                except Exception:
                    pass

            # Update all data row column frames for this column
            if hasattr(self, 'table_frame') and self.table_frame.winfo_exists():
                try:
                    for row_frame in [
                        w for w in self.table_frame.winfo_children()
                        if w != self.header_frame and w.winfo_exists()
                    ]:
                        row_children = row_frame.winfo_children()
                        if self._resize_column_idx < len(row_children):
                            col_frame = row_children[self._resize_column_idx]
                            if col_frame.winfo_exists():
                                # Skip direct width configure to prevent Tk callback errors
                                # Update cell label wraplength dynamically
                                for child in col_frame.winfo_children():
                                    if isinstance(child, Label) and child.winfo_exists():
                                        child.configure(wraplength=new_wraplength)
                except Exception:
                    pass
        except Exception:
            pass

    def _end_resize(self, event) -> None:
        """End column resize operation."""
        self._resizing = False
        self._resize_column_idx = None
        self._resize_start_x = None
        self._resize_start_width = None

    def _auto_expand_column(self, col_idx: int) -> None:
        """Auto-expand column to fit maximum content size."""
        try:
            if col_idx >= len(self.headers):
                return

            # Find maximum width needed for this column
            # (Removed unused local variable 'max_width')

            # Check header width
            header = self.headers[col_idx]
            header_width = len(header) * 8 + 24  # 8px per char + padding

            # Check all data rows for maximum content width
            max_content_width = header_width
            for row in self.rows:
                if col_idx < len(row):
                    cell_text = str(row[col_idx])
                    # Account for text length: 7px per char + padding
                    cell_width = len(cell_text) * 7 + 24
                    if cell_width > max_content_width:
                        max_content_width = cell_width

            # Cap at reasonable maximum (80% of screen width)
            screen_width = self.winfo_screenwidth()
            max_allowed_width = int(screen_width * 0.8)
            new_width = min(max_content_width, max_allowed_width)
            new_width = max(new_width, self.min_col_width)

            # Update column width
            self.col_widths[col_idx] = new_width
            new_wraplength = max(new_width - 24, 20)

            # Update header column frame
            if hasattr(self, 'header_frame') and self.header_frame.winfo_exists():
                try:
                    header_children = self.header_frame.winfo_children()
                    if col_idx < len(header_children):
                        col_frame = header_children[col_idx]
                        if col_frame.winfo_exists():
                            for child in col_frame.winfo_children():
                                if isinstance(child, Label) and child.winfo_exists():
                                    child.configure(wraplength=new_wraplength)
                except Exception:
                    pass

            # Update all data row column frames
            if hasattr(self, 'table_frame') and self.table_frame.winfo_exists():
                try:
                    for row_frame in [
                        w for w in self.table_frame.winfo_children()
                        if w != self.header_frame and w.winfo_exists()
                    ]:
                        row_children = row_frame.winfo_children()
                        if col_idx < len(row_children):
                            col_frame = row_children[col_idx]
                            if col_frame.winfo_exists():
                                for child in col_frame.winfo_children():
                                    if isinstance(child, Label) and child.winfo_exists():
                                        child.configure(wraplength=new_wraplength)
                except Exception:
                    pass
        except Exception:
            pass
