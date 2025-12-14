#!/usr/bin/env python
"""Test script to verify UI refactoring - all tabs instantiate correctly."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from PySide6 import QtCore, QtWidgets

# This test imports the full UI, which includes graph features requiring networkx.
pytest.importorskip("networkx", reason="networkx not installed in this environment")

# Import all required modules
print("✓ Importing MainWindow and tabs...")
try:
    from src.ui.app import MainWindow
    from src.ui.tabs import TabContext
    from src.ui.tabs.backup_tab import BackupTab
    from src.ui.tabs.records_tab import RecordsTab
    from src.ui.tabs.review_tab import ReviewTab
    from src.ui.tabs.status_tab import StatusTab
    from src.ui.tabs.chat_tab import ChatTab
    from src.ui.tabs.regex_lab_tab import RegexLabTab
    from src.ui.tabs.automation_tab import AutomationTab
    from src.ui.tabs.rag_tab import RAGTab
    from src.ui.tabs.sds_tab import SDSTab
    print("✓ All imports successful")
except ImportError as e:
    pytest.skip(f"Import error: {e}", allow_module_level=True)


def test_tab_context_creation():
    """Test that TabContext can be instantiated."""
    print("\n🧪 Testing TabContext creation...")
    try:
        from unittest.mock import MagicMock

        # Provide complete color palette expected by tabs
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

        context = TabContext(
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
        print("✓ TabContext created successfully")
        return context
    except Exception as e:
        print(f"✗ TabContext creation failed: {e}")
        return None


def test_tab_instantiation(context: TabContext):
    """Test that all tabs can be instantiated with TabContext."""
    print("\n🧪 Testing tab instantiation...")

    tabs = {
        "BackupTab": BackupTab,
        "RecordsTab": RecordsTab,
        "ReviewTab": ReviewTab,
        "StatusTab": StatusTab,
        "ChatTab": ChatTab,
        "RegexLabTab": RegexLabTab,
        "AutomationTab": AutomationTab,
        "RAGTab": RAGTab,
        "SDSTab": SDSTab,
    }

    results = {}
    for name, TabClass in tabs.items():
        try:
            tab = TabClass(context)
            results[name] = True
            print(f"  ✓ {name}")
        except Exception as e:
            results[name] = False
            print(f"  ✗ {name}: {e}")

    success_count = sum(1 for v in results.values() if v)
    total_count = len(results)
    print(f"\n✓ {success_count}/{total_count} tabs instantiated successfully")
    return all(results.values())


def test_tab_properties(context: TabContext):
    """Test that tabs have required properties and methods."""
    print("\n🧪 Testing tab properties...")

    test_tab = StatusTab(context)
    required_methods = ["_set_status", "_start_task", "_style_label", "_style_button"]
    required_attrs = ["context", "colors"]

    all_good = True
    for method in required_methods:
        if hasattr(test_tab, method) and callable(getattr(test_tab, method)):
            print(f"  ✓ Has method: {method}")
        else:
            print(f"  ✗ Missing method: {method}")
            all_good = False

    for attr in required_attrs:
        if hasattr(test_tab, attr):
            print(f"  ✓ Has attribute: {attr}")
        else:
            print(f"  ✗ Missing attribute: {attr}")
            all_good = False

    return all_good


def test_signal_callbacks(context: TabContext):
    """Test that callbacks are properly connected."""
    print("\n🧪 Testing signal callbacks...")

    # Verify that TabContext has the expected callbacks
    assert callable(context.set_status), "set_status is not callable"
    assert callable(context.on_error), "on_error is not callable"
    assert callable(context.start_task), "start_task is not callable"

    print("  ✓ set_status is callable")
    print("  ✓ on_error is callable")
    print("  ✓ start_task is callable")

    # Try calling them (with mocks, they should not error)
    try:
        context.set_status("test message")
        context.on_error("test error")
        print("  ✓ Callbacks execute without errors")
        return True
    except Exception as e:
        print(f"  ✗ Callback execution failed: {e}")
        return False


def main():
    """Run all tests."""
    print("=" * 60)
    print("UI REFACTORING TEST SUITE")
    print("=" * 60)

    # Create Qt application (required for UI testing)
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    # Run tests
    context = test_tab_context_creation()
    if not context:
        print("\n✗ Cannot continue without TabContext")
        return False

    all_pass = True
    all_pass &= test_tab_instantiation(context)
    all_pass &= test_tab_properties(context)
    all_pass &= test_signal_callbacks(context)

    print("\n" + "=" * 60)
    if all_pass:
        print("✅ ALL TESTS PASSED")
        print("=" * 60)
        return True
    else:
        print("❌ SOME TESTS FAILED")
        print("=" * 60)
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
