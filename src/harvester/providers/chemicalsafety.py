import requests
from bs4 import BeautifulSoup
from pathlib import Path
from typing import List
from ..base import BaseSDSProvider, SDSMetadata
from ...utils.logger import get_logger

logger = get_logger(__name__)

class ChemicalSafetyProvider(BaseSDSProvider):
    """SDS Provider for ChemicalSafety.com."""

    BASE_URL = "https://chemicalsafety.com"
    SEARCH_URL = "https://chemicalsafety.com/sds-search/"

    def __init__(self):
        super().__init__("ChemicalSafety")
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Referer": "https://chemicalsafety.com/",
        })

    def search(self, cas_number: str) -> List[SDSMetadata]:
        results = []
        try:
            # ChemicalSafety search usually works via a search box that redirects or loads results.
            # Let's try common query parameters.
            params = {"s": cas_number} # WordPress default search
            # Or looking at the page, it might be a specific tool.
            # Let's try fetching the search page with the query.
            
            response = self.session.get(self.SEARCH_URL, params=params, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Look for PDF links or result rows
            # This is speculative without seeing the DOM.
            # But we look for 'href' ending in .pdf or containing 'sds'
            
            links = soup.find_all("a", href=True)
            for link in links:
                href = link["href"]
                text = link.get_text(strip=True).lower()
                
                if ("sds" in text or "safety data sheet" in text or "pdf" in href.lower()) and cas_number in text:
                     # This is a very specific match condition
                     full_url = href if href.startswith("http") else f"{self.BASE_URL}{href}"
                     results.append(SDSMetadata(
                        title=f"SDS for {cas_number}",
                        url=full_url,
                        source=self.name,
                        cas_number=cas_number,
                        manufacturer="ChemicalSafety"
                     ))
            
            return results

        except Exception as e:
            logger.error(f"Error searching ChemicalSafety: {e}")
            return []

    def download(self, url: str, destination: Path) -> bool:
        try:
            response = self.session.get(url, stream=True, timeout=20)
            response.raise_for_status()
            with open(destination, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            return True
        except Exception as e:
            logger.error(f"Error downloading from {url}: {e}")
            return False
