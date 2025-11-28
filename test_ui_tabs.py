#!/usr/bin/env python3
"""
Test script for modular UI tabs.

Run individual tabs to verify functionality before integrating into main app.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

import customtkinter as ctk
from src.ui.tabs import RAGViewerTab, SDSProcessorTab, BackupTab


def test_rag_viewer():
    """Test RAGViewerTab in standalone window."""
    app = ctk.CTk()
    app.title("Test: RAG Viewer Tab")
    app.geometry("900x700")

    # Create frame
    frame = ctk.CTkFrame(app, fg_color="transparent")
    frame.pack(fill="both", expand=True, padx=10, pady=10)

    # Add tab
    tab = RAGViewerTab(frame)
    tab.pack(fill="both", expand=True)

    app.mainloop()


def test_sds_processor():
    """Test SDSProcessorTab in standalone window."""
    app = ctk.CTk()
    app.title("Test: SDS Processor Tab")
    app.geometry("900x700")

    # Create frame
    frame = ctk.CTkFrame(app, fg_color="transparent")
    frame.pack(fill="both", expand=True, padx=10, pady=10)

    # Add tab
    tab = SDSProcessorTab(frame)
    tab.pack(fill="both", expand=True)

    app.mainloop()


def test_backup():
    """Test BackupTab in standalone window."""
    app = ctk.CTk()
    app.title("Test: Backup Tab")
    app.geometry("900x700")

    # Create frame
    frame = ctk.CTkFrame(app, fg_color="transparent")
    frame.pack(fill="both", expand=True, padx=10, pady=10)

    # Add tab
    tab = BackupTab(frame)
    tab.pack(fill="both", expand=True)

    app.mainloop()


def test_all_tabs():
    """Test all tabs in a tabbed interface."""
    app = ctk.CTk()
    app.title("Test: All UI Tabs")
    app.geometry("1000x800")

    # Create tab view
    tab_view = ctk.CTkTabview(app)
    tab_view.pack(fill="both", expand=True, padx=10, pady=10)

    # Add tabs
    tab_view.add("RAG Viewer")
    tab_view.add("SDS Processor")
    tab_view.add("Backup")

    # Add content to each tab
    rag_frame = tab_view.tab("RAG Viewer")
    rag_tab = RAGViewerTab(rag_frame)
    rag_tab.pack(fill="both", expand=True)

    sds_frame = tab_view.tab("SDS Processor")
    sds_tab = SDSProcessorTab(sds_frame)
    sds_tab.pack(fill="both", expand=True)

    backup_frame = tab_view.tab("Backup")
    backup_tab = BackupTab(backup_frame)
    backup_tab.pack(fill="both", expand=True)

    app.mainloop()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Test UI tabs")
    parser.add_argument(
        "tab",
        nargs="?",
        default="all",
        choices=["rag", "sds", "backup", "all"],
        help="Which tab to test",
    )

    args = parser.parse_args()

    print("=" * 60)
    print("RAG SDS Matrix - UI Tabs Test")
    print("=" * 60)

    if args.tab == "rag":
        print("Testing RAGViewerTab...")
        test_rag_viewer()
    elif args.tab == "sds":
        print("Testing SDSProcessorTab...")
        test_sds_processor()
    elif args.tab == "backup":
        print("Testing BackupTab...")
        test_backup()
    else:  # all
        print("Testing all tabs in tabbed interface...")
        test_all_tabs()

    print("Test completed!")
