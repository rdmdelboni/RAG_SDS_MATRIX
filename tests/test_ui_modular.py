
import sys
from unittest.mock import MagicMock
import pytest
from PySide6.QtCore import QSettings, QThreadPool
from PySide6.QtWidgets import QApplication

from src.ui.tabs import TabContext
from src.ui.tabs.rag_tab import RAGTab
from src.ui.tabs.automation_tab import AutomationTab
from src.ui.tabs.sds_processing_tab import SDSProcessingTab

# Ensure QApplication exists (singleton)
@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app

@pytest.fixture
def mock_context():
    """Create a mock TabContext with fake dependencies."""
    return TabContext(
        db=MagicMock(),
        ingestion=MagicMock(),
        ollama=MagicMock(),
        profile_router=MagicMock(),
        heuristics=MagicMock(),
        sds_extractor=MagicMock(),
        colors={
            "bg": "#000000",
            "text": "#ffffff",
            "surface": "#333333",
            "input": "#444444",
            "overlay": "#555555",
            "primary": "#666666",
            "accent": "#777777",
            "error": "#ff0000",
            "warning": "#ffff00",
            "success": "#00ff00",
            "subtext": "#aaaaaa",
            "button_hover": "#888888",
        },
        app_settings=MagicMock(spec=QSettings),
        thread_pool=MagicMock(spec=QThreadPool),
        set_status=MagicMock(),
        on_error=MagicMock(),
        start_task=MagicMock(),
    )

def test_rag_tab_init(qapp, mock_context):
    """Test that RAGTab can be instantiated."""
    tab = RAGTab(mock_context)
    assert tab is not None
    # Check if critical widgets are created
    assert hasattr(tab, "rag_stats_label")
    assert hasattr(tab, "sources_table")

def test_automation_tab_init(qapp, mock_context):
    """Test that AutomationTab can be instantiated."""
    tab = AutomationTab(mock_context)
    assert tab is not None
    # Check widgets
    assert hasattr(tab, "cas_file_input")
    assert hasattr(tab, "harvest_output_input")

def test_sds_processing_tab_init(qapp, mock_context):
    """Test that SDSProcessingTab can be instantiated via mock context."""
    # SDSProcessingTab might need real profile router list in UI build
    mock_context.profile_router.list_profiles.return_value = ["Profile1", "Profile2"]
    
    tab = SDSProcessingTab(mock_context)
    assert tab is not None
    assert hasattr(tab, "mode_batch_radio")
    assert hasattr(tab, "test_file_input")

