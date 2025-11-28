"""UI tabs package."""

from .backup_tab import BackupTab
from .chat_tab import ChatTab
from .quality_tab import QualityTab
from .rag_tab import RagTab
from .records_tab import RecordsTab
from .sds_tab import SdsTab
from .sources_tab import SourcesTab
from .status_tab import StatusTab

__all__ = [
    "RagTab",
    "SourcesTab",
    "SdsTab",
    "StatusTab",
    "RecordsTab",
    "BackupTab",
    "ChatTab",
    "QualityTab",
]
