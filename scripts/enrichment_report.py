#!/usr/bin/env python3
"""
Generate a comprehensive enrichment report showing current data availability
and potential for knowledge graph expansion.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database import get_db_manager
from src.graph.hazard_extractor import HazardExtractor


def generate_enrichment_report():
    """Generate a complete data enrichment assessment report."""
    
    db = get_db_manager()
    
    print("\n" + "="*80)
    print("DATA ENRICHMENT OPPORTUNITY ASSESSMENT REPORT")
    print("="*80)
    print()
    
    # Phase 1 Results
    print("📊 PHASE 1: HAZARD & SAFETY STATEMENT EXTRACTION")
    print("-" * 80)
    
    extractor = HazardExtractor(db)
    results = extractor.extract_all_hazards()
    summary = extractor.get_summary()
    
    print(f"\n✓ Hazard Classifications Extracted:")
    print(f"  - Chemicals with hazard data: {summary['chemicals_with_hazards']}/109 ({summary['chemicals_with_hazards']/109*100:.1f}%)")
    print(f"  - Total hazard classifications: {summary['total_hazard_classifications']}")
    print(f"  - Avg classifications per chemical: {summary['avg_hazards_per_chemical']:.1f}")
    
    print(f"\n✓ H-Statements (Hazard Codes) Extracted:")
    print(f"  - Chemicals with H-statements: {summary['chemicals_with_h_statements']}/109 ({summary['chemicals_with_h_statements']/109*100:.1f}%)")
    print(f"  - Total H-statements: {summary['total_h_statements']}")
    
    print(f"\n✓ P-Statements (Precautionary Codes) Extracted:")
    print(f"  - Chemicals with P-statements: {summary['chemicals_with_p_statements']}/109 ({summary['chemicals_with_p_statements']/109*100:.1f}%)")
    print(f"  - Total P-statements: {summary['total_p_statements']}")
    
    # Calculate potential relationships
    print(f"\n📈 RELATIONSHIP POTENTIAL FROM PHASE 1:")
    print(f"  - Hazard → Chemical edges: {summary['total_hazard_classifications']}")
    print(f"  - H-statement → Chemical edges: {summary['total_h_statements']}")
    print(f"  - P-statement → Chemical edges: {summary['total_p_statements']}")
    print(f"  - Total Phase 1 relationships: {summary['total_hazard_classifications'] + summary['total_h_statements'] + summary['total_p_statements']}")
    
    # Estimate graph density after Phase 1
    total_relationships = 12 + (summary['total_hazard_classifications'] + summary['total_h_statements'] + summary['total_p_statements'])
    new_density = (total_relationships / 5886) * 100
    
    print(f"\n💡 PHASE 1 PROJECTED IMPACT:")
    print(f"  - Current graph: 12 relationships (0.204% density)")
    print(f"  - + Phase 1 enrichment: +{summary['total_hazard_classifications'] + summary['total_h_statements'] + summary['total_p_statements']} relationships")
    print(f"  - New total: {total_relationships} relationships ({new_density:.2f}% density)")
    print(f"  - Improvement: {new_density/0.204:.1f}x increase")
    
    # Other available data
    print(f"\n🔍 OTHER AVAILABLE EXTRACTION DATA:")
    conn = db.conn
    
    fields_of_interest = ['product_name', 'manufacturer', 'iupac_name', 'molecular_formula', 'molecular_weight', 'un_number', 'incompatibilities', 'packing_group']
    
    for field in fields_of_interest:
        cursor = conn.execute(f"SELECT COUNT(*) FROM extractions WHERE field_name = '{field}' AND value IS NOT NULL AND value != 'NOT_FOUND'")
        count = cursor.fetchone()[0]
        pct = (count / 109) * 100
        print(f"  - {field}: {count} chemicals ({pct:.1f}%)")
    
    # Phase 2 opportunities
    print(f"\n🚀 PHASE 2: ADVANCED ENRICHMENT OPPORTUNITIES")
    print(f"-" * 80)
    
    # Check manufacturer data
    cursor = conn.execute("""
        SELECT COUNT(DISTINCT value) FROM extractions 
        WHERE field_name = 'manufacturer' AND value IS NOT NULL AND value != 'NOT_FOUND'
    """)
    mfg_count = cursor.fetchone()[0]
    print(f"\n✓ Manufacturer/Supplier Network:")
    print(f"  - Unique manufacturers: {mfg_count}")
    print(f"  - Potential edges: +{mfg_count * 5} (chemical → manufacturer → supplier)")
    
    # Check if we can extract more complex relationships
    cursor = conn.execute("""
        SELECT COUNT(*) FROM extractions
        WHERE field_name = 'incompatibilities' AND value IS NOT NULL AND value != 'NOT_FOUND'
    """)
    incompat_raw = cursor.fetchone()[0]
    print(f"\n✓ Raw Incompatibility Data in Extractions:")
    print(f"  - Records with incompatibility data: {incompat_raw}")
    print(f"  - Current graph incompatibilities: 12")
    print(f"  - Extraction efficiency: {12/max(incompat_raw, 1)*100:.1f}%")
    print(f"  - Potential if extraction improved: +{incompat_raw * 3} relationships")
    
    # Phase 3 - external APIs
    print(f"\n🌐 PHASE 3: EXTERNAL DATA INTEGRATION")
    print(f"-" * 80)
    
    cursor = conn.execute("""
        SELECT COUNT(*) FROM extractions 
        WHERE field_name = 'cas_number' AND value IS NOT NULL AND value != 'NOT_FOUND'
    """)
    cas_count = cursor.fetchone()[0]
    
    print(f"\n✓ PubChem API Integration Potential:")
    print(f"  - CAS numbers available: {cas_count}")
    print(f"  - Properties per chemical (est.): 5-10")
    print(f"  - Potential property nodes: +{cas_count * 7}")
    print(f"  - Similarity relationships (est.): +{int(cas_count * (cas_count-1) / 2 * 0.05)} (5% pairwise similarity)")
    
    # Summary projection
    print(f"\n📊 THREE-PHASE ENRICHMENT PROJECTION")
    print(f"=" * 80)
    
    phase1_rels = total_relationships
    phase2_rels = phase1_rels + (mfg_count * 2) + (incompat_raw * 2)
    phase3_rels = phase2_rels + (cas_count * 7) + int(cas_count * (cas_count-1) / 2 * 0.05)
    
    print(f"\nStarting point:")
    print(f"  - Relationships: 12 (0.204%)")
    print(f"  - Chemicals with data: 17 (15.6%)")
    
    print(f"\nAfter Phase 1 (Hazard extraction):")
    print(f"  - Relationships: {phase1_rels} ({(phase1_rels/5886)*100:.2f}%)")
    print(f"  - Coverage improvement: +{(phase1_rels/12):.0f}x")
    
    print(f"\nAfter Phase 2 (External integration):")
    print(f"  - Relationships: ~{phase2_rels} ({(phase2_rels/5886)*100:.2f}%)")
    print(f"  - Coverage improvement: +{(phase2_rels/12):.0f}x")
    
    print(f"\nAfter Phase 3 (API enrichment):")
    print(f"  - Relationships: ~{phase3_rels} ({(phase3_rels/5886)*100:.2f}%)")
    print(f"  - Coverage improvement: +{(phase3_rels/12):.0f}x")
    
    print(f"\n✨ RECOMMENDATION:")
    print(f"  Priority 1: Extract incompatibilities properly (highest ROI)")
    print(f"  Priority 2: Use extracted hazard/P-statement data")
    print(f"  Priority 3: Integrate PubChem for validation & enrichment")
    
    print("\n" + "="*80 + "\n")


if __name__ == '__main__':
    generate_enrichment_report()
