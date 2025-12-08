#!/usr/bin/env python3
"""Analyze current knowledge graph data quality and statistics."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database import get_db_manager  # noqa: E402


def get_table_stats(db_manager):
    """Get statistics from all relevant tables."""
    conn = db_manager.conn
    stats = {}
    
    # Extraction results
    try:
        cursor = conn.execute("SELECT COUNT(*) FROM extractions")
        stats['extraction_results'] = cursor.fetchone()[0]
    except Exception as e:
        stats['extraction_results'] = f"Error: {e}"
    
    # Unique chemicals (from CAS extractions)
    try:
        cursor = conn.execute("""
            SELECT COUNT(DISTINCT value) FROM extractions 
            WHERE field_name = 'cas_number' AND value IS NOT NULL
        """)
        stats['unique_chemicals'] = cursor.fetchone()[0]
    except Exception as e:
        stats['unique_chemicals'] = f"Error: {e}"
    
    # Incompatibility relationships
    try:
        cursor = conn.execute("SELECT COUNT(*) FROM rag_incompatibilities")
        stats['incompatibility_pairs'] = cursor.fetchone()[0]
    except Exception as e:
        stats['incompatibility_pairs'] = f"Error: {e}"
    
    # Unique incompatibility chemicals
    try:
        cursor = conn.execute("""
            SELECT COUNT(DISTINCT cas_a) + COUNT(DISTINCT cas_b) as total_chemicals
            FROM rag_incompatibilities
        """)
        result = cursor.fetchone()
        stats['chemicals_with_incompatibilities'] = result[0] if result else 0
    except Exception as e:
        stats['chemicals_with_incompatibilities'] = f"Error: {e}"
    
    # Hazard data
    try:
        cursor = conn.execute("SELECT COUNT(*) FROM rag_hazards")
        stats['hazard_records'] = cursor.fetchone()[0]
    except Exception as e:
        stats['hazard_records'] = f"Error: {e}"
    
    # GHS classifications
    try:
        cursor = conn.execute("SELECT COUNT(*) FROM rag_documents")
        stats['document_records'] = cursor.fetchone()[0]
    except Exception as e:
        stats['document_records'] = f"Error: {e}"
    
    # Unique document types
    try:
        cursor = conn.execute("""
            SELECT COUNT(DISTINCT source_type) FROM rag_documents
        """)
        stats['unique_document_types'] = cursor.fetchone()[0]
    except Exception as e:
        stats['unique_document_types'] = f"Error: {e}"
    
    return stats


def get_relationship_density(db_manager):
    """Calculate relationship density metrics."""
    conn = db_manager.conn
    density = {}
    
    # Average incompatibilities per chemical
    try:
        cursor = conn.execute("""
            SELECT AVG(incomp_count)
            FROM (
                SELECT cas_a, COUNT(*) as incomp_count
                FROM rag_incompatibilities
                GROUP BY cas_a
            ) t
        """)
        density['avg_incompatibilities_per_chemical'] = cursor.fetchone()[0] or 0
    except Exception as e:
        density['avg_incompatibilities_per_chemical'] = f"Error: {e}"
    
    # Chemicals with most incompatibilities
    try:
        cursor = conn.execute("""
            SELECT cas_a, COUNT(*) as incomp_count
            FROM rag_incompatibilities
            GROUP BY cas_a
            ORDER BY incomp_count DESC
            LIMIT 10
        """)
        density['top_incompatible_chemicals'] = cursor.fetchall()
    except Exception as e:
        density['top_incompatible_chemicals'] = f"Error: {e}"
    
    # Incompatibility rules distribution
    try:
        cursor = conn.execute("""
            SELECT rule, COUNT(*) as count
            FROM rag_incompatibilities
            GROUP BY rule
            ORDER BY count DESC
        """)
        density['rule_distribution'] = cursor.fetchall()
    except Exception as e:
        density['rule_distribution'] = f"Error: {e}"
    
    # Hazard type distribution
    try:
        cursor = conn.execute("""
            SELECT hazard_flags, COUNT(*) as count
            FROM rag_hazards
            WHERE hazard_flags IS NOT NULL
            GROUP BY hazard_flags
            ORDER BY count DESC
            LIMIT 15
        """)
        density['hazard_distribution'] = cursor.fetchall()
    except Exception as e:
        density['hazard_distribution'] = f"Error: {e}"
    
    return density


def main():
    """Main analysis."""
    db = get_db_manager()
    
    print("\n" + "="*70)
    print("KNOWLEDGE GRAPH DATA QUALITY ANALYSIS")
    print("="*70 + "\n")
    
    # Basic statistics
    print("📊 TABLE STATISTICS")
    print("-" * 70)
    stats = get_table_stats(db)
    for key, value in stats.items():
        formatted_key = key.replace('_', ' ').title()
        print(f"  {formatted_key:<40} {value:>15}")
    
    # Relationship density
    print("\n📈 RELATIONSHIP DENSITY METRICS")
    print("-" * 70)
    density = get_relationship_density(db)
    
    avg_incompat = density.get('avg_incompatibilities_per_chemical', 0)
    print(f"  Average Incompatibilities per Chemical: {avg_incompat:.2f}")
    
    # Top incompatible chemicals
    print("\n🔴 TOP 10 MOST INCOMPATIBLE CHEMICALS")
    print("-" * 70)
    top_chem = density.get('top_incompatible_chemicals', [])
    if isinstance(top_chem, list) and top_chem and not isinstance(top_chem[0], str):
        for i, (cas, count) in enumerate(top_chem, 1):
            print(f"  {i:2}. {cas:<20} {count:3} incompatibilities")
    else:
        print(f"  {top_chem}")
    
    # Rule distribution
    print("\n📋 INCOMPATIBILITY RULES DISTRIBUTION")
    print("-" * 70)
    rules = density.get('rule_distribution', [])
    if isinstance(rules, list) and rules and not isinstance(rules[0], str):
        total_rules = sum(r[1] for r in rules)
        for rule, count in rules:
            pct = (count / total_rules * 100) if total_rules > 0 else 0
            print(f"  {rule:<30} {count:4} ({pct:5.1f}%)")
    else:
        print(f"  {rules}")
    
    # Hazard distribution
    print("\n⚠️  HAZARD TYPE DISTRIBUTION")
    print("-" * 70)
    hazards = density.get('hazard_distribution', [])
    if isinstance(hazards, list) and hazards and not isinstance(hazards[0], str):
        total_hazards = sum(h[1] for h in hazards)
        for hazard, count in hazards:
            pct = (count / total_hazards * 100) if total_hazards > 0 else 0
            print(f"  {hazard:<30} {count:4} ({pct:5.1f}%)")
    else:
        print(f"  {hazards}")
    
    # Data gaps analysis
    print("\n🔍 DATA QUALITY ASSESSMENT")
    print("-" * 70)
    
    total_chemicals = stats.get('unique_chemicals', 0)
    chemicals_with_incomp = stats.get('chemicals_with_incompatibilities', 0)
    incomp_pairs = stats.get('incompatibility_pairs', 0)
    
    if isinstance(total_chemicals, int) and isinstance(chemicals_with_incomp, int):
        coverage = (chemicals_with_incomp / total_chemicals * 100) if total_chemicals > 0 else 0
        print(f"  Chemicals with incompatibilities: {coverage:.1f}%")
        print(f"    ({chemicals_with_incomp}/{total_chemicals} chemicals)")
    
    if isinstance(incomp_pairs, int):
        max_possible_edges = (total_chemicals * (total_chemicals - 1) / 2) if isinstance(total_chemicals, int) else 0
        if max_possible_edges > 0:
            edge_coverage = (incomp_pairs / max_possible_edges * 100)
            print(f"  Knowledge graph density: {edge_coverage:.3f}%")
            print(f"    ({incomp_pairs} edges / {int(max_possible_edges)} possible)")
    
    hazard_coverage = stats.get('hazard_records', 0)
    if isinstance(hazard_coverage, int) and isinstance(total_chemicals, int):
        haz_cov_pct = (hazard_coverage / total_chemicals * 100) if total_chemicals > 0 else 0
        print(f"  Chemicals with hazard data: {haz_cov_pct:.1f}%")
        print(f"    ({hazard_coverage}/{total_chemicals} chemicals)")
    
    doc_cov = stats.get('document_records', 0)
    if isinstance(doc_cov, int):
        print(f"  RAG Documents indexed: {doc_cov}")
    
    print("\n" + "="*70 + "\n")


if __name__ == "__main__":
    main()
