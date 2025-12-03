import requests
from bs4 import BeautifulSoup
from pathlib import Path
from typing import List, Optional
from ..base import BaseSDSProvider, SDSMetadata
from ...utils.logger import get_logger

logger = get_logger(__name__)

class FisherScientificProvider(BaseSDSProvider):
    """SDS Provider for Fisher Scientific."""

    BASE_URL = "https://www.fishersci.com"
    SEARCH_URL = "https://www.fishersci.com/us/en/catalog/search/sds.html"

    def __init__(self):
        super().__init__("Fisher Scientific")
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        })

    def search(self, cas_number: str) -> List[SDSMetadata]:
        """Search Fisher Scientific for SDS."""
        results = []
        try:
            params = {"keyword": cas_number}
            response = self.session.get(self.SEARCH_URL, params=params, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")
            
            # This is a best-effort guess at their DOM structure which changes.
            # We look for links containing "SDS" and ".pdf" or specific classes.
            # Fisher's search results often list products with an "SDS" button.
            
            # Look for SDS links. The structure is often:
            # <a href="..." ...>SDS</a>
            
            # Generic approach: find all 'a' tags with 'SDS' text or 'sds' in href
            links = soup.find_all("a", href=True)
            
            for link in links:
                href = link["href"]
                text = link.get_text(strip=True).upper()
                
                if "SDS" in text or "SAFETY DATA SHEET" in text or "/sds/" in href.lower():
                    # Resolve relative URLs
                    full_url = href if href.startswith("http") else f"{self.BASE_URL}{href}"
                    
                    # Basic validation to avoid junk links
                    if "fishersci.com" in full_url:
                        results.append(SDSMetadata(
                            title=f"SDS for {cas_number}",
                            url=full_url,
                            source=self.name,
                            cas_number=cas_number,
                            manufacturer="Fisher Scientific"
                        ))
            
            # Deduplicate by URL
            unique_results = []
            seen_urls = set()
            for res in results:
                if res.url not in seen_urls:
                    seen_urls.add(res.url)
                    unique_results.append(res)
            
            return unique_results

        except Exception as e:
            logger.error(f"Error searching Fisher Scientific for {cas_number}: {e}")
            return []

    def download(self, url: str, destination: Path) -> bool:
        """Download SDS PDF."""
        try:
            response = self.session.get(url, stream=True, timeout=15)
            response.raise_for_status()
            
            # Check content type
            content_type = response.headers.get("Content-Type", "").lower()
            if "pdf" not in content_type and "application/octet-stream" not in content_type:
                 logger.warning(f"URL {url} returned content-type {content_type}, expected PDF.")
                 # Proceeding anyway as some servers are misconfigured, but logging warning.
            
            with open(destination, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            return True
        except Exception as e:
            logger.error(f"Error downloading from {url}: {e}")
            if destination.exists():
                destination.unlink()
            return False
