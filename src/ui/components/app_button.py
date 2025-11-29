from __future__ import annotations

import customtkinter as ctk


class AppButton(ctk.CTkButton):
    """Unified application button with consistent proportions.

    Matches tab segmented button aesthetics: medium height, rounded corners,
    bold font, and consistent padding.
    """

    def __init__(
        self,
        master,
        *,
        text: str,
        command=None,
        fg_color: str | None = None,
        text_color: str | None = None,
        hover_color: str | None = None,
        width: int = 140,
        height: int = 38,
        corner_radius: int = 10,
        font: tuple = ("Segoe UI", 12, "bold"),
        **kwargs,
    ):
        super().__init__(
            master,
            text=text,
            command=command,
            width=width,
            height=height,
            corner_radius=corner_radius,
            fg_color=fg_color,
            text_color=text_color,
            hover_color=hover_color,
            font=font,
            **kwargs,
        )
