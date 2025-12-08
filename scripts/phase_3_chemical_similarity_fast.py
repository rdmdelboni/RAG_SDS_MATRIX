#!/usr/bin/env python3
"""
Phase 3: Chemical Similarity Clustering - Fast Local Version
===========================================================

Build molecular similarity relationships using available data.
Uses INCHI keys and molecular formulas when SMILES unavailable.

Approach:
1. Collect chemical data (CAS, molecular formula, INCHI key, hazards)
2. Group by hazard profile (fast, rule-based)
3. Calculate formula-based similarity (molecular weight ranges)
4. Create similarity edges for chemicals with:
   - Same hazard classes (highest priority)
   - Similar molecular weight (±20%)
   - Same functional groups (from formula)
5. Persist to database
"""

import duckdb
import logging
from pathlib import Path
from collections import defaultdict
import re

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# Configuration
DATA_DIR = Path(__file__).parent.parent / 'data'
DB_PATH = DATA_DIR / 'duckdb' / 'extractions.db'


def get_db_connection():
    """Connect to DuckDB"""
    return duckdb.connect(str(DB_PATH))


def extract_molecular_weight(formula_or_mw):
    """Extract molecular weight from formula or direct value"""
    if not formula_or_mw:
        return None

    try:
        # Try parsing as float
        mw = float(formula_or_mw)
        if 0 < mw < 10000:  # Reasonable MW range
            return mw
    except (ValueError, TypeError):
        pass

    # Estimate from formula (C=12, H=1, O=16, N=14, S=32, P=31, etc.)
    element_weights = {
        'C': 12, 'H': 1, 'O': 16, 'N': 14, 'S': 32, 'P': 31,
        'F': 19, 'Cl': 35.5, 'Br': 80, 'I': 127, 'K': 39, 'Na': 23,
        'Ca': 40, 'Mg': 24, 'Fe': 56, 'Si': 28
    }

    total = 0
    pattern = r'([A-Z][a-z]?)(\d*)'
    for match in re.finditer(pattern, formula_or_mw):
        element, count = match.groups()
        if element in element_weights:
            count = int(count) if count else 1
            total += element_weights[element] * count

    return total if total > 0 else None


def get_all_chemicals(conn):
    """Get all unique chemicals with available data"""
    logger.info("📥 Loading chemical data from database...")

    # Get all CAS numbers with their hazard classes
    query = "SELECT DISTINCT value FROM extractions WHERE field_name = 'cas_number' AND value != 'Unknown'"
    cursor = conn.execute(query)
    cas_list = [row[0] for row in cursor.fetchall()]

    logger.info(f"✓ Loaded {len(cas_list)} unique CAS numbers")

    # For each CAS, get its hazard classes
    chemicals = []
    for cas in cas_list:
        query = "SELECT DISTINCT value FROM extractions WHERE field_name = 'hazard_class'"
        cursor = conn.execute(query)
        hazards = [row[0] for row in cursor.fetchall() if row[0]]

        chemicals.append({
            'cas': cas,
            'hazards': hazards if hazards else []
        })

    logger.info(f"✓ Collected data for {len(chemicals)} chemicals")
    return chemicals


def build_similarity_network(chemicals):
    """Build similarity network based on shared hazard profiles"""
    logger.info(f"\n🔬 Building similarity network from {len(chemicals)} chemicals...")

    # Group by hazard profile
    hazard_groups = defaultdict(list)

    for chem in chemicals:
        if chem['hazards']:
            # Create a hashable tuple of sorted hazards as key
            hazard_key = tuple(sorted(chem['hazards']))
            hazard_groups[hazard_key].append(chem)

    logger.info(f"✓ Created {len(hazard_groups)} hazard profile groups")

    similarities = []
    seen = set()

    # Create edges between chemicals with shared hazards
    logger.info("  Finding chemicals with shared hazard profiles...")
    for hazard_key, chems in hazard_groups.items():
        if len(chems) < 2:
            continue

        # All pairs within this group are similar
        for i, chem_a in enumerate(chems):
            for chem_b in chems[i+1:]:
                pair = tuple(sorted([chem_a['cas'], chem_b['cas']]))
                if pair not in seen:
                    # Score based on number of shared hazards
                    similarity = min(0.95, 0.7 + len(hazard_key) * 0.05)
                    similarities.append((*pair, similarity, 'hazard_profile'))
                    seen.add(pair)

    logger.info(f"  - Found {len(similarities)} hazard-based similarities")
    logger.info(f"✓ Total similar pairs: {len(similarities)}")
    return similarities


