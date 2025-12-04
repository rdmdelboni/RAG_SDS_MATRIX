#!/usr/bin/env python
"""Integration test for handler implementations - verifies handlers can be called."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from PySide6 import QtWidgets

# Import tabs
from src.ui.tabs import TabContext
from src.ui.tabs.rag_tab import RAGTab
from src.ui.tabs.sds_tab import SDSTab
from src.ui.tabs.automation_tab import AutomationTab
from src.ui.components import WorkerSignals


def create_test_context() -> TabContext:
    """Create a test TabContext with all mocked services."""
    colors = {
        "text": "#ffffff",
        "bg": "#000000",
        "surface": "#1a1a1a",
        "input": "#2a2a2a",
        "overlay": "#3a3a3a",
        "primary": "#4a9eff",
        "primary_hover": "#3a8eef",
        "button_hover": "#5aaeff",
        "accent": "#4fd1c5",
        "success": "#22c55e",
        "warning": "#f9e2af",
        "error": "#f38ba8",
        "subtext": "#a6adc8",
    }

    return TabContext(
        db=MagicMock(),
        ingestion=MagicMock(),
        ollama=MagicMock(),
        profile_router=MagicMock(),
        heuristics=MagicMock(),
        sds_extractor=MagicMock(),
        colors=colors,
        app_settings=MagicMock(),
        thread_pool=MagicMock(),
        set_status=MagicMock(),
        on_error=MagicMock(),
        start_task=MagicMock(),
    )


def test_rag_tab_handlers(context: TabContext) -> bool:
    """Test RAGTab handler methods exist and are callable."""
    print("\n🧪 Testing RAGTab handlers...")

    tab = RAGTab(context)

    # Test that handlers exist and are callable
    handlers = [
        "_on_ingest_files",
        "_on_ingest_folder",
        "_on_ingest_url",
        "_refresh_sources_table",
        "_refresh_rag_stats",
        "_ingest_files_task",
        "_ingest_url_task",
        "_on_ingest_done",
    ]

    for handler_name in handlers:
        if not hasattr(tab, handler_name):
            print(f"  ✗ Missing handler: {handler_name}")
            return False
        if not callable(getattr(tab, handler_name)):
            print(f"  ✗ Handler not callable: {handler_name}")
            return False
        print(f"  ✓ {handler_name}")

    # Test that handler methods don't crash when called with invalid input
    try:
        tab.url_input.setText("")  # Invalid - should be caught
        tab._on_ingest_url()  # Should handle gracefully
        print("  ✓ Handlers handle invalid input gracefully")
    except Exception as e:
        print(f"  ✗ Handler crashed with invalid input: {e}")
        return False

    print("✓ RAGTab handlers working correctly")
    return True


def test_sds_tab_handlers(context: TabContext) -> bool:
    """Test SDSTab handler methods exist and are callable."""
    print("\n🧪 Testing SDSTab handlers...")

    tab = SDSTab(context)

    # Test that handlers exist and are callable
    handlers = [
        "_on_select_folder",
        "_load_folder_contents",
        "_on_process_sds",
        "_on_build_matrix",
        "_on_export",
        "_on_select_all_files",
        "_on_select_pending_files",
        "_process_sds_task",
        "_build_matrix_task",
        "_export_task",
        "_on_sds_progress",
        "_on_sds_done",
        "_on_matrix_done",
        "_on_export_done",
    ]

    for handler_name in handlers:
        if not hasattr(tab, handler_name):
            print(f"  ✗ Missing handler: {handler_name}")
            return False
        if not callable(getattr(tab, handler_name)):
            print(f"  ✗ Handler not callable: {handler_name}")
            return False
        print(f"  ✓ {handler_name}")

    # Test that handlers don't crash with invalid input
    try:
        tab.selected_folder = None  # No folder selected
        tab._on_process_sds()  # Should handle gracefully
        print("  ✓ Handlers handle invalid input gracefully")
    except Exception as e:
        print(f"  ✗ Handler crashed with invalid input: {e}")
        return False

    print("✓ SDSTab handlers working correctly")
    return True


def test_automation_tab_handlers(context: TabContext) -> bool:
    """Test AutomationTab handler methods exist and are callable."""
    print("\n🧪 Testing AutomationTab handlers...")

    tab = AutomationTab(context)

    # Test that handlers exist and are callable
    handlers = [
        "_on_select_cas_file",
        "_on_select_harvest_output",
        "_on_select_packet_matrix",
        "_on_select_packet_sds_dir",
        "_on_select_gen_data",
        "_on_select_gen_output",
        "_on_run_harvest_process",
        "_harvest_process_task",
        "_on_harvest_progress",
        "_on_harvest_process_done",
        "_on_run_scheduler",
        "_scheduler_task",
        "_on_scheduler_progress",
        "_on_scheduler_done",
        "_on_export_packet",
        "_export_packet_task",
        "_on_packet_done",
        "_on_generate_sds_pdf",
        "_generate_sds_task",
        "_on_generate_done",
    ]

    for handler_name in handlers:
        if not hasattr(tab, handler_name):
            print(f"  ✗ Missing handler: {handler_name}")
            return False
        if not callable(getattr(tab, handler_name)):
            print(f"  ✗ Handler not callable: {handler_name}")
            return False
        print(f"  ✓ {handler_name}")

    # Test that handlers don't crash with invalid input
    try:
        tab.cas_file_input.setText("")  # Invalid
        tab._on_run_harvest_process()  # Should handle gracefully
        print("  ✓ Handlers handle invalid input gracefully")
    except Exception as e:
        print(f"  ✗ Handler crashed with invalid input: {e}")
        return False

    print("✓ AutomationTab handlers working correctly")
    return True


def test_background_tasks(context: TabContext) -> bool:
    """Test that background tasks can be invoked without errors."""
    print("\n🧪 Testing background task execution...")

    # Create a mock WorkerSignals
    signals = MagicMock(spec=WorkerSignals)

    # Test RAGTab ingestion task (simplified - just test it doesn't crash)
    rag_tab = RAGTab(context)
    context.ingestion.ingest_local_files = MagicMock(
        return_value=MagicMock(to_message=MagicMock(return_value="Test message"))
    )

    try:
        # Just verify the method exists and can be called
        result = rag_tab._ingest_files_task([], signals=signals)
        print("  ✓ RAGTab._ingest_files_task executes without error")
    except Exception as e:
        print(f"  ✗ RAGTab._ingest_files_task failed: {e}")
        return False

    # Test SDSTab matrix building task
    sds_tab = SDSTab(context)
    context.db.get_processed_files_metadata = MagicMock(return_value={})

    try:
        result = sds_tab._build_matrix_task(signals=signals)
        print("  ✓ SDSTab._build_matrix_task executes without error")
    except Exception as e:
        print(f"  ✗ SDSTab._build_matrix_task failed: {e}")
        return False

    # Test AutomationTab packet export task
    automation_tab = AutomationTab(context)

    try:
        result = automation_tab._export_packet_task(
            Path("matrix.csv"),
            Path("/tmp"),
            ["67-64-1"],
            signals=signals
        )
        # Should fail since files don't exist, but task method should execute
        print("  ✓ AutomationTab._export_packet_task executes without error")
    except Exception as e:
        print(f"  ✗ AutomationTab._export_packet_task failed: {e}")
        return False

    print("✓ Background tasks execute without errors")
    return True


def main() -> int:
    """Run all integration tests."""
    print("=" * 60)
    print("HANDLER INTEGRATION TEST SUITE")
    print("=" * 60)

    # Create Qt application
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    # Create test context
    context = create_test_context()

    all_pass = True
    all_pass &= test_rag_tab_handlers(context)
    all_pass &= test_sds_tab_handlers(context)
    all_pass &= test_automation_tab_handlers(context)
    all_pass &= test_background_tasks(context)

    print("\n" + "=" * 60)
    if all_pass:
        print("✅ ALL INTEGRATION TESTS PASSED")
        print("=" * 60)
        return 0
    else:
        print("❌ SOME TESTS FAILED")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
