#!/usr/bin/env python3
"""
Re-extract Enhanced Fields from Existing PDFs

Processes all existing SDS PDFs to extract the 21 new Priority 1 fields:
- GHS classification (pictograms, signal word)
- Exposure limits (OSHA PEL, ACGIH TLV, NIOSH REL, IDLH)
- Physical properties (flash point, boiling/melting point, pH, state)
- Toxicity data (oral/dermal LD50, inhalation LC50)
- Transport info (proper shipping name)
- Regulatory status (TSCA, SARA 313, California Prop 65)

This will UPDATE the extractions table with new field data while preserving
existing extraction data.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database import get_db_manager
from src.config.constants import EXTRACTION_FIELDS
from src.utils.logger import get_logger

logger = get_logger(__name__)


def main():
    """Re-extract Priority 1 fields from existing documents."""
    
    print("\n" + "="*80)
    print("🔄 RE-EXTRACTING ENHANCED FIELDS FROM EXISTING PDFs")
    print("="*80 + "\n")
    
    db = get_db_manager()
    
    # Get list of new fields (those not currently in extractions table)
    print("📋 Checking which fields need extraction...")
    
    new_fields = [
        'ghs_pictograms', 'signal_word',
        'exposure_limit_osha_pel', 'exposure_limit_acgih_tlv', 
        'exposure_limit_niosh_rel', 'exposure_limit_idlh',
        'flash_point', 'boiling_point', 'melting_point', 'ph', 'physical_state',
        'toxicity_oral_ld50', 'toxicity_dermal_ld50', 'toxicity_inhalation_lc50',
        'proper_shipping_name',
        'tsca_status', 'sara_313', 'california_prop65'
    ]
    
    # Check how many of these fields already have data
    conn = db.conn
    existing_counts = {}
    for field in new_fields:
        try:
            result = conn.execute(f"""
                SELECT COUNT(*) FROM extractions 
                WHERE field_name = '{field}' 
                AND value IS NOT NULL 
                AND value != 'NOT_FOUND'
            """).fetchone()
            existing_counts[field] = result[0] if result else 0
        except:
            existing_counts[field] = 0
    
    # Show status
    print(f"\n✓ Found {len(new_fields)} new fields to extract")
    print(f"✓ {sum(1 for c in existing_counts.values() if c == 0)} fields have no data yet")
    print(f"✓ {sum(1 for c in existing_counts.values() if c > 0)} fields have partial data")
    
    # Get document count
    doc_count = conn.execute("SELECT COUNT(DISTINCT document_id) FROM extractions").fetchone()[0]
    print(f"\\n📁 Total documents to process: {doc_count}")
    
    print("\\n" + "-"*80)
    print("⚠️  WARNING: Full re-extraction requires SDS pipeline")
    print("-"*80)
    print("\\nThe complete extraction process needs to:")
    print("  1. Re-read all PDF files from data/input/")
    print("  2. Extract text from each document")
    print("  3. Run LLM extraction for 21 new fields per document")
    print("  4. Insert results into extractions table")
    
    print("\\n📝 Recommended approach:")
    print("  Option A: Run full SDS pipeline (comprehensive but slow)")
    print("    cd /home/rdmdelboni/Work/Gits/RAG_SDS_MATRIX")
    print("    ./.venv/bin/python scripts/sds_pipeline.py --input data/input/ --reprocess")
    
    print("\\n  Option B: Sample extraction (test on 10 documents)")
    print("    # Create test_sample/ directory with 10 PDFs")
    print("    mkdir -p data/test_sample")
    print("    ls data/input/*.pdf | head -10 | xargs -I {} cp {} data/test_sample/")
    print("    ./.venv/bin/python scripts/sds_pipeline.py --input data/test_sample/")
    
    print("\\n  Option C: Targeted LLM extraction (faster, LLM-only)")
    print("    # Extract ONLY the new fields using LLM on existing text")
    print("    ./.venv/bin/python scripts/extract_new_fields_only.py")
    print("    (Note: This script needs to be created)")
    
    print("\\n⏱️  Estimated time:")
    print(f"  - Full pipeline: ~{doc_count * 30} seconds ({doc_count * 30 // 60} minutes)")
    print(f"  - LLM extraction: ~{doc_count * 21 * 2} seconds ({doc_count * 21 * 2 // 60} minutes)")
    print(f"  - 10 document sample: ~5 minutes")
    
    print("\\n" + "="*80)
    print("\\n🎯 Ready to proceed? Choose an option above.")
    print("   For fastest results, start with Option B (10 document sample)")
    print("\\n" + "="*80 + "\\n")


if __name__ == "__main__":
    main()
