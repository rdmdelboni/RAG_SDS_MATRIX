from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional
from pathlib import Path

@dataclass
class SDSMetadata:
    """Metadata for a found SDS."""
    title: str
    url: str
    source: str
    cas_number: str
    language: str = "en"
    date: Optional[str] = None
    manufacturer: Optional[str] = None

class BaseSDSProvider(ABC):
    """Base class for SDS providers."""

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def search(self, cas_number: str) -> List[SDSMetadata]:
        """Search for SDS by CAS number."""
        pass

    @abstractmethod
    def download(self, url: str, destination: Path) -> bool:
        """Download SDS from URL to destination. Returns True if successful."""
        pass
