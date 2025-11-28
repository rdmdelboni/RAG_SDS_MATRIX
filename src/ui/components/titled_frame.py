"""
A reusable titled frame component.
"""

import customtkinter as ctk


class TitledFrame(ctk.CTkFrame):
    """
    A class to create a titled frame
    """

    def __init__(self, parent, title, **kwargs):
        super().__init__(parent, **kwargs)

        self.title_label = ctk.CTkLabel(
            self, text=title, font=("JetBrains Mono", 14, "bold")
        )
        self.title_label.pack(pady=(5, 10), padx=10, anchor="w")
