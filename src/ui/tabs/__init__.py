"""UI tabs for the RAG SDS Matrix application.

Each tab is a self-contained component that receives shared services via TabContext.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from PySide6 import QtCore, QtWidgets

from ..components import (
    refresh_checkbox_symbols,
    style_button,
    style_checkbox_symbols,
    style_label,
    style_line_edit,
    style_table,
    style_textedit,
)
from ...utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class TabContext:
    """Shared context passed to all tab instances.

    Provides access to backend services, styling, and callbacks to the main window.
    """

    # Backend services
    db: object  # DatabaseManager
    ingestion: object  # KnowledgeIngestionService
    ollama: object  # OllamaClient
    profile_router: object  # ProfileRouter
    heuristics: object  # HeuristicExtractor
    sds_extractor: object  # SDSExtractor

    # Theme and settings
    colors: dict
    app_settings: QtCore.QSettings
    thread_pool: QtCore.QThreadPool

    # Callbacks for MainWindow communication
    set_status: Callable[[str], None]
    on_error: Callable[[str], None]
    start_task: Callable


class BaseTab(QtWidgets.QWidget):
    """Base class for all tab implementations.

    Provides common functionality, styling methods, and access to shared context.
    """

    def __init__(self, context: TabContext) -> None:
        super().__init__()
        self.context = context
        self.colors = context.colors

    def _style_label(
        self,
        label: QtWidgets.QLabel,
        bold: bool = False,
        color: str | None = None,
    ) -> None:
        """Apply consistent styling to a label."""
        style_label(label, self.colors, bold=bold, color=color)

    def _style_button(self, button: QtWidgets.QPushButton) -> None:
        """Apply consistent styling to a button."""
        style_button(button, self.colors)

    def _style_checkbox_symbols(
        self,
        checkbox: QtWidgets.QCheckBox,
        label: str = "",
        *,
        font_size: int = 14,
        spacing: int = 6,
    ) -> None:
        """Render a checkbox as colored ✓/✗ text."""
        style_checkbox_symbols(
            checkbox,
            self.colors,
            label=label,
            font_size=font_size,
            spacing=spacing,
        )

    def _refresh_checkbox_symbols(self, checkbox: QtWidgets.QCheckBox) -> None:
        """Re-apply symbolic checkbox styling after state changes."""
        refresh_checkbox_symbols(checkbox)

    def _style_table(self, table: QtWidgets.QTableWidget) -> None:
        """Apply consistent styling to a table."""
        style_table(table, self.colors)

    def _style_textedit(self, textedit: QtWidgets.QTextEdit) -> None:
        """Apply consistent styling to a text edit."""
        style_textedit(textedit, self.colors)

    def _style_line_edit(self, line_edit: QtWidgets.QLineEdit) -> None:
        """Apply consistent styling to a line edit."""
        style_line_edit(line_edit, self.colors)

    def _set_status(self, message: str, *, error: bool = False) -> None:
        """Update main window status bar."""
        if error:
            self.context.on_error(message)
        else:
            self.context.set_status(message)

    def _start_task(
        self,
        fn: Callable,
        *args,
        on_result: Callable | None = None,
        on_progress: Callable | None = None,
    ) -> None:
        """Start a background task via MainWindow."""
        self.context.start_task(
            fn,
            *args,
            on_result=on_result,
            on_progress=on_progress,
        )


__all__ = [
    "TabContext",
    "BaseTab",
]
