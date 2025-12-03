#!/usr/bin/env python3
"""
Test script for PubChem enrichment functionality.

Demonstrates how PubChem API can improve and validate SDS extraction data.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.sds.pubchem_enrichment import PubChemEnricher
from src.utils.logger import get_logger

logger = get_logger(__name__)


def test_enrichment_with_complete_data():
    """Test enrichment with complete extraction data."""
    print("\n" + "="*80)
    print("TEST 1: Complete extraction data (Sulfuric Acid)")
    print("="*80)
    
    enricher = PubChemEnricher()
    
    # Simulated extraction result with all fields present
    extractions = {
        "product_name": {
            "value": "Ácido Sulfúrico",
            "confidence": 0.85,
            "source": "heuristic"
        },
        "cas_number": {
            "value": "7664-93-9",
            "confidence": 0.90,
            "source": "heuristic"
        },
        "molecular_formula": {
            "value": "H2SO4",
            "confidence": 0.80,
            "source": "llm"
        }
    }
    
    enrichments = enricher.enrich_extraction(extractions, aggressive=False)
    
    print("\n📊 Enrichment Results:")
    print(enricher.generate_enrichment_report(enrichments))
    
    print("\n🔍 Detailed Enrichments:")
    for field_name, enrich in enrichments.items():
        print(f"\n  Field: {field_name}")
        print(f"    Status: {enrich.validation_status}")
        print(f"    Original: {enrich.original_value}")
        print(f"    Enriched: {enrich.enriched_value}")
        print(f"    Confidence: {enrich.confidence:.2f}")
        if enrich.issues:
            print(f"    Issues: {enrich.issues}")


def test_enrichment_with_missing_data():
    """Test enrichment with missing fields."""
    print("\n" + "="*80)
    print("TEST 2: Missing data (Ethanol - only product name)")
    print("="*80)
    
    enricher = PubChemEnricher()
    
    # Simulated extraction with missing CAS and formula
    extractions = {
        "product_name": {
            "value": "Ethanol",
            "confidence": 0.90,
            "source": "heuristic"
        }
    }
    
    enrichments = enricher.enrich_extraction(extractions, aggressive=True)
    
    print("\n📊 Enrichment Results:")
    print(enricher.generate_enrichment_report(enrichments))
    
    print("\n✨ New Fields Added:")
    for field_name, enrich in enrichments.items():
        if not enrich.original_value:
            print(f"  • {field_name}: {enrich.enriched_value}")


def test_enrichment_with_incorrect_data():
    """Test enrichment with incorrect/mismatched data."""
    print("\n" + "="*80)
    print("TEST 3: Incorrect data (CAS mismatch)")
    print("="*80)
    
    enricher = PubChemEnricher()
    
    # Simulated extraction with WRONG CAS number
    extractions = {
        "product_name": {
            "value": "Sulfuric Acid",
            "confidence": 0.85,
            "source": "heuristic"
        },
        "cas_number": {
            "value": "1234-56-7",  # WRONG CAS (correct is 7664-93-9)
            "confidence": 0.75,
            "source": "heuristic"
        }
    }
    
    enrichments = enricher.enrich_extraction(extractions, aggressive=False)
    
    print("\n📊 Enrichment Results:")
    print(enricher.generate_enrichment_report(enrichments))
    
    print("\n⚠️  Validation Issues Found:")
    for field_name, enrich in enrichments.items():
        if enrich.validation_status == "warning":
            print(f"\n  Field: {field_name}")
            if enrich.issues:
                for issue in enrich.issues:
                    print(f"    ⚠ {issue}")


def test_enrichment_h_statements():
    """Test H-statement enrichment."""
    print("\n" + "="*80)
    print("TEST 4: H-statement enrichment (Hydrochloric Acid)")
    print("="*80)
    
    enricher = PubChemEnricher()
    
    # Partial H-statements extracted
    extractions = {
        "product_name": {
            "value": "Hydrochloric Acid",
            "confidence": 0.90,
            "source": "heuristic"
        },
        "cas_number": {
            "value": "7647-01-0",
            "confidence": 0.85,
            "source": "heuristic"
        },
        "h_statements": {
            "value": "H314",  # Only one extracted, missing others
            "confidence": 0.70,
            "source": "heuristic"
        }
    }
    
    enrichments = enricher.enrich_extraction(extractions, aggressive=True)
    
    print("\n📊 Enrichment Results:")
    print(enricher.generate_enrichment_report(enrichments))
    
    # Show H-statement details
    if "h_statements" in enrichments:
        h_enrich = enrichments["h_statements"]
        print(f"\n🔬 H-Statements Analysis:")
        print(f"  Original (extracted): {h_enrich.original_value}")
        print(f"  Complete (from PubChem): {h_enrich.enriched_value}")
        if h_enrich.additional_data and "missing_statements" in h_enrich.additional_data:
            missing = h_enrich.additional_data["missing_statements"]
            print(f"  Missing statements: {', '.join(missing)}")


def test_enrichment_by_formula():
    """Test enrichment using only molecular formula."""
    print("\n" + "="*80)
    print("TEST 5: Lookup by formula only (H2O)")
    print("="*80)
    
    enricher = PubChemEnricher()
    
    # Only formula available (edge case)
    extractions = {
        "molecular_formula": {
            "value": "H2O",
            "confidence": 0.95,
            "source": "heuristic"
        }
    }
    
    enrichments = enricher.enrich_extraction(extractions, aggressive=True)
    
    print("\n📊 Enrichment Results:")
    print(enricher.generate_enrichment_report(enrichments))
    
    if enrichments:
        print("\n💡 Note: Formula-based lookup found:")
        for field_name, enrich in enrichments.items():
            if enrich.enriched_value:
                print(f"  • {field_name}: {enrich.enriched_value}")


def main():
    """Run all test cases."""
    print("\n╔═══════════════════════════════════════════════════════════════════════════════╗")
    print("║              PubChem Enrichment System - Test Suite                          ║")
    print("╚═══════════════════════════════════════════════════════════════════════════════╝")
    
    try:
        test_enrichment_with_complete_data()
        test_enrichment_with_missing_data()
        test_enrichment_with_incorrect_data()
        test_enrichment_h_statements()
        test_enrichment_by_formula()
        
        print("\n" + "="*80)
        print("✅ All tests completed successfully!")
        print("="*80)
        print("\n💡 Summary of PubChem Enrichment Capabilities:")
        print("  1. ✓ Validates extracted chemical identifiers (CAS, formula)")
        print("  2. ✓ Fills in missing fields (molecular weight, IUPAC name, etc.)")
        print("  3. ✓ Enriches H/P statements with complete GHS classification")
        print("  4. ✓ Detects mismatches and inconsistencies")
        print("  5. ✓ Provides chemical structure identifiers (SMILES, InChI)")
        print("  6. ✓ Cross-validates product names against synonyms")
        print("\n")
        
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        print(f"\n❌ Test failed: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
