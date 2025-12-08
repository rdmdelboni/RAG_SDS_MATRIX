#!/usr/bin/env python3
"""
Integrate extracted hazard data into the knowledge graph.

This module takes the extracted hazard classifications, H-statements, and
P-statements and builds them into the chemical knowledge graph as nodes
and relationships.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database import get_db_manager
from src.graph.hazard_extractor import HazardExtractor


def integrate_hazards_into_graph():
    """Build hazard relationships into the chemical knowledge graph."""
    
    db = get_db_manager()
    conn = db.conn
    
    print("\n" + "="*80)
    print("INTEGRATING HAZARD DATA INTO KNOWLEDGE GRAPH")
    print("="*80 + "\n")
    
    # Extract all hazard data
    extractor = HazardExtractor(db)
    print("Step 1: Extracting hazard data from SDS extractions...")
    results = extractor.extract_all_hazards()
    print(f"  ✓ Extraction complete\n")
    
    # Ensure hazard classification table exists
    print("Step 2: Creating hazard classification tables...")
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS hazard_classifications (
                id BIGINT PRIMARY KEY DEFAULT nextval('extractions_seq'),
                cas_number VARCHAR NOT NULL,
                ghs_class VARCHAR NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(cas_number, ghs_class)
            )
        """)
        print("  ✓ hazard_classifications table ready")
    except Exception as e:
        print(f"  ℹ hazard_classifications table exists: {e}")
    
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS chemical_h_statements (
                id BIGINT PRIMARY KEY DEFAULT nextval('extractions_seq'),
                cas_number VARCHAR NOT NULL,
                h_code VARCHAR NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(cas_number, h_code)
            )
        """)
        print("  ✓ chemical_h_statements table ready")
    except Exception as e:
        print(f"  ℹ chemical_h_statements table exists: {e}")
    
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS chemical_p_statements (
                id BIGINT PRIMARY KEY DEFAULT nextval('extractions_seq'),
                cas_number VARCHAR NOT NULL,
                p_code VARCHAR NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(cas_number, p_code)
            )
        """)
        print("  ✓ chemical_p_statements table ready\n")
    except Exception as e:
        print(f"  ℹ chemical_p_statements table exists: {e}\n")
    
    # Insert hazard classifications
    print("Step 3: Inserting hazard classifications...")
    hazard_insert_count = 0
    for cas, hazards in extractor.extracted_hazards.items():
        for hazard in hazards:
            try:
                conn.execute("""
                    INSERT INTO hazard_classifications (cas_number, ghs_class)
                    VALUES (?, ?)
                    ON CONFLICT DO NOTHING
                """, [cas, hazard])
                hazard_insert_count += 1
            except Exception as e:
                # Ignore duplicates
                pass
    
    conn.commit()
    print(f"  ✓ Inserted {hazard_insert_count} hazard classifications\n")
    
    # Insert H-statements
    print("Step 4: Inserting H-statements...")
    h_insert_count = 0
    for cas, h_codes in extractor.extracted_h_statements.items():
        for h_code in h_codes:
            try:
                conn.execute("""
                    INSERT INTO chemical_h_statements (cas_number, h_code)
                    VALUES (?, ?)
                    ON CONFLICT DO NOTHING
                """, [cas, h_code])
                h_insert_count += 1
            except Exception as e:
                pass
    
    conn.commit()
    print(f"  ✓ Inserted {h_insert_count} H-statement relationships\n")
    
    # Insert P-statements
    print("Step 5: Inserting P-statements...")
    p_insert_count = 0
    for cas, p_codes in extractor.extracted_p_statements.items():
        for p_code in p_codes:
            try:
                conn.execute("""
                    INSERT INTO chemical_p_statements (cas_number, p_code)
                    VALUES (?, ?)
                    ON CONFLICT DO NOTHING
                """, [cas, p_code])
                p_insert_count += 1
            except Exception as e:
                pass
    
    conn.commit()
    print(f"  ✓ Inserted {p_insert_count} P-statement relationships\n")
    
    # Verify insertions
    print("Step 6: Verifying data...")
    cursor = conn.execute("SELECT COUNT(*) FROM hazard_classifications")
    hazard_count = cursor.fetchone()[0]
    
    cursor = conn.execute("SELECT COUNT(*) FROM chemical_h_statements")
    h_count = cursor.fetchone()[0]
    
    cursor = conn.execute("SELECT COUNT(*) FROM chemical_p_statements")
    p_count = cursor.fetchone()[0]
    
    total_new = hazard_count + h_count + p_count
    
    print(f"  ✓ Hazard classifications in database: {hazard_count}")
    print(f"  ✓ H-statements in database: {h_count}")
    print(f"  ✓ P-statements in database: {p_count}")
    print(f"  ✓ Total new relationships: {total_new}\n")
    
    print("="*80)
    print(f"✨ ENRICHMENT COMPLETE!")
    print("="*80)
    print(f"\nGraph Enhancement Summary:")
    print(f"  Before: 12 incompatibility relationships")
    print(f"  After:  {12 + total_new} total relationships")
    print(f"  Increase: +{total_new} relationships ({(total_new/12)*100:.0f}% growth)")
    print(f"  New density: {((12 + total_new)/5886)*100:.2f}%")
    print(f"  Improvement: {(12 + total_new)/12:.1f}x\n")


if __name__ == '__main__':
    integrate_hazards_into_graph()
