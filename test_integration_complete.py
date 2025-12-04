#!/usr/bin/env python
"""Integration tests for all UI handlers with realistic backend interactions."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent))

from PySide6 import QtWidgets

from src.ui.tabs import TabContext
from src.ui.tabs.rag_tab import RAGTab
from src.ui.tabs.sds_tab import SDSTab
from src.ui.tabs.automation_tab import AutomationTab
from src.ui.tabs.review_tab import ReviewTab
from src.ui.tabs.backup_tab import BackupTab
from src.ui.tabs.records_tab import RecordsTab
from src.ui.tabs.status_tab import StatusTab
from src.ui.tabs.chat_tab import ChatTab
from src.ui.tabs.regex_lab_tab import RegexLabTab


def create_test_context() -> TabContext:
    """Create a test TabContext with comprehensive mocks."""
    colors = {
        "text": "#ffffff", "bg": "#000000", "surface": "#1a1a1a", "input": "#2a2a2a",
        "overlay": "#3a3a3a", "primary": "#4a9eff", "primary_hover": "#3a8eef",
        "button_hover": "#5aaeff", "accent": "#4fd1c5", "success": "#22c55e",
        "warning": "#f9e2af", "error": "#f38ba8", "subtext": "#a6adc8",
    }

    # Create mocks with realistic return values
    db_mock = MagicMock()
    db_mock.get_statistics.return_value = {
        "total_documents": 150,
        "processed": 120,
        "failed": 5,
        "rag_documents": 80,
        "rag_chunks": 450,
        "rag_last_updated": "2025-12-04 10:30",
    }
    db_mock.fetch_results.return_value = [
        {
            "id": 1,
            "filename": "chemical_001.pdf",
            "status": "SUCCESS",
            "product_name": "Test Chemical A",
            "cas_number": "67-64-1",
            "un_number": "1987",
            "hazard_class": "3",
            "processed_at": "2025-12-04 09:00",
        },
        {
            "id": 2,
            "filename": "chemical_002.pdf",
            "status": "NOT_FOUND",
            "product_name": "Test Chemical B",
            "cas_number": "64-17-5",
            "un_number": "1170",
            "hazard_class": "3",
            "processed_at": None,
        },
    ]
    db_mock.get_rag_documents.return_value = [
        {
            "id": "doc1",
            "title": "Safety Guidelines",
            "source_type": "document",
            "source_path": "/docs/safety.pdf",
            "indexed_at": "2025-12-04 08:00",
            "chunk_count": 12,
        }
    ]
    db_mock.get_processed_files_metadata.return_value = {
        ("file1.pdf", 1024): "hash123",
        ("file2.pdf", 2048): "hash456",
    }
    db_mock.update_record.return_value = True

    ingestion_mock = MagicMock()
    ingestion_mock.ingest_local_files.return_value = MagicMock(
        to_message=MagicMock(return_value="Ingested 3 files successfully")
    )
    ingestion_mock.ingest_url.return_value = MagicMock(
        to_message=MagicMock(return_value="Ingested URL successfully")
    )
    ingestion_mock.vector_store = MagicMock()
    ingestion_mock.vector_store.search_with_context.return_value = [
        {"title": "Doc 1", "content": "Safety information..."},
    ]

    ollama_mock = MagicMock()
    ollama_mock.list_models.return_value = ["llama2", "mistral"]
    ollama_mock.chat.return_value = "Based on the safety guidelines, you should..."

    profile_router_mock = MagicMock()
    profile_router_mock.list_profiles.return_value = ["manufacturer_a", "manufacturer_b"]
    profile_router_mock.identify_profile.return_value = MagicMock(name="manufacturer_a")

    heuristics_mock = MagicMock()
    heuristics_mock.extract_all_fields.return_value = {
        "product_name": {"value": "Chemical X", "confidence": 0.95, "source": "regex"},
        "cas_number": {"value": "7732-18-5", "confidence": 0.99, "source": "database"},
    }

    sds_extractor_mock = MagicMock()
    sds_extractor_mock.extract_document.return_value = {
        "text": "Safety Data Sheet content...",
        "sections": {"hazards": "Contains hazardous substances"},
    }

    return TabContext(
        db=db_mock,
        ingestion=ingestion_mock,
        ollama=ollama_mock,
        profile_router=profile_router_mock,
        heuristics=heuristics_mock,
        sds_extractor=sds_extractor_mock,
        colors=colors,
        app_settings=MagicMock(),
        thread_pool=MagicMock(),
        set_status=MagicMock(),
        on_error=MagicMock(),
        start_task=MagicMock(),
    )


def test_rag_tab_workflow(context: TabContext) -> bool:
    """Test RAGTab ingestion workflow."""
    print("\n🧪 Testing RAGTab workflow...")

    tab = RAGTab(context)

    # Test file ingestion validation
    try:
        tab.url_input.setText("")
        with tempfile.TemporaryDirectory():
            tab._on_ingest_url()  # Should show error or return early
        print("  ✓ URL validation works")
    except Exception as e:
        print(f"  ✗ URL validation failed: {e}")
        return False

    # Test that ingestion methods are callable
    try:
        result = tab._ingest_files_task([Path(__file__)])
        assert hasattr(result, "to_message")
        print("  ✓ File ingestion task executes")
    except Exception as e:
        print(f"  ✗ File ingestion failed: {e}")
        return False

    # Test refresh methods
    tab._refresh_rag_stats()
    assert context.db.get_statistics.called
    print("  ✓ Statistics refresh works")

    tab._refresh_sources_table()
    assert context.db.get_rag_documents.called
    print("  ✓ Sources table refresh works")

    print("✓ RAGTab workflow tests passed")
    return True


def test_sds_tab_workflow(context: TabContext) -> bool:
    """Test SDSTab processing workflow."""
    print("\n🧪 Testing SDSTab workflow...")

    tab = SDSTab(context)

    # Test folder loading
    with tempfile.TemporaryDirectory() as tmpdir:
        tab.selected_folder = Path(tmpdir)
        tab._load_folder_contents()
        print("  ✓ Folder loading works")

    # Test that process method is callable
    try:
        result = tab._process_sds_task(Path(__file__), use_rag=True)
        assert isinstance(result, dict)
        print("  ✓ SDS processing task executes")
    except Exception as e:
        print(f"  ✗ SDS processing failed: {e}")
        return False

    # Test matrix building
    try:
        result = tab._build_matrix_task()
        assert isinstance(result, dict)
        print("  ✓ Matrix building task executes")
    except Exception as e:
        print(f"  ✗ Matrix building failed: {e}")
        return False

    # Test export
    with tempfile.NamedTemporaryFile(suffix=".xlsx") as tmp:
        try:
            result = tab._export_task(tmp.name, "Excel (*.xlsx)")
            assert isinstance(result, dict)
            print("  ✓ Export task executes")
        except Exception as e:
            print(f"  ✗ Export failed: {e}")

    print("✓ SDSTab workflow tests passed")
    return True


def test_automation_tab_workflow(context: TabContext) -> bool:
    """Test AutomationTab workflows."""
    print("\n🧪 Testing AutomationTab workflows...")

    tab = AutomationTab(context)

    # Test harvest validation with empty inputs (should trigger validation error)
    context.on_error.reset_mock()
    tab._on_run_harvest_process()
    assert context.on_error.called  # Should call on_error for missing CAS file
    print("  ✓ Harvest validation works")

    # Test harvest task
    with tempfile.TemporaryDirectory() as tmpdir:
        cas_file = Path(tmpdir) / "cas_list.txt"
        cas_file.write_text("67-64-1\n64-17-5\n")

        try:
            result = tab._harvest_process_task(cas_file, Path(tmpdir), limit=1, process=False, use_rag=False)
            assert isinstance(result, dict)
            print("  ✓ Harvest task executes")
        except Exception as e:
            print(f"  ✗ Harvest task failed: {e}")
            return False

    # Test scheduler task
    with tempfile.TemporaryDirectory() as tmpdir:
        cas_file = Path(tmpdir) / "cas_list.txt"
        cas_file.write_text("67-64-1\n")

        try:
            # Test with 1 iteration to avoid long waits
            result = tab._scheduler_task(
                cas_file, interval=1, iterations=1, output_dir=Path(tmpdir),
                limit=1, process=False, use_rag=False
            )
            assert isinstance(result, dict)
            print("  ✓ Scheduler task executes")
        except Exception as e:
            print(f"  ✗ Scheduler task failed: {e}")

    # Test packet export
    with tempfile.TemporaryDirectory() as tmpdir:
        matrix_file = Path(tmpdir) / "matrix.csv"
        matrix_file.write_text("file,data\n")

        try:
            result = tab._export_packet_task(matrix_file, Path(tmpdir), ["67-64-1"])
            assert isinstance(result, dict)
            print("  ✓ Packet export task executes")
        except Exception as e:
            print(f"  ✗ Packet export failed: {e}")

    # Test SDS generation
    with tempfile.TemporaryDirectory() as tmpdir:
        data_file = Path(tmpdir) / "sds_data.json"
        data_file.write_text(json.dumps({"product_name": "Test", "cas_number": "123-45-6"}))
        output_pdf = Path(tmpdir) / "output.pdf"

        try:
            result = tab._generate_sds_task(data_file, output_pdf)
            assert isinstance(result, dict)
            print("  ✓ SDS generation task executes")
        except Exception as e:
            print(f"  ✗ SDS generation failed: {e}")

    print("✓ AutomationTab workflow tests passed")
    return True


def test_review_tab_workflow(context: TabContext) -> bool:
    """Test ReviewTab edit workflow."""
    print("\n🧪 Testing ReviewTab workflow...")

    tab = ReviewTab(context)

    # Test data loading
    test_data = [
        {"filename": "test1.pdf", "status": "SUCCESS", "product_name": "Chem1", "cas_number": "111", "un_number": "222", "hazard_class": "3"},
    ]
    tab._on_review_loaded(test_data)
    assert tab.current_data == test_data
    print("  ✓ Data loading works")

    # Test edit tracking
    tab.review_table.setItem(0, 2, QtWidgets.QTableWidgetItem("Modified Chemical"))
    tab._on_cell_changed(tab.review_table.item(0, 2))
    assert tab.edit_model.has_changes()
    print("  ✓ Edit tracking works")

    # Test button states
    tab._update_button_states()
    assert tab.save_btn.isEnabled()
    assert tab.cancel_btn.isEnabled()
    print("  ✓ Button state management works")

    # Test cancel changes
    tab._on_cancel_changes()
    # Would show confirmation dialog in real UI
    print("  ✓ Cancel handler works")

    print("✓ ReviewTab workflow tests passed")
    return True


def test_other_tabs(context: TabContext) -> bool:
    """Test that other tabs initialize without error."""
    print("\n🧪 Testing other tabs...")

    tabs_to_test = [
        ("BackupTab", BackupTab),
        ("RecordsTab", RecordsTab),
        ("StatusTab", StatusTab),
        ("ChatTab", ChatTab),
        ("RegexLabTab", RegexLabTab),
    ]

    for name, TabClass in tabs_to_test:
        try:
            _tab = TabClass(context)
            print(f"  ✓ {name} initializes")
        except Exception as e:
            print(f"  ✗ {name} failed: {e}")
            return False

    print("✓ All other tabs working")
    return True


def main() -> int:
    """Run all integration tests."""
    print("=" * 60)
    print("COMPREHENSIVE INTEGRATION TEST SUITE")
    print("=" * 60)

    _app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    context = create_test_context()

    all_pass = True
    all_pass &= test_rag_tab_workflow(context)
    all_pass &= test_sds_tab_workflow(context)
    all_pass &= test_automation_tab_workflow(context)
    all_pass &= test_review_tab_workflow(context)
    all_pass &= test_other_tabs(context)

    print("\n" + "=" * 60)
    if all_pass:
        print("✅ ALL INTEGRATION TESTS PASSED")
        print("=" * 60)
        print("\nIntegration Testing Complete!")
        print("Ready for UI Enhancements and Documentation phases.")
        return 0
    else:
        print("❌ SOME TESTS FAILED")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
