import requests
from bs4 import BeautifulSoup
from pathlib import Path
from typing import List

from ..base import BaseSDSProvider, SDSMetadata
from ...utils.logger import get_logger

logger = get_logger(__name__)


class FluorochemProvider(BaseSDSProvider):
    """SDS Provider for Fluorochem."""

    BASE_URL = "http://www.fluorochem.co.uk"
    SEARCH_URL = "http://www.fluorochem.co.uk/msds"

    def __init__(self) -> None:
        super().__init__("Fluorochem")
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            }
        )

    def search(self, cas_number: str) -> List[SDSMetadata]:
        results: List[SDSMetadata] = []
        try:
            params = {"cas": cas_number}
            resp = self.session.get(self.SEARCH_URL, params=params, timeout=10)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            for link in soup.find_all("a", href=True):
                href = link["href"]
                text = link.get_text(strip=True).upper()
                if "SDS" in text or "MSDS" in text or ".PDF" in href.upper():
                    full_url = href if href.startswith("http") else f"{self.BASE_URL}{href}"
                    results.append(
                        SDSMetadata(
                            title=f"SDS for {cas_number}",
                            url=full_url,
                            source=self.name,
                            cas_number=cas_number,
                            manufacturer="Fluorochem",
                        )
                    )

            seen = set()
            deduped: List[SDSMetadata] = []
            for item in results:
                if item.url in seen:
                    continue
                seen.add(item.url)
                deduped.append(item)
            return deduped
        except Exception as exc:
            logger.debug("Fluorochem search failed for %s: %s", cas_number, exc)
            return []

    def download(self, url: str, destination: Path) -> bool:
        try:
            resp = self.session.get(url, stream=True, timeout=15)
            resp.raise_for_status()
            with open(destination, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
            return True
        except Exception as exc:
            logger.debug("Fluorochem download failed for %s: %s", url, exc)
            destination.unlink(missing_ok=True)
            return False
