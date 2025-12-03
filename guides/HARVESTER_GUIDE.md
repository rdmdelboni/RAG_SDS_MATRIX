# SDS Harvester Guide

The SDS Harvester is a new module designed to automate the discovery and downloading of Safety Data Sheets (SDS) from the web using CAS numbers.

## Features

- **Multi-Provider Architecture**: Extensible design allowing multiple data sources.
- **Current Providers**:
  - Fisher Scientific (Scraping)
  - ChemicalBook (Scraping)
  - ChemicalSafety.com (Scraping)
  - ChemBlink (Scraping)
  - VWR / Avantor (Scraping)
  - TCI Chemicals (Scraping)
  - Fluorochem (Scraping)
- **CLI Tool**: Easy-to-use command line interface.
- **Provenance Logging**: Downloads are recorded in DuckDB (`harvester_downloads`) with source URL and status.
- **Optional Sync**:
  - Copy mode: `OE_SYNC_ENABLED=true` and `OE_SYNC_EXPORT_DIR=/path/to/stage` to copy downloaded SDS files.
  - MySQL mode: `OE_SYNC_ENABLED=true`, `OE_SYNC_MODE=mysql`, and set `OE_SYNC_DB_HOST/PORT/USER/PASSWORD/DB_NAME` to push SDS blobs into an Open Enventory–style table (defaults: table `molecule`, `cas_nr` CAS field, `default_safety_sheet_blob` blob field).
  - Missing marker: set `OE_SYNC_MISSING_TABLE` (and optional `OE_SYNC_MISSING_CAS_FIELD`) to log missing CAS entries when downloads fail.

## Usage

Run the `fetch_sds.py` script from the project root:

```bash
./scripts/fetch_sds.py [CAS_NUMBER_1] [CAS_NUMBER_2] ...
```

### Example

```bash
./scripts/fetch_sds.py 67-64-1 7664-93-9 --output data/input/new_sds
```

## Implementation Details

The core logic resides in `src/harvester/`.
- `base.py`: Defines the `BaseSDSProvider` interface.
- `core.py`: Manages providers and parallel execution.
- `providers/`: Contains specific provider implementations.
- Downloads are logged to DuckDB (`harvester_downloads` table) via `scripts/fetch_sds.py` for provenance/trust tracking.

## Bot Protection Solution

Many chemical vendors implement bot detection (JavaScript challenges, CAPTCHAs, fingerprinting). For providers that block `requests`, use **Browser Providers** with Playwright.

### Browser vs Regular Providers

**Regular Providers** (`BaseSDSProvider`):
- Fast HTTP requests with `requests` library
- Suitable for simple HTML scraping
- Lower resource usage
- May be blocked by sophisticated bot protection

**Browser Providers** (`BrowserSDSProvider`):
- Full browser automation with Playwright
- JavaScript execution, CAPTCHA handling
- Realistic user behavior simulation
- Higher resource usage but better success rates

### Migrating to Browser Providers

**1. Install Playwright:**
```bash
pip install playwright
playwright install chromium
```

**2. Convert Provider to Browser-Based:**

Before (Regular Provider):
```python
from src.harvester.base import BaseSDSProvider

class FisherProvider(BaseSDSProvider):
    def search(self, cas_number: str) -> Optional[str]:
        response = requests.get(f"{self.base_url}/search?q={cas_number}")
        # Parse HTML...
        return sds_url
```

After (Browser Provider):
```python
from src.harvester.browser_provider import BrowserSDSProvider

class FisherBrowserProvider(BrowserSDSProvider):
    base_url = "https://www.fishersci.com"
    
    def search(self, cas_number: str) -> Optional[str]:
        page = self._get_page()
        
        # Navigate and interact
        page.goto(f"{self.base_url}/us/en/catalog/search/sds")
        page.fill('input[name="q"]', cas_number)
        page.click('button[type="submit"]')
        page.wait_for_load_state("networkidle")
        
        # Extract SDS URL
        sds_link = page.locator('a:has-text("View SDS")').first
        if sds_link.is_visible():
            return sds_link.get_attribute("href")
        return None
    
    def download(self, url: str, output_path: Path) -> bool:
        page = self._get_page()
        
        # Handle download
        with page.expect_download() as download_info:
            page.goto(url)
        
        download = download_info.value
        download.save_as(output_path)
        return output_path.exists()
```

**3. Anti-Detection Features (Built-in):**

The `BrowserSDSProvider` base class automatically applies:
- ✅ Stealth mode (disables `navigator.webdriver`)
- ✅ Realistic browser fingerprint
- ✅ Natural timing (human-like delays)
- ✅ JavaScript execution
- ✅ Cookie/session persistence

**4. Resource Management:**

Always use context manager to properly clean up:
```python
with FisherBrowserProvider() as provider:
    results = provider.search("67-64-1")
```

Or explicit cleanup:
```python
provider = FisherBrowserProvider()
try:
    results = provider.search("67-64-1")
finally:
    provider.close()
```

### Performance Considerations

- **Browser providers are slower**: ~2-5 seconds per search (vs ~0.5s for requests)
- **Resource intensive**: Each browser instance uses ~100-200MB RAM
- **Best practices**:
  - Use browser providers only when necessary (when requests fail)
  - Reuse provider instances across multiple searches
  - Implement provider fallback chain (try fast first, then browser)

### Example: Hybrid Provider Strategy

```python
from src.harvester.core import HarvesterCore
from src.harvester.providers import FisherProvider
from src.harvester.browser_provider import FisherBrowserProvider

# Try fast provider first
harvester = HarvesterCore()
harvester.register_provider(FisherProvider())

result = harvester.fetch_sds("67-64-1")

if not result:
    # Fallback to browser provider if blocked
    harvester.register_provider(FisherBrowserProvider(), priority=100)
    result = harvester.fetch_sds("67-64-1")
```

### Debugging Bot Protection

**Check if site blocks requests:**
```bash
# Test with curl
curl -I "https://www.fishersci.com/search?q=67-64-1"

# If you get 403/404, try with browser headers
curl -H "User-Agent: Mozilla/5.0..." "https://..."
```

**Common blocking indicators:**
- HTTP 403 Forbidden
- HTTP 429 Too Many Requests
- Redirect to CAPTCHA page
- JavaScript challenge pages
- Empty response body

**Solution: Switch to browser provider for that vendor.**

## Implementation Details

The core logic resides in `src/harvester/`.
- `base.py`: Defines the `BaseSDSProvider` interface for regular providers.
- `browser_provider.py`: Defines the `BrowserSDSProvider` base class for browser automation.
- `core.py`: Manages providers and parallel execution.
- `providers/`: Contains specific provider implementations.
- Downloads are logged to DuckDB (`harvester_downloads` table) via inventory sync for provenance/trust tracking.
