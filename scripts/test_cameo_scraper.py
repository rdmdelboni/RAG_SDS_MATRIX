#!/usr/bin/env python3
"""
Quick test script to validate CAMEO scraper without full ingestion.

This tests:
1. Network connectivity to CAMEO
2. HTML parsing capabilities
3. Data extraction logic
4. Ingestion integration

Run this BEFORE doing full ingestion to ensure everything works.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add src to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

# Check dependencies
try:
    from bs4 import BeautifulSoup
    import requests

    print("✓ BeautifulSoup4 and requests available")
except ImportError as e:
    print(f"✗ Missing dependency: {e}")
    print("  Install with: pip install beautifulsoup4 requests")
    sys.exit(1)

from scripts.ingest_cameo_chemicals import CAMEOScraper, ChemicalData


def test_network():
    """Test network connectivity to CAMEO."""
    print("\n1️⃣  Testing network connectivity...")
    try:
        response = requests.get("https://cameochemicals.noaa.gov", timeout=10)
        if response.status_code == 200:
            print("   ✓ CAMEO is reachable")
            return True
        else:
            print(f"   ✗ CAMEO returned status {response.status_code}")
            return False
    except Exception as e:
        print(f"   ✗ Cannot reach CAMEO: {e}")
        return False


def test_browse_page():
    """Test fetching a browse page."""
    print("\n2️⃣  Testing browse page parsing...")
    try:
        scraper = CAMEOScraper(timeout=15, delay=0.5)
        chemical_ids = scraper.fetch_chemical_ids("A")
        scraper.close()

        if chemical_ids:
            print(f"   ✓ Found {len(chemical_ids)} chemicals starting with 'A'")
            print(f"     Sample IDs: {', '.join(chemical_ids[:5])}")
            return True
        else:
            print("   ✗ No chemicals found for letter 'A'")
            return False
    except Exception as e:
        print(f"   ✗ Error fetching browse page: {e}")
        return False


def test_chemical_parsing():
    """Test parsing a single chemical page."""
    print("\n3️⃣  Testing chemical data extraction...")
    try:
        scraper = CAMEOScraper(timeout=15, delay=0.5)

        # Test with a known chemical (Acetone)
        print("   Fetching Acetone (ID: 18052)...")
        chem_data = scraper.fetch_chemical_data("18052")
        scraper.close()

        if chem_data and chem_data.name:
            print(f"   ✓ Successfully parsed chemical: {chem_data.name}")
            print(f"     - CAS: {chem_data.cas_number or 'not found'}")
            print(f"     - Hazards found: {len(chem_data.primary_hazards)}")
            print(
                f"     - NFPA rating: {chem_data.nfpa_rating if chem_data.nfpa_rating else 'not found'}"
            )

            # Show extracted text preview
            text = chem_data.to_text()
            print(f"     - Text length: {len(text)} chars")
            print(f"\n     Preview:\n{text[:300]}...")

            return True
        else:
            print("   ✗ Failed to parse chemical data")
            return False
    except Exception as e:
        print(f"   ✗ Error parsing chemical: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_ingestion_integration():
    """Test that ingestion service is available."""
    print("\n4️⃣  Testing ingestion integration...")
    try:
        from src.rag.ingestion_service import KnowledgeIngestionService
        from src.rag.vector_store import get_vector_store
        from src.database import get_db_manager

        service = KnowledgeIngestionService()
        vector_store = get_vector_store()
        db = get_db_manager()

        print("   ✓ Ingestion service initialized")
        print(f"     - Vector store type: {type(vector_store).__name__}")
        print(
            f"     - Database: {db.db_path if hasattr(db, 'db_path') else 'initialized'}"
        )

        # Get current stats
        try:
            stats = db.get_statistics()
            print(f"     - Current RAG documents: {stats.get('rag_documents', 0)}")
            print(f"     - Current chunks: {stats.get('rag_documents', 0)}")  # Approx
        except Exception:
            print("     - Database stats: (not available)")

        return True
    except Exception as e:
        print(f"   ✗ Error with ingestion service: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("=" * 70)
    print("  🧪 CAMEO Scraper Validation Test")
    print("=" * 70)

    results = {
        "network": test_network(),
        "browse": test_browse_page(),
        "parsing": test_chemical_parsing(),
        "ingestion": test_ingestion_integration(),
    }

    # Summary
    print("\n" + "=" * 70)
    print("📊 TEST SUMMARY")
    print("=" * 70)

    test_names = {
        "network": "Network Connectivity",
        "browse": "Browse Page Parsing",
        "parsing": "Chemical Data Extraction",
        "ingestion": "Ingestion Integration",
    }

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for key, name in test_names.items():
        status = "✓ PASS" if results[key] else "✗ FAIL"
        print(f"{status} - {name}")

    print("=" * 70)
    print(f"\nResult: {passed}/{total} tests passed")

    if passed == total:
        print("\n✅ All tests passed! You can run the full ingestion:")
        print("   python scripts/ingest_cameo_chemicals.py\n")
        return 0
    else:
        print("\n❌ Some tests failed. Check the output above for details.")
        print("   Common issues:")
        print("   - Network: Check your internet connection")
        print("   - Parsing: CAMEO website structure may have changed")
        print("   - Ingestion: Check your database and vector store setup\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
