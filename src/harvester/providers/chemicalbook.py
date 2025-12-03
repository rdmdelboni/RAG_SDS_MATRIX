import requests
from bs4 import BeautifulSoup
from pathlib import Path
from typing import List
from ..base import BaseSDSProvider, SDSMetadata
from ...utils.logger import get_logger

logger = get_logger(__name__)

class ChemicalBookProvider(BaseSDSProvider):
    """SDS Provider for ChemicalBook."""

    BASE_URL = "https://www.chemicalbook.com"
    SEARCH_URL = "https://www.chemicalbook.com/Search_EN.aspx"

    def __init__(self):
        super().__init__("ChemicalBook")
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Referer": "https://www.chemicalbook.com/",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
        })

    def search(self, cas_number: str) -> List[SDSMetadata]:
        results = []
        try:
            params = {"keyword": cas_number}
            response = self.session.get(self.SEARCH_URL, params=params, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")
            
            # ChemicalBook results table
            # Look for links containing "MSDS" or "SDS"
            # Usually in a column or a button "MSDS"
            
            links = soup.find_all("a", href=True)
            for link in links:
                href = link["href"]
                text = link.get_text(strip=True)
                
                if "MSDS" in text or "SDS" in text or "ProductMSDS" in href:
                    full_url = href if href.startswith("http") else f"{self.BASE_URL}/{href.lstrip('/')}"
                    
                    # For ChemicalBook, the MSDS page is HTML, but often has a "Download PDF" or prints to PDF.
                    # We might need to parse that page too to find the PDF link.
                    # But for now, let's return the Metadata pointing to the HTML page?
                    # Our `download` method expects a direct file or needs to handle HTML-to-PDF.
                    # Wait, ChemicalBook MSDS are often HTML.
                    # The user asked for PDFs.
                    
                    results.append(SDSMetadata(
                        title=f"MSDS for {cas_number}",
                        url=full_url,
                        source=self.name,
                        cas_number=cas_number,
                        manufacturer="ChemicalBook"
                    ))

            # Dedupe
            unique = []
            seen = set()
            for r in results:
                if r.url not in seen:
                    seen.add(r.url)
                    unique.append(r)
            return unique

        except Exception as e:
            logger.error(f"Error searching ChemicalBook: {e}")
            return []

    def download(self, url: str, destination: Path) -> bool:
        # ChemicalBook pages are HTML. We might need to "print" them or find a PDF link inside.
        # For this prototype, if it's HTML, we just save the HTML?
        # Or better: Try to find a "Download PDF" button on that page.
        try:
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            
            if "application/pdf" in response.headers.get("Content-Type", ""):
                with open(destination, "wb") as f:
                    f.write(response.content)
                return True
            
            # If HTML, try to find PDF link
            soup = BeautifulSoup(response.text, "html.parser")
            pdf_link = soup.find("a", string="PDF")
            if pdf_link and pdf_link.get("href"):
                pdf_url = pdf_link["href"]
                if not pdf_url.startswith("http"):
                    pdf_url = f"{self.BASE_URL}/{pdf_url.lstrip('/')}"
                return self.download(pdf_url, destination)
            
            # If no PDF link, save HTML as fallback? 
            # User wants PDFs. Saving HTML as .pdf is bad.
            # Let's just save as .html if forced?
            # The prompt implies grabbing SDS. HTML SDS is better than nothing.
            
            dest_html = destination.with_suffix(".html")
            with open(dest_html, "w", encoding="utf-8") as f:
                f.write(response.text)
            logger.info(f"Saved HTML SDS to {dest_html} (PDF not found)")
            return True

        except Exception as e:
            logger.error(f"Error downloading {url}: {e}")
            return False
