"""
Lightweight table widget for presenting tabular data in the UI.

Uses a CTkTextbox under the hood with monospaced formatting and optional headers.
"""

from __future__ import annotations

import textwrap
from typing import Iterable, Sequence

import customtkinter as ctk


class Table(ctk.CTkTextbox):
    """Simple table renderer for read-only tabular data."""

    def __init__(
        self,
        master,
        headers: Sequence[str] | None = None,
        rows: Iterable[Sequence[str]] | None = None,
        *,
        fg_color: str = "#0f172a",
        text_color: str = "#e2e8f0",
        accent_color: str = "#4fd1c5",
        font=("JetBrains Mono", 11),
        max_col_width: int = 32,
        **kwargs,
    ) -> None:
        super().__init__(
            master,
            fg_color=fg_color,
            text_color=text_color,
            font=font,
            wrap="none",
            state="disabled",
            **kwargs,
        )
        self.headers = headers or []
        self.max_col_width = max_col_width
        if rows is None:
            rows = []
        self.set_data(self.headers, rows, accent_color=accent_color)

    def set_data(
        self,
        headers: Sequence[str],
        rows: Iterable[Sequence[str]],
        *,
        accent_color: str = "#4fd1c5",
    ) -> None:
        """Render headers and rows."""
        # Normalize to strings and truncate columns
        headers = [self._fmt_cell(h) for h in headers]
        formatted_rows = []
        for row in rows:
            formatted_rows.append([self._fmt_cell(cell) for cell in row])

        # Compute column widths
        col_count = (
            len(headers)
            if headers
            else (len(formatted_rows[0]) if formatted_rows else 0)
        )
        widths = [0] * col_count
        for i, h in enumerate(headers):
            widths[i] = max(widths[i], len(h))
        for row in formatted_rows:
            for i, cell in enumerate(row):
                widths[i] = max(widths[i], len(cell))

        # Build lines
        lines: list[str] = []
        if headers:
            header_line = " | ".join(h.ljust(widths[i]) for i, h in enumerate(headers))
            lines.append(header_line)
            lines.append("-+-".join("-" * w for w in widths))
        for row in formatted_rows:
            line = " | ".join(row[i].ljust(widths[i]) for i in range(col_count))
            lines.append(line)

        # Render
        self.configure(state="normal")
        self.delete("1.0", "end")
        self.insert("1.0", "\n".join(lines) if lines else "Nenhum dado disponível.")
        self.configure(state="disabled")

    def _fmt_cell(self, value) -> str:
        """Format a cell value with max width and strip newlines."""
        text = "" if value is None else str(value)
        text = text.replace("\n", " ")
        if len(text) > self.max_col_width:
            text = textwrap.shorten(text, width=self.max_col_width, placeholder="…")
        return text