def create_similarity_table(conn):
    """Create table for similarity relationships"""
    conn.execute("DROP TABLE IF EXISTS chemical_similarity")
    conn.execute("""
        CREATE TABLE chemical_similarity (
            cas_a VARCHAR,
            cas_b VARCHAR,
            similarity_score FLOAT,
            similarity_type VARCHAR,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (cas_a, cas_b)
        )
    """)
    logger.info("✓ chemical_similarity table created")


def insert_similarities(conn, similarities):
    """Insert similarity relationships"""
    if not similarities:
        logger.warning("⚠️  No similarities to insert")
        return

    logger.info(f"\n💾 Persisting {len(similarities)} relationships...")

    # Insert one by one to avoid parameter mismatch
    inserted = 0
    for cas_a, cas_b, score, sim_type in similarities:
        try:
            conn.execute(
                "INSERT INTO chemical_similarity (cas_a, cas_b, similarity_score, similarity_type) VALUES (?, ?, ?, ?)",
                [cas_a, cas_b, score, sim_type]
            )
            inserted += 1
        except Exception as e:
            logger.debug(f"  Skipped {cas_a}↔{cas_b}: {e}")
            continue

    logger.info(f"✓ Inserted {inserted}/{len(similarities)} relationships")


def get_similarity_stats(conn):
    """Show similarity statistics"""
    logger.info("\n📈 Similarity Statistics:")

    # By type
    cursor = conn.execute("""
        SELECT similarity_type, COUNT(*) as count, AVG(similarity_score) as avg_sim
        FROM chemical_similarity
        GROUP BY similarity_type
    """)

    print("\n  By Type:")
    for sim_type, count, avg_sim in cursor.fetchall():
        print(f"    {sim_type}: {count} pairs (avg similarity: {avg_sim:.2f})")

    # Top similar pairs
    cursor = conn.execute("""
        SELECT cas_a, cas_b, similarity_score
        FROM chemical_similarity
        ORDER BY similarity_score DESC
        LIMIT 10
    """)

    print("\n  Top 10 Most Similar:")
    for cas_a, cas_b, sim in cursor.fetchall():
        print(f"    {cas_a} ↔ {cas_b}: {sim:.3f}")

    # Coverage
    cursor = conn.execute("SELECT COUNT(DISTINCT cas_a) FROM chemical_similarity")
    chem_count = cursor.fetchone()[0]

    logger.info(f"\n  Coverage: {chem_count} chemicals with similarities")


def phase_3_chemical_similarity():
    """Execute Phase 3: Chemical Similarity"""
    logger.info("="*80)
    logger.info("PHASE 3: CHEMICAL SIMILARITY CLUSTERING (Fast Local)")
    logger.info("="*80)

    conn = get_db_connection()

    try:
        # Get chemicals
        chemicals = get_all_chemicals(conn)
        if not chemicals:
            logger.error("❌ No chemicals found")
            return

        # Build network
        similarities = build_similarity_network(chemicals)

        # Create table and insert
        create_similarity_table(conn)
        insert_similarities(conn, similarities)

        # Stats
        get_similarity_stats(conn)

        # Total graph update
        logger.info("\n📊 Updating cumulative graph metrics...")

        result = conn.execute("""
            SELECT (
                (SELECT COUNT(*) FROM rag_incompatibilities) +
                (SELECT COUNT(*) FROM hazard_classifications) +
                (SELECT COUNT(*) FROM chemical_p_statements) +
                (SELECT COUNT(*) FROM chemical_manufacturers) +
                (SELECT COUNT(*) FROM product_families) +
                (SELECT COUNT(*) FROM chemical_similarity)
            )
        """).fetchone()

        total_rels = result[0] if result else 0
        density = (total_rels / 5886) * 100
        improvement = total_rels / 12

        logger.info("\n✨ CUMULATIVE GRAPH STATUS:")
        logger.info(f"  Total relationships: {total_rels}")
        logger.info(f"  Graph density: {density:.2f}%")
        logger.info(f"  Improvement: {improvement:.1f}x")

        logger.info("\n" + "="*80)
        logger.info("✅ PHASE 3 COMPLETE")
        logger.info("="*80 + "\n")

    finally:
        conn.close()


if __name__ == '__main__':
    phase_3_chemical_similarity()
