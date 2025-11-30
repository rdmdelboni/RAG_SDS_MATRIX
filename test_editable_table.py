#!/usr/bin/env python3
"""Test script for the new EditableTable based on tkintertable."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import customtkinter as ctk
from src.ui.components.editable_table import EditableTable


def main():
    """Create a test window with the new EditableTable."""
    # Setup app
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    root = ctk.CTk()
    root.title("EditableTable (tkintertable) Test")
    root.geometry("1024x768")

    # Add title
    title = ctk.CTkLabel(
        root,
        text="EditableTable with tkintertable Backend",
        font=("JetBrains Mono", 16, "bold"),
    )
    title.pack(pady=10)

    # Create test data
    headers = ["Name", "CAS Number", "GHS Pictograms", "Notes"]
    test_rows = [
        ["Acetone", "67-64-1", "GHS02, GHS07", "Flammable liquid and vapor."],
        ["Sodium Hydroxide", "1310-73-2", "GHS05", "Causes severe skin burns and eye damage."],
        ["Ethanol", "64-17-5", "GHS02, GHS07", "Highly flammable liquid and vapor."],
        [
            "Formaldehyde",
            "50-00-0",
            "GHS05, GHS06, GHS08",
            "Toxic if swallowed, in contact with skin or if inhaled.",
        ],
        ["Methanol", "67-56-1", "GHS02, GHS06, GHS08", "Toxic if swallowed, in contact with skin or if inhaled."],
    ]

    # Callback functions
    def on_cell_edit(row, col, value):
        print(f"Cell edited: Row {row}, Col {col}, New Value: {value}")
        status_label.configure(text=f"Cell edited: Row {row}, Col {col}, Value: {value}")

    def on_row_select(row_idx):
        print(f"Row selected: {row_idx}")
        selected_data = table.get_selected_row_data()
        status_label.configure(text=f"Row selected: {row_idx} | Data: {selected_data}")
        
    def on_row_double_click(row_idx):
        print(f"Row double-clicked: {row_idx}")
        status_label.configure(text=f"Row double-clicked: {row_idx}")

    # Create EditableTable
    table = EditableTable(
        root,
        headers=headers,
        rows=test_rows,
        editable=True,
        on_cell_edit=on_cell_edit,
        on_row_select=on_row_select,
        on_row_double_click=on_row_double_click
    )
    table.pack(fill="both", expand=True, padx=20, pady=20)

    # Add instructions
    instructions = ctk.CTkLabel(
        root,
        text="Instructions:\n" 
        "- Click column headers to sort.\n" 
        "- Drag column dividers in the header to resize.\n" 
        "- Double-click a cell to edit its content.\n" 
        "- Click a row to select it and see callback output in the console.",
        font=("JetBrains Mono", 10),
        text_color="#94a3b8",
        wraplength=800,
        justify="left",
    )
    instructions.pack(pady=10)

    # Test status
    status_label = ctk.CTkLabel(
        root,
        text="Table loaded. Interact with the table to see updates.",
        font=("JetBrains Mono", 10),
        text_color="#50fa7b",
    )
    status_label.pack(pady=5, fill="x")

    root.mainloop()


if __name__ == "__main__":
    main()
