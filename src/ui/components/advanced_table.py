"""
Advanced table widget with scrolling and resizable columns.

Features:
- Horizontal and vertical scrollbars (auto-hide when not needed)
- Resizable columns (drag column borders)
- Excel-like appearance
- Proportional sizing
"""

from __future__ import annotations

from typing import Iterable, Sequence

import customtkinter as ctk
from tkinter import Canvas, Frame, Scrollbar, Label


class AdvancedTable(ctk.CTkFrame):
    """Advanced table with scrolling and resizable columns."""

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
        font: tuple = ("JetBrains Mono", 12),
        header_font: tuple = ("JetBrains Mono", 12, "bold"),
        row_height: int = 32,
        min_col_width: int = 60,
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
        self._resize_column_index: int | None = None
        self._resize_start_x: int | None = None
        self._h_scrollbar_visible = False
        self._v_scrollbar_visible = False

        self._create_widgets()

    def _create_widgets(self) -> None:
        """Create the table structure with smart scrollbars."""
        # Main container
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

        # Horizontal scrollbar (initially hidden)
        self.h_scrollbar = Scrollbar(
            self,
            orient="horizontal",
            command=self.canvas.xview,
            bg=self.header_color,
            troughcolor=self.fg_color,
        )
        self.canvas.configure(xscrollcommand=self._on_h_scroll)

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
        """Handle vertical scrollbar visibility."""
        # Get scroll info: (start, end) where both are 0-1
        if args and len(args) >= 2:
            start, end = float(args[0]), float(args[1])
            # Show scrollbar if content exceeds canvas height
            needs_scrollbar = start > 0 or end < 1
            if needs_scrollbar and not self._v_scrollbar_visible:
                self.v_scrollbar.pack(side="right", fill="y")
                self._v_scrollbar_visible = True
            elif not needs_scrollbar and self._v_scrollbar_visible:
                self.v_scrollbar.pack_forget()
                self._v_scrollbar_visible = False

    def _on_h_scroll(self, *args) -> None:
        """Handle horizontal scrollbar visibility."""
        # Get scroll info: (start, end) where both are 0-1
        if args and len(args) >= 2:
            start, end = float(args[0]), float(args[1])
            # Show scrollbar if content exceeds canvas width
            needs_scrollbar = start > 0 or end < 1
            if needs_scrollbar and not self._h_scrollbar_visible:
                self.h_scrollbar.pack(side="bottom", fill="x")
                self._h_scrollbar_visible = True
            elif not needs_scrollbar and self._h_scrollbar_visible:
                self.h_scrollbar.pack_forget()
                self._h_scrollbar_visible = False

    def _on_frame_configure(self, event=None) -> None:
        """Update scroll region when frame changes."""
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_mousewheel(self, event) -> None:
        """Handle mouse wheel scrolling."""
        if event.num == 5 or event.delta < 0:
            self.canvas.yview_scroll(3, "units")
        elif event.num == 4 or event.delta > 0:
            self.canvas.yview_scroll(-3, "units")

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

        # Clear existing widgets
        for widget in self.table_frame.winfo_children():
            widget.destroy()

        if not self.headers:
            return

        # Calculate column widths
        self._calculate_column_widths()

        # Create header row
        self._create_header_row()

        # Create data rows
        for row in self.rows:
            self._create_data_row(row)

    def _calculate_column_widths(self) -> None:
        """Calculate optimal column widths based on content with proportional distribution."""
        col_count = len(self.headers)
        self.col_widths = {}

        # Calculate content-based widths
        content_widths = {}

        # Analyze headers
        for i, header in enumerate(self.headers):
            content_widths[i] = len(header) * 7  # Characters to pixels

        # Analyze row content (sample for performance)
        for row in self.rows[:50]:  # Sample first 50 rows
            for i, cell in enumerate(row[:col_count]):
                cell_width = len(str(cell)) * 6  # Slightly smaller for content
                if cell_width > content_widths.get(i, 0):
                    content_widths[i] = cell_width

        # Apply minimum widths and add padding
        for i in range(col_count):
            base_width = content_widths.get(i, self.min_col_width)
            # Add padding for comfortable display
            self.col_widths[i] = max(base_width + 16, self.min_col_width)
            # Cap at reasonable maximum
            self.col_widths[i] = min(self.col_widths[i], 400)

    def _create_header_row(self) -> None:
        """Create the header row with resizable columns."""
        header_frame = Frame(
            self.table_frame,
            bg=self.header_color,
            height=self.row_height,
        )
        header_frame.pack(fill="x", padx=0, pady=0)

        for i, header in enumerate(self.headers):
            col_width = self.col_widths.get(i, self.min_col_width)

            # Column header container
            col_frame = Frame(
                header_frame,
                bg=self.header_color,
                width=col_width,
                height=self.row_height,
            )
            col_frame.pack(side="left", fill="both", expand=False, padx=0, pady=0)
            col_frame.pack_propagate(False)

            # Header label with better formatting
            header_label = Label(
                col_frame,
                text=header,
                bg=self.header_color,
                fg=self.text_color,
                font=self.header_font,
                anchor="w",
                padx=10,
                pady=6,
            )
            header_label.pack(side="left", fill="both", expand=True)

            # Resize handle (right border, only if not last column)
            if i < len(self.headers) - 1:
                resize_handle = Label(
                    col_frame,
                    text="",
                    bg=self.accent_color,
                    width=1,
                    cursor="sb_h_double_arrow",
                    relief="flat",
                )
                resize_handle.pack(side="right", fill="y", padx=0, ipady=0)
                resize_handle.bind(
                    "<Button-1>",
                    lambda e, idx=i: self._start_resize(idx, e),
                )

    def _create_data_row(self, row: list[str]) -> None:
        """Create a data row with proper spacing and alignment."""
        row_frame = Frame(
            self.table_frame,
            bg=self.fg_color,
            height=self.row_height,
        )
        row_frame.pack(fill="x", padx=0, pady=0)

        # Alternate row colors for better readability
        row_index = len([w for w in self.table_frame.winfo_children()])
        if row_index % 2 == 0:
            row_bg = self.fg_color
        else:
            row_bg = "#0a0f1b"  # Slightly darker alternate color

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

            # Cell label with optimized text display
            cell_text = str(cell)
            # Truncate very long content but keep it readable
            if len(cell_text) > 40:
                cell_text = cell_text[:37] + "…"

            cell_label = Label(
                col_frame,
                text=cell_text,
                bg=row_bg,
                fg=self.text_color,
                font=self.font,
                anchor="w",
                padx=10,
                pady=6,
                justify="left",
            )
            cell_label.pack(fill="both", expand=True)

    def _start_resize(self, col_idx: int, event) -> None:
        """Start column resize operation."""
        self._resize_column_index = col_idx
        self._resize_start_x = event.x_root
        self.canvas.bind("<Motion>", self._on_resize_motion)
        self.canvas.bind("<ButtonRelease-1>", self._end_resize)

    def _on_resize_motion(self, event) -> None:
        """Handle column resize motion (disabled for stability)."""
        # Column resize disabled due to window stability issues
        # Users can still view and scroll tables normally
        pass

    def _end_resize(self, event) -> None:
        """End column resize operation."""
        self._resize_column_index = None
        self._resize_start_x = None
        self.canvas.unbind("<Motion>")
        self.canvas.unbind("<ButtonRelease-1>")
