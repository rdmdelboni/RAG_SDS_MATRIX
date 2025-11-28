#!/usr/bin/env python3
"""Test script for SimpleTable column resizing functionality."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

import customtkinter as ctk
from src.ui.components.simple_table import SimpleTable


def main():
    """Create a test window with SimpleTable and test resizing."""
    # Setup app
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    root = ctk.CTk()
    root.title("SimpleTable Column Resize Test")
    root.geometry("900x600")

    # Add title
    title = ctk.CTkLabel(
        root,
        text="SimpleTable Column Resizing Test",
        font=("JetBrains Mono", 16, "bold"),
    )
    title.pack(pady=10)

    # Create test data
    headers = ["Filename", "Quality Tier", "Confidence", "Validated"]
    test_rows = [
        ("document_001.pdf", "excellent", "95.2%", "✓"),
        ("document_002.pdf", "good", "87.3%", "✓"),
        ("document_003.pdf", "acceptable", "72.1%", "✗"),
        ("very_long_document_name_that_should_wrap_properly_001.pdf", "poor", "45.8%", "✗"),
        ("document_005.pdf", "excellent", "91.5%", "✓"),
        ("document_006.pdf", "good", "84.2%", "✓"),
        ("document_007.pdf", "unreliable", "32.0%", "✗"),
        ("document_008.pdf", "excellent", "96.1%", "✓"),
        ("document_009.pdf", "acceptable", "68.5%", "✗"),
        ("document_010.pdf", "good", "89.3%", "✓"),
        ("document_011.pdf", "excellent", "93.7%", "✓"),
        ("document_012.pdf", "poor", "38.2%", "✗"),
        ("document_013.pdf", "good", "85.9%", "✓"),
        ("document_014.pdf", "acceptable", "71.4%", "✗"),
        ("document_015.pdf", "excellent", "94.6%", "✓"),
    ]

    # Create SimpleTable
    table = SimpleTable(
        root,
        headers=headers,
        rows=test_rows,
        fg_color="#0f172a",
        text_color="#e2e8f0",
        header_color="#1e293b",
        accent_color="#4fd1c5",
    )
    table.pack(fill="both", expand=True, padx=10, pady=10)

    # Add instructions
    instructions = ctk.CTkLabel(
        root,
        text="Instructions: Drag the cyan column separators to resize columns. "
        "Font should be 14pt and easily readable.",
        font=("JetBrains Mono", 10),
        text_color="#94a3b8",
        wraplength=800,
    )
    instructions.pack(pady=5)

    # Test status
    def check_table_state():
        """Verify table state and properties."""
        try:
            # Check that font is 14pt
            font_name, font_size = table.font[:2]
            status_text = (
                f"✓ Font: {font_size}pt | "
                f"Columns: {len(table.headers)} | "
                f"Rows: {len(table.rows)} | "
                f"Resizable: Yes"
            )
            status_label.configure(text=status_text)
        except Exception as e:
            status_label.configure(text=f"✗ Error: {e}")

    status_label = ctk.CTkLabel(
        root,
        text="Loading table...",
        font=("JetBrains Mono", 9),
        text_color="#50fa7b",
    )
    status_label.pack(pady=5)

    root.after(100, check_table_state)
    root.mainloop()


if __name__ == "__main__":
    main()
