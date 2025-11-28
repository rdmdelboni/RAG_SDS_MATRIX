"""
A reusable title label component.
"""

import customtkinter as ctk


class TitleLabel(ctk.CTkLabel):
    """
    A class to create a title label
    """

    def __init__(self, parent, text, **kwargs):
        super().__init__(
            parent, text=text, font=("JetBrains Mono", 24, "bold"), **kwargs
        )
        self.pack(pady=20)
