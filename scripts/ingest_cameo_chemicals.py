#!/usr/bin/env python3
"""
Ingest all CAMEO chemical data sheets from https://cameochemicals.noaa.gov/browse/A-Z

This script:
1. Fetches all chemical IDs from browse pages (A-Z)
2. Extracts chemical details from individual sheets
3. Ingests the data into the RAG knowledge base with proper chunking
4. Provides progress tracking and error handling

Uses only free libraries: requests + BeautifulSoup4
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

# Add src to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

try:
    from bs4 import BeautifulSoup
    import requests
except ImportError as e:
    print(f"Error: Missing required library: {e}")
    print("Install with: pip install beautifulsoup4 requests")
    sys.exit(1)

from src.rag.ingestion_service import KnowledgeIngestionService
from src.utils.logger import get_logger

logger = get_logger("ingest_cameo_chemicals")

# CAMEO base URLs
CAMEO_BASE = "https://cameochemicals.noaa.gov"
CAMEO_BROWSE = f"{CAMEO_BASE}/browse"
CAMEO_CHEMICAL = f"{CAMEO_BASE}/chemical"


@dataclass
class ChemicalData:
    """Data extracted from a chemical sheet."""

    id: str
    name: str
    cas_number: str | None = None
    synonyms: list[str] = field(default_factory=list)
    hazard_summary: str = ""
    health_hazard: str = ""
    fire_hazard: str = ""
    reactivity_hazard: str = ""
    primary_hazards: list[str] = field(default_factory=list)
    nfpa_rating: dict[str, int] = field(default_factory=dict)
    url: str = ""

    def to_text(self) -> str:
        """Convert chemical data to formatted text for ingestion."""
        lines = [
            f"Chemical: {self.name}",
            f"ID: {self.id}",
        ]

        if self.cas_number:
            lines.append(f"CAS Number: {self.cas_number}")

        if self.synonyms:
            lines.append(f"Synonyms: {', '.join(self.synonyms)}")

        if self.hazard_summary:
            lines.append(f"\nHazard Summary:\n{self.hazard_summary}")

        if self.health_hazard:
            lines.append(f"\nHealth Hazard:\n{self.health_hazard}")

        if self.fire_hazard:
            lines.append(f"\nFire Hazard:\n{self.fire_hazard}")

        if self.reactivity_hazard:
            lines.append(f"\nReactivity Hazard:\n{self.reactivity_hazard}")

        if self.primary_hazards:
            lines.append(f"\nPrimary Hazards: {', '.join(self.primary_hazards)}")

        if self.nfpa_rating:
            lines.append(f"\nNFPA Rating: {json.dumps(self.nfpa_rating)}")

        lines.append(f"\nSource: {self.url}")

        return "\n".join(lines)


class CAMEOScraper:
    """Scraper for CAMEO chemicals database using BeautifulSoup."""

    def __init__(self, timeout: int = 30, delay: float = 1.0):
        """Initialize scraper with IP protection.

        Args:
            timeout: Request timeout in seconds
            delay: Delay between requests in seconds (rate limiting - be respectful!)
        """
        self.timeout = timeout
        self.delay = delay
        self.request_count = 0
        self.max_requests_per_minute = 60
        self.last_request_time = 0
        self.session = requests.Session()

        # Rotate User-Agent to avoid detection
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:91.0) Gecko/20100101 Firefox/91.0",
        ]

        # Configure session with retry strategy
        retry_strategy = requests.adapters.Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"],
        )
        adapter = requests.adapters.HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        self._update_headers()

    def _update_headers(self):
        """Update session headers with rotating User-Agent."""
        import random

        self.session.headers.update(
            {
                "User-Agent": random.choice(self.user_agents),
                "Accept": "text/html,application/xhtml+xml,*/*;q=0.9",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "DNT": "1",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Cache-Control": "max-age=0",
            }
        )

    def _rate_limit_check(self):
        """Enforce rate limiting to prevent IP banning."""
        import random
        import time as time_module

        current_time = time_module.time()
        # Add random jitter (±20%) to delay to appear more human-like
        jitter = self.delay * random.uniform(0.8, 1.2)

        if current_time - self.last_request_time < jitter:
            sleep_time = jitter - (current_time - self.last_request_time)
            logger.debug(f"Rate limiting: sleeping {sleep_time:.2f}s")
            time_module.sleep(sleep_time)

        self.last_request_time = time_module.time()
        self.request_count += 1

    def fetch_chemical_ids(self, letter: str) -> list[str]:
        """Fetch all chemical IDs for a given letter using BeautifulSoup.

        Args:
            letter: Single letter (A-Z)

        Returns:
            List of chemical IDs
        """
        if not letter or len(letter) != 1 or not letter.isalpha():
            raise ValueError("Letter must be single character A-Z")

        url = f"{CAMEO_BROWSE}/{letter}"
        logger.info(f"Fetching chemical IDs for letter '{letter}' from {url}")

        try:
            self._rate_limit_check()  # Enforce rate limiting
            self._update_headers()  # Rotate User-Agent
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            logger.debug(f"Got response: {response.status_code}")
        except Exception as exc:
            logger.error(f"Failed to fetch browse page for '{letter}': {exc}")
            return []

        chemical_ids = []
        try:
            soup = BeautifulSoup(response.text, "html.parser")

            # CAMEO lists chemicals in a table or div structure
            # Look for all links that point to chemical pages
            for link in soup.find_all("a", href=True):
                href = link.get("href", "")
                # CAMEO chemical links are like /chemical/18052
                if "/chemical/" in href:
                    parts = href.split("/chemical/")
                    if len(parts) > 1:
                        chem_id = (
                            parts[-1].strip("/").split("?")[0]
                        )  # Remove query params
                        if chem_id.isdigit():
                            chemical_ids.append(chem_id)

            # Remove duplicates while preserving order
            seen = set()
            unique_ids = []
            for cid in chemical_ids:
                if cid not in seen:
                    seen.add(cid)
                    unique_ids.append(cid)

            logger.info(
                f"Found {len(unique_ids)} unique chemicals for letter '{letter}'"
            )
            return unique_ids

        except Exception as exc:
            logger.error(f"Error parsing browse page for '{letter}': {exc}")
            return []

    def fetch_chemical_data(self, chemical_id: str) -> ChemicalData | None:
        """Fetch detailed data for a single chemical using BeautifulSoup.

        Args:
            chemical_id: CAMEO chemical ID

        Returns:
            ChemicalData object or None if fetch failed
        """
        url = f"{CAMEO_CHEMICAL}/{chemical_id}"

        try:
            self._rate_limit_check()  # Enforce rate limiting
            self._update_headers()  # Rotate User-Agent
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
        except Exception as exc:
            logger.warning(f"Failed to fetch chemical {chemical_id}: {exc}")
            return None

        try:
            soup = BeautifulSoup(response.text, "html.parser")

            # Extract chemical name (usually in h1 or title)
            name = ""
            h1 = soup.find("h1")
            if h1:
                name = h1.get_text(strip=True)

            if not name:
                # Try to get from page title
                title_tag = soup.find("title")
                if title_tag:
                    title_text = title_tag.get_text(strip=True)
                    # Remove suffix like " - CAMEO Chemicals"
                    name = title_text.split(" - ")[0].strip()

            if not name:
                logger.warning(f"Could not extract name for chemical {chemical_id}")
                return None

            # Extract CAS number
            cas_number = self._extract_cas_number(soup)

            # Extract synonyms
            synonyms = self._extract_synonyms(soup)

            # Extract hazard sections
            hazard_summary = self._extract_section(
                soup, ["Hazard Summary", "Hazards", "Overview"]
            )
            health_hazard = self._extract_section(
                soup, ["Health Hazard", "Health Effects", "Health"]
            )
            fire_hazard = self._extract_section(
                soup, ["Fire Hazard", "Fire", "Flammability"]
            )
            reactivity_hazard = self._extract_section(
                soup, ["Reactivity", "Stability", "Incompatibility"]
            )

            # Extract primary hazards
            primary_hazards = self._extract_primary_hazards(soup)

            # Extract NFPA rating
            nfpa_rating = self._extract_nfpa_rating(soup)

            return ChemicalData(
                id=chemical_id,
                name=name,
                cas_number=cas_number,
                synonyms=synonyms,
                hazard_summary=hazard_summary,
                health_hazard=health_hazard,
                fire_hazard=fire_hazard,
                reactivity_hazard=reactivity_hazard,
                primary_hazards=primary_hazards,
                nfpa_rating=nfpa_rating,
                url=url,
            )

        except Exception as exc:
            logger.error(f"Error parsing chemical {chemical_id}: {exc}")
            return None

    def _extract_cas_number(self, soup) -> str | None:
        """Extract CAS number from soup using BeautifulSoup."""
        import re

        # Look for CAS number patterns in text
        text = soup.get_text()
        # CAS format: 1234567-12-3
        cas_match = re.search(r"(\d{1,7}-\d{1,2}-\d)", text)
        if cas_match:
            return cas_match.group(1)

        # Also try in specific elements
        for elem in soup.find_all(["td", "dd", "span", "p"]):
            if elem:
                elem_text = elem.get_text(strip=True)
                if "CAS" in elem_text:
                    match = re.search(r"(\d{1,7}-\d{1,2}-\d)", elem_text)
                    if match:
                        return match.group(1)

        return None

    def _extract_synonyms(self, soup) -> list[str]:
        """Extract synonyms from soup."""
        synonyms = []
        try:
            import re

            text = soup.get_text()

            # Look for lines with "Other names" or "Synonym"
            for line in text.split("\n"):
                line = line.strip()
                if any(
                    x in line for x in ["Other names:", "Synonyms:", "Also known as"]
                ):
                    # Extract the part after the label
                    parts = re.split(r"Other names:|Synonyms:|Also known as", line)
                    if len(parts) > 1:
                        syn_text = parts[-1].strip()
                        # Split by comma or semicolon
                        raw_syns = re.split(r"[,;]", syn_text)
                        for syn in raw_syns:
                            syn = syn.strip()
                            if syn and len(syn) > 2 and len(syn) < 100:
                                synonyms.append(syn)
                                if len(synonyms) >= 5:  # Limit to 5
                                    break
                    if synonyms:
                        break

        except Exception as exc:
            logger.debug(f"Error extracting synonyms: {exc}")

        return synonyms

    def _extract_section(self, soup, section_names: list[str]) -> str:
        """Extract a section by heading name using BeautifulSoup."""
        try:
            # Look for headings (h1, h2, h3, h4, h5, h6)
            for heading_tag in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
                heading_text = heading_tag.get_text(strip=True)
                # Check if any section name matches (case-insensitive)
                if any(name.lower() in heading_text.lower() for name in section_names):
                    # Get text until next heading
                    content = []
                    for sibling in heading_tag.find_next_siblings():
                        # Stop at next heading
                        if sibling.name and sibling.name in [
                            "h1",
                            "h2",
                            "h3",
                            "h4",
                            "h5",
                            "h6",
                        ]:
                            break
                        # Get text from paragraphs, divs, etc.
                        if sibling.name in ["p", "div", "li", "td"]:
                            text = sibling.get_text(strip=True)
                            if text and len(text) > 10:
                                content.append(text)
                                if len(content) >= 3:  # Limit to 3 paragraphs
                                    break

                    result = "\n".join(content)
                    if result:
                        return result[:500]  # Limit to 500 chars per section

        except Exception as exc:
            logger.debug(f"Error extracting section: {exc}")

        return ""

    def _extract_primary_hazards(self, soup) -> list[str]:
        """Extract primary hazard classifications using BeautifulSoup."""
        hazards = []
        try:
            # Look for hazard-related keywords
            text = soup.get_text()
            hazard_keywords = [
                "Flammable",
                "Explosive",
                "Oxidizer",
                "Toxic",
                "Corrosive",
                "Irritant",
                "Sensitizer",
                "Carcinogenic",
                "Mutagen",
                "Reproductive",
                "Target Organ",
                "Hazardous to Environment",
                "Acute Toxicity",
                "Chronic Toxicity",
                "Eye Damage",
            ]

            for keyword in hazard_keywords:
                # Case-insensitive search
                if keyword.lower() in text.lower():
                    hazards.append(keyword)

        except Exception as exc:
            logger.debug(f"Error extracting hazards: {exc}")

        return list(set(hazards))  # Remove duplicates

    def _extract_nfpa_rating(self, soup) -> dict[str, int]:
        """Extract NFPA rating diamond if available."""
        nfpa = {}
        try:
            import re

            text = soup.get_text()

            # Look for NFPA numbers (usually 0-4)
            # Pattern: "Health: 3" or "Flammability = 2"
            patterns = [
                (r"Health\s*[:\=]?\s*(\d)", "health"),
                (r"Flammability\s*[:\=]?\s*(\d)", "flammability"),
                (r"Instability\s*[:\=]?\s*(\d)", "instability"),
                (r"Reactivity\s*[:\=]?\s*(\d)", "reactivity"),
                (r"Special\s*[:\=]?\s*(\d)", "special"),
            ]

            for pattern, label in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    try:
                        nfpa[label] = int(match.group(1))
                    except ValueError:
                        pass

        except Exception as exc:
            logger.debug(f"Error extracting NFPA rating: {exc}")

        return nfpa

    def close(self):
        """Close the session."""
        if self.session:
            self.session.close()


class CAMEOIngester:
    """Manages ingestion of CAMEO data into the knowledge base."""

    def __init__(self):
        self.service = KnowledgeIngestionService()
        self.scraper = CAMEOScraper()
        self.stats = {
            "total_chemicals": 0,
            "successfully_scraped": 0,
            "successfully_ingested": 0,
            "failed": 0,
            "skipped": 0,
            "errors": [],
        }

    def ingest_all_chemicals(
        self, letters: str = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    ) -> dict[str, Any]:
        """Ingest all chemicals for the given letters.

        Args:
            letters: String of letters to process (default: A-Z)

        Returns:
            Statistics dictionary
        """
        logger.info("=" * 70)
        logger.info("CAMEO Chemical Ingestion - Starting")
        logger.info("=" * 70)

        start_time = time.time()

        for letter in letters.upper():
            self._ingest_letter(letter)
            # Delay between letters to be respectful to server
            time.sleep(2)

        elapsed = time.time() - start_time

        logger.info("=" * 70)
        logger.info("CAMEO Chemical Ingestion - Complete")
        logger.info(f"Total time: {elapsed:.1f} seconds")
        logger.info("=" * 70)
        self._print_stats()

        return self.stats

    def _ingest_letter(self, letter: str):
        """Ingest all chemicals starting with a letter."""
        logger.info(f"\n### Processing letter '{letter}' ###")

        # Get chemical IDs for this letter
        chemical_ids = self.scraper.fetch_chemical_ids(letter)

        if not chemical_ids:
            logger.warning(f"No chemicals found for letter '{letter}'")
            return

        self.stats["total_chemicals"] += len(chemical_ids)
        logger.info(f"Found {len(chemical_ids)} chemicals")

        # Process each chemical
        for idx, chem_id in enumerate(chemical_ids, 1):
            logger.debug(
                f"[{idx}/{len(chemical_ids)}] Processing chemical {chem_id}..."
            )

            # Fetch chemical data
            chem_data = self.scraper.fetch_chemical_data(chem_id)

            if not chem_data:
                self.stats["failed"] += 1
                logger.warning(f"Failed to scrape chemical {chem_id}")
                continue

            self.stats["successfully_scraped"] += 1

            # Ingest into knowledge base
            try:
                text = chem_data.to_text()
                metadata = {
                    "source": chem_data.url,
                    "title": chem_data.name,
                    "type": "cameo_chemical",
                    "chemical_id": chem_id,
                    "cas_number": chem_data.cas_number or "unknown",
                    "hazards": (
                        ",".join(chem_data.primary_hazards)
                        if chem_data.primary_hazards
                        else "none"
                    ),
                }

                # Use the ingestion service to handle chunking and deduplication
                from langchain_core.documents import Document

                doc = Document(page_content=text, metadata=metadata)
                chunks = self.service.chunker.chunk_documents([doc])

                if chunks:
                    self.service.vector_store.add_documents(chunks)
                    self.service.db.register_rag_document(
                        source_type="cameo_chemical",
                        source_url=chem_data.url,
                        title=chem_data.name,
                        chunk_count=len(chunks),
                        content_hash=self.service._hash_text(text),
                        metadata=metadata,
                    )
                    self.stats["successfully_ingested"] += 1
                    logger.info(
                        f"✓ Ingested: {chem_data.name} (ID: {chem_id}, {len(chunks)} chunks)"
                    )
                else:
                    self.stats["skipped"] += 1
                    logger.warning(f"No chunks created for {chem_id}")

            except Exception as exc:
                self.stats["failed"] += 1
                error_msg = f"Ingestion failed for {chem_id}: {str(exc)[:100]}"
                logger.error(error_msg)
                self.stats["errors"].append(error_msg)

    def _print_stats(self):
        """Print final statistics."""
        print("\n" + "=" * 70)
        print("📊 INGESTION STATISTICS")
        print("=" * 70)
        print(f"Total Chemicals Found:      {self.stats['total_chemicals']}")
        print(f"Successfully Scraped:       {self.stats['successfully_scraped']}")
        print(f"Successfully Ingested:      {self.stats['successfully_ingested']}")
        print(f"Failed to Scrape:           {self.stats['failed']}")
        print(f"Skipped (no chunks):        {self.stats['skipped']}")

        success_rate = (
            (self.stats["successfully_ingested"] / self.stats["total_chemicals"] * 100)
            if self.stats["total_chemicals"] > 0
            else 0
        )
        print(f"\nSuccess Rate:               {success_rate:.1f}%")

        if self.stats["errors"]:
            print(f"\n⚠️  Errors ({len(self.stats['errors'])}):")
            for error in self.stats["errors"][:10]:  # Show first 10 errors
                print(f"  - {error}")
            if len(self.stats["errors"]) > 10:
                print(f"  ... and {len(self.stats['errors']) - 10} more")

        print("=" * 70)

    def cleanup(self):
        """Clean up resources."""
        self.scraper.close()


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Ingest CAMEO chemical data sheets into RAG knowledge base",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Ingest all chemicals (A-Z)
  python ingest_cameo_chemicals.py

  # Ingest only specific letters
  python ingest_cameo_chemicals.py --letters ABC

  # Start from specific letter (useful for resuming)
  python ingest_cameo_chemicals.py --start M

  # Adjust request timing
  python ingest_cameo_chemicals.py --timeout 60 --delay 2.0
        """,
    )
    parser.add_argument(
        "--letters",
        type=str,
        default="ABCDEFGHIJKLMNOPQRSTUVWXYZ",
        help="Letters to process (default: A-Z)",
    )
    parser.add_argument(
        "--start",
        type=str,
        default=None,
        help="Start from specific letter (e.g., M to start from M-Z)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Request timeout in seconds (default: 30)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Delay between requests in seconds (default: 1.0 - be respectful!)",
    )

    args = parser.parse_args()

    letters = args.letters.upper()

    # Handle --start option
    if args.start:
        start_idx = letters.find(args.start.upper())
        if start_idx != -1:
            letters = letters[start_idx:]
        else:
            print(f"Error: Letter '{args.start}' not found in range")
            return 1

    print("\n" + "=" * 70)
    print("  🧪 CAMEO Chemical Database Ingestion")
    print("=" * 70)
    print(f"Letters to process: {letters}")
    print(f"Request timeout: {args.timeout}s")
    print(f"Delay between requests: {args.delay}s")
    print(
        f"Estimated time: ~{len(letters) * 60 * args.delay / 60:.0f} minutes (rough estimate)"
    )
    print("=" * 70 + "\n")

    ingester = CAMEOIngester()
    ingester.scraper.timeout = args.timeout
    ingester.scraper.delay = args.delay

    try:
        stats = ingester.ingest_all_chemicals(letters)
        ingester.cleanup()
        return 0 if stats["failed"] == 0 else 1
    except KeyboardInterrupt:
        logger.warning("\n⚠️  Interrupted by user")
        ingester.cleanup()
        print("\nIngestion interrupted. You can resume with:")
        print(f"  python ingest_cameo_chemicals.py --start <next-letter>")
        return 130
    except Exception as exc:
        logger.exception("❌ Unexpected error during ingestion")
        ingester.cleanup()
        return 1


if __name__ == "__main__":
    sys.exit(main())
