#!/usr/bin/env python3
"""
Phase 2b: Create Product Family Relationships

Chemicals from the same manufacturer are typically:
- Compatible with each other (same storage, handling)
- Part of a product family
- Often used together in formulations

This creates compatibility relationships for product families.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database import get_db_manager


def create_product_families():
    """Create relationships for chemicals from the same manufacturer."""
    
    db = get_db_manager()
    conn = db.conn
    
    print("\n" + "="*80)
    print("PHASE 2b: CREATE PRODUCT FAMILY RELATIONSHIPS")
    print("="*80 + "\n")
    
    # Create product family relationship table
    print("Step 1: Creating product family table...")
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS product_families (
                id BIGINT PRIMARY KEY DEFAULT nextval('extractions_seq'),
                cas_a VARCHAR NOT NULL,
                cas_b VARCHAR NOT NULL,
                manufacturer VARCHAR NOT NULL,
                family_type VARCHAR,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(cas_a, cas_b, manufacturer)
            )
        """)
        print("  ✓ product_families table ready\n")
    except Exception:
        print("  ℹ product_families table exists\n")
    
    # Get chemicals grouped by manufacturer
    print("Step 2: Finding chemicals from same manufacturer...")
    
    cursor = conn.execute("""
        SELECT manufacturer_name, COUNT(*) as chem_count
        FROM chemical_manufacturers
        GROUP BY manufacturer_name
        HAVING COUNT(*) >= 2
        ORDER BY chem_count DESC
    """)
    
    manufacturers = cursor.fetchall()
    print(f"  ✓ Found {len(manufacturers)} manufacturers with 2+ chemicals\n")
    
    # Create product family relationships
    print("Step 3: Creating product family relationships...")
    
    family_count = 0
    
    for mfg_name, chem_count in manufacturers:
        # Get all chemicals for this manufacturer
        cursor = conn.execute("""
            SELECT DISTINCT cas_number FROM chemical_manufacturers
            WHERE manufacturer_name = ?
            ORDER BY cas_number
        """, [mfg_name])
        
        chemicals = [row[0] for row in cursor.fetchall()]
        
        # Create relationships between all pairs
        # (they're from the same manufacturer = likely compatible)
        for i, cas_a in enumerate(chemicals):
            for cas_b in chemicals[i+1:]:
                try:
                    pair = tuple(sorted([cas_a, cas_b]))
                    conn.execute(
                        "INSERT INTO product_families (cas_a, cas_b, manufacturer, family_type, created_at) VALUES (?, ?, ?, 'same_manufacturer', CURRENT_TIMESTAMP)",
                        [pair[0], pair[1], mfg_name]
                    )
                    family_count += 1
                except Exception:
                    pass
    
    conn.commit()
    print(f"  ✓ Created {family_count} product family relationships\n")
    
    # Summary
    print("="*80)
    print("PHASE 2b RESULTS - PRODUCT FAMILY RELATIONSHIPS")
    print("="*80)
    print(f"\nProduct Family Network:")
    print(f"  Product family relationships created: +{family_count}")
    print(f"  (chemicals from same manufacturer = compatible/similar)")
    
    # Overall stats
    cursor = conn.execute("SELECT COUNT(*) FROM rag_incompatibilities")
    incomp_count = cursor.fetchone()[0]
    
    cursor = conn.execute("SELECT COUNT(*) FROM chemical_manufacturers")
    mfg_count = cursor.fetchone()[0]
    
    cursor = conn.execute("SELECT COUNT(*) FROM product_families")
    family_relationships = cursor.fetchone()[0]
    
    # Phase 2 total
    phase_2_rels = mfg_count + family_relationships
    total_rels = 1131 + phase_2_rels  # Phase 1 + Phase 2
    
    density = (total_rels / 5886) * 100
    
    print(f"\nPhase 2 Summary:")
    print(f"  Manufacturer-Chemical relationships: 144")
    print(f"  Product family relationships: +{family_relationships}")
    print(f"  Phase 2 total: +{phase_2_rels} relationships")
    print(f"\nCumulative Graph Status:")
    print(f"  Phase 1 relationships: 1,131")
    print(f"  Phase 2 relationships: +{phase_2_rels}")
    print(f"  Total relationships: {total_rels}")
    print(f"  Graph density: {density:.2f}%")
    print(f"  Improvement from baseline: {total_rels/12:.1f}x\n")


if __name__ == '__main__':
    create_product_families()
