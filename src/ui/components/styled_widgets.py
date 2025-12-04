"""Reusable styled widget functions.

Provides styling functions that work with color dictionaries for consistent
theming across all tabs.
"""

from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets


def style_label(
    label: QtWidgets.QLabel,
    colors: dict,
    bold: bool = False,
    color: str | None = None,
) -> None:
    """Apply consistent styling to a label.

    Args:
        label: QLabel to style
        colors: Color dictionary from theme
        bold: Whether to use bold font
        color: Override color (defaults to colors['text'])
    """
    c = color or colors["text"]
    weight = "font-weight: 700;" if bold else ""
    label.setStyleSheet(f"color: {c}; {weight}")


def style_button(button: QtWidgets.QPushButton, colors: dict) -> None:
    """Apply consistent styling to a button.

    Args:
        button: QPushButton to style
        colors: Color dictionary from theme
    """
    button.setStyleSheet(
        f"QPushButton {{"
        f"background-color: {colors['primary']};"
        f"border: none;"
        f"border-radius: 4px;"
        f"color: {colors['text']};"
        f"padding: 6px 12px;"
        f"font-weight: 500;"
        f"}}"
        f"QPushButton:hover {{"
        f"background-color: {colors.get('primary_hover', colors['button_hover'])};"
        f"}}"
        f"QPushButton:pressed {{"
        f"background-color: {colors['primary']};"
        f"}}"
    )


def style_checkbox_symbols(
    checkbox: QtWidgets.QCheckBox,
    colors: dict,
    label: str = "",
    *,
    font_size: int = 14,
    spacing: int = 6,
) -> None:
    """Render a checkbox as colored ✓/✗ text instead of the default indicator.

    Args:
        checkbox: QCheckBox to style
        colors: Color dictionary from theme
        label: Text label for the checkbox
        font_size: Font size in pixels
        spacing: Spacing in pixels
    """
    checked_color = colors.get("success", "#22c55e")
    unchecked_color = colors.get("subtext", "#9ca3af")

    def apply(state: int) -> None:
        is_checked = state == QtCore.Qt.CheckState.Checked.value
        symbol = "✓" if is_checked else "✗"
        color = checked_color if is_checked else unchecked_color
        text = f"{symbol} {label}".strip()
        checkbox.setText(text)
        checkbox.setStyleSheet(
            "QCheckBox {"
            f"color: {color};"
            "font-weight: 600;"
            f"font-size: {font_size}px;"
            f"spacing: {spacing}px;"
            "}"
            "QCheckBox::indicator {"
            "width: 0px;"
            "height: 0px;"
            "}"
        )

    checkbox._symbolic_update = apply  # type: ignore[attr-defined]
    checkbox.stateChanged.connect(apply)
    apply(checkbox.checkState().value)


def refresh_checkbox_symbols(checkbox: QtWidgets.QCheckBox) -> None:
    """Re-apply the symbolic checkbox styling after programmatic state changes.

    Args:
        checkbox: QCheckBox to refresh
    """
    updater = getattr(checkbox, "_symbolic_update", None)
    if callable(updater):
        updater(checkbox.checkState().value)


def style_table(table: QtWidgets.QTableWidget, colors: dict) -> None:
    """Apply consistent styling to a table.

    Args:
        table: QTableWidget to style
        colors: Color dictionary from theme
    """
    table.setStyleSheet(
        f"QTableWidget {{"
        f"background-color: {colors['input']};"
        f"color: {colors['text']};"
        f"gridline-color: {colors['overlay']};"
        f"}}"
        f"QHeaderView::section {{"
        f"background-color: {colors['surface']};"
        f"color: {colors['text']};"
        f"padding: 4px;"
        f"border: none;"
        f"}}"
        f"QTableWidget::item:selected {{"
        f"background-color: {colors['accent']};"
        f"color: {colors['bg']};"
        f"}}"
        f"QScrollBar:vertical {{"
        f"background-color: {colors['input']};"
        f"width: 12px;"
        f"margin: 0px;"
        f"}}"
        f"QScrollBar::handle:vertical {{"
        f"background-color: {colors['overlay']};"
        f"border-radius: 6px;"
        f"min-height: 20px;"
        f"}}"
        f"QScrollBar::handle:vertical:hover {{"
        f"background-color: {colors['subtext']};"
        f"}}"
        f"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{"
        f"border: none;"
        f"background: none;"
        f"}}"
        f"QScrollBar:horizontal {{"
        f"background-color: {colors['input']};"
        f"height: 12px;"
        f"margin: 0px;"
        f"}}"
        f"QScrollBar::handle:horizontal {{"
        f"background-color: {colors['overlay']};"
        f"border-radius: 6px;"
        f"min-width: 20px;"
        f"}}"
        f"QScrollBar::handle:horizontal:hover {{"
        f"background-color: {colors['subtext']};"
        f"}}"
        f"QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{"
        f"border: none;"
        f"background: none;"
        f"}}"
    )
    table.verticalHeader().setStyleSheet(
        f"QHeaderView {{"
        f"background-color: {colors['surface']};"
        f"color: {colors['text']};"
        f"}}"
    )
    # Style the corner button (top-left select all button)
    corner_btn = table.findChild(QtWidgets.QAbstractButton)
    if corner_btn:
        corner_btn.setStyleSheet(
            f"QAbstractButton {{"
            f"background-color: {colors['primary']};"
            f"}}"
        )


def style_textedit(textedit: QtWidgets.QTextEdit, colors: dict) -> None:
    """Apply consistent styling to a text edit.

    Args:
        textedit: QTextEdit to style
        colors: Color dictionary from theme
    """
    textedit.setStyleSheet(
        f"QTextEdit {{"
        f"background-color: {colors['input']};"
        f"color: {colors['text']};"
        f"border: 1px solid {colors['overlay']};"
        f"border-radius: 4px;"
        f"padding: 4px;"
        f"}}"
    )


def style_line_edit(line_edit: QtWidgets.QLineEdit, colors: dict) -> None:
    """Apply consistent styling to a line edit.

    Args:
        line_edit: QLineEdit to style
        colors: Color dictionary from theme
    """
    line_edit.setStyleSheet(
        f"QLineEdit {{"
        f"background-color: {colors['input']};"
        f"color: {colors['text']};"
        f"border: 1px solid {colors['overlay']};"
        f"border-radius: 4px;"
        f"padding: 6px;"
        f"}}"
    )
