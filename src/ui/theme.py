"""Catppuccin color theme for the UI."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True)
class CatppuccinMocha:
    """Catppuccin Mocha color palette."""

    # Base colors
    base: str = "#1e1e2e"
    mantle: str = "#181825"
    crust: str = "#11111b"

    # Surface colors
    surface0: str = "#313244"
    surface1: str = "#45475a"
    surface2: str = "#585b70"

    # Overlay colors
    overlay0: str = "#6c7086"
    overlay1: str = "#7f849c"
    overlay2: str = "#9399b2"

    # Text colors
    text: str = "#cdd6f4"
    subtext0: str = "#a6adc8"
    subtext1: str = "#bac2de"

    # Accent colors
    rosewater: str = "#f5e0dc"
    flamingo: str = "#f2cdcd"
    pink: str = "#f5c2e7"
    mauve: str = "#cba6f7"
    red: str = "#f38ba8"
    maroon: str = "#eba0ac"
    peach: str = "#fab387"
    yellow: str = "#f9e2af"
    green: str = "#a6e3a1"
    teal: str = "#94e2d5"
    sky: str = "#89dceb"
    sapphire: str = "#74c7ec"
    blue: str = "#89b4fa"
    lavender: str = "#b4befe"


@dataclass(frozen=True)
class CatppuccinLatte:
    """Catppuccin Latte (light) color palette."""

    # Base colors
    base: str = "#eff1f5"
    mantle: str = "#e6e9ef"
    crust: str = "#dce0e8"

    # Surface colors
    surface0: str = "#ccd0da"
    surface1: str = "#bcc0cc"
    surface2: str = "#acb0be"

    # Overlay colors
    overlay0: str = "#9ca0b0"
    overlay1: str = "#8c8fa1"
    overlay2: str = "#7c7f93"

    # Text colors
    text: str = "#4c4f69"
    subtext0: str = "#6c6f85"
    subtext1: str = "#5c5f77"

    # Accent colors
    rosewater: str = "#dc8a78"
    flamingo: str = "#dd7878"
    pink: str = "#ea76cb"
    mauve: str = "#8839ef"
    red: str = "#d20f39"
    maroon: str = "#e64553"
    peach: str = "#fe640b"
    yellow: str = "#df8e1d"
    green: str = "#40a02b"
    teal: str = "#179299"
    sky: str = "#04a5e5"
    sapphire: str = "#209fb5"
    blue: str = "#1e66f5"
    lavender: str = "#7287fd"


# Theme mapping for UI
COLORS_DARK: Final[dict[str, str]] = {
    # Base and surfaces
    "bg": "#0b1220",
    "surface": "#111a2d",
    "overlay": "#162238",
    "header": "#0f172a",
    "input": "#1b2740",
    # Text
    "text": "#e2e8f0",
    "subtext": "#a6adc8",
    # Accents
    "accent": "#4fd1c5",  # teal
    "primary": "#3b82f6",  # blue
    "success": "#22c55e",
    "warning": "#f59e0b",
    "error": "#f87171",
    "button_hover": "#67e8f9",
    # Tabs / trees
    "tab_inactive": "#1c2b47",
    "tab_active": "#2b3b63",
    "tab_hover": "#355080",
    "tree_bg": "#111a2d",
    "tree_fg": "#e6edf3",
    "tree_selected": "#4fd1c5",
    "tree_selected_fg": "#0b1220",
}

COLORS_LIGHT: Final[dict[str, str]] = {
    # Base and surfaces
    "bg": "#f6f8fb",
    "surface": "#e8edf5",
    "overlay": "#d9e2f0",
    "header": "#d0d9e8",
    "input": "#eef2f8",
    # Text
    "text": "#2b2b2b",
    "subtext": "#4b5563",
    # Accents
    "accent": "#0ea5e9",
    "primary": "#2563eb",
    "success": "#16a34a",
    "warning": "#d97706",
    "error": "#dc2626",
    "button_hover": "#38bdf8",
    # Tabs / trees
    "tab_inactive": "#d7e1f0",
    "tab_active": "#b8c7e6",
    "tab_hover": "#9fb5de",
    "tree_bg": "#e8edf5",
    "tree_fg": "#1f2937",
    "tree_selected": "#0ea5e9",
    "tree_selected_fg": "#f6f8fb",
}


def get_colors(theme: str = "dark") -> dict[str, str]:
    """Get color palette for specified theme.

    Args:
        theme: 'dark' or 'light'

    Returns:
        Color dictionary
    """
    return COLORS_DARK if theme == "dark" else COLORS_LIGHT
