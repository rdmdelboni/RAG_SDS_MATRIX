"""Browser-based SDS provider using Playwright for bot protection bypass.

This module provides a base class for SDS providers that need to handle
JavaScript rendering, CAPTCHAs, and anti-bot measures.
"""

from __future__ import annotations

from abc import abstractmethod
from pathlib import Path
from typing import List

from ..utils.logger import get_logger
from .base import BaseSDSProvider, SDSMetadata

logger = get_logger(__name__)


class BrowserSDSProvider(BaseSDSProvider):
    """Base class for browser-based SDS providers using Playwright.
    
    Use this instead of BaseSDSProvider when the target site:
    - Requires JavaScript execution
    - Has CAPTCHA protection
    - Blocks requests library with 403/cloudflare
    - Uses dynamic content loading
    
    Installation:
        pip install playwright
        playwright install chromium
    """

    def __init__(self, name: str, headless: bool = True):
        super().__init__(name)
        self.headless = headless
        self._browser = None
        self._playwright = None
        self._context = None
        
    def _ensure_browser(self) -> None:
        """Lazy initialization of browser."""
        if self._browser is not None:
            return
            
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise ImportError(
                f"{self.name} requires Playwright for bot protection bypass.\n"
                "Install with: pip install playwright && playwright install chromium"
            )
        
        self._playwright = sync_playwright().start()
        
        # Launch with anti-detection measures
        self._browser = self._playwright.chromium.launch(
            headless=self.headless,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
            ]
        )
        
        # Create context with realistic browser fingerprint
        self._context = self._browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent=(
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/120.0.0.0 Safari/537.36'
            ),
            locale='en-US',
            timezone_id='America/New_York',
        )
        
        # Stealth mode: remove webdriver detection
        self._context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)
        
        logger.info("Browser initialized for %s (headless=%s)", self.name, self.headless)

    def _get_page(self):
        """Get a new browser page."""
        self._ensure_browser()
        return self._context.new_page()

    @abstractmethod
    def search(self, cas_number: str) -> List[SDSMetadata]:
        """Search using browser automation. Must be implemented by subclass."""
        pass

    def download(self, url: str, destination: Path) -> bool:
        """Download PDF using browser to bypass protections."""
        try:
            page = self._get_page()
            
            # Handle PDF downloads
            download_promise = page.expect_download(timeout=30000)
            page.goto(url, wait_until='networkidle', timeout=30000)
            
            try:
                download = download_promise.value
                download.save_as(destination)
                page.close()
                logger.info("Downloaded %s via browser", destination.name)
                return True
            except Exception:
                # If no download triggered, try saving rendered page
                page.pdf(path=str(destination))
                page.close()
                logger.info("Saved PDF from rendered page: %s", destination.name)
                return True
                
        except Exception as exc:
            logger.warning("Browser download failed for %s: %s", url, exc)
            destination.unlink(missing_ok=True)
            return False

    def close(self) -> None:
        """Clean up browser resources."""
        if self._context:
            self._context.close()
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()
        logger.info("Browser closed for %s", self.name)

    def __enter__(self):
        """Context manager support."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Clean up on exit."""
        self.close()


# Example implementation for Fisher Scientific
class FisherBrowserProvider(BrowserSDSProvider):
    """Fisher Scientific provider using browser automation.
    
    Use this when the regular FisherScientificProvider fails with 403 errors.
    """
    
    BASE_URL = "https://www.fishersci.com"
    SEARCH_URL = f"{BASE_URL}/us/en/catalog/search/sdshome.html"
    
    def __init__(self):
        # Set headless=False during development to see what's happening
        super().__init__("Fisher Scientific (Browser)", headless=True)
    
    def search(self, cas_number: str) -> List[SDSMetadata]:
        """Search Fisher using browser automation."""
        results = []
        
        try:
            page = self._get_page()
            
            # Navigate and search
            page.goto(self.SEARCH_URL, wait_until='networkidle')
            
            # Fill search form
            page.fill('input[name="msdsKeyword"]', cas_number)
            page.click('button[type="submit"]')
            
            # Wait for results
            page.wait_for_selector('.search-results', timeout=10000)
            
            # Extract SDS links
            links = page.query_selector_all('a[href*="sds"], a[href*="msds"]')
            
            for link in links[:5]:  # Limit to first 5 results
                href = link.get_attribute('href')
                if not href:
                    continue
                    
                full_url = href if href.startswith('http') else f"{self.BASE_URL}{href}"
                title = link.text_content().strip() or f"SDS for {cas_number}"
                
                results.append(SDSMetadata(
                    title=title,
                    url=full_url,
                    source=self.name,
                    cas_number=cas_number,
                    manufacturer="Fisher Scientific",
                ))
            
            page.close()
            logger.info("Found %d results for CAS %s", len(results), cas_number)
            
        except Exception as exc:
            logger.warning("Browser search failed for %s: %s", cas_number, exc)
        
        return results
