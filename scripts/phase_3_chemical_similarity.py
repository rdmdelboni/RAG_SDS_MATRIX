#!/usr/bin/env python3
"""
Phase 3: Chemical Similarity Clustering - with PubChem Enrichment
=================================================================

Build molecular similarity relationships using RDKit fingerprints.
First fetches SMILES from PubChem API, then computes similarities.
"""

import time
from pathlib import Path
from rdkit import Chem
from rdkit.Chem import AllChem
import logging
import requests

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# Configuration
SIMILARITY_THRESHOLD = 0.7
DATA_DIR = Path(__file__).parent.parent / 'data'
DB_PATH = DATA_DIR / 'duckdb' / 'extractions.db'


def get_db_connection():
    """Connect to DuckDB"""
    import duckdb
    return duckdb.connect(str(DB_PATH))


def fetch_smiles_from_pubchem(cas):
    """Fetch SMILES from PubChem API"""
    try:
        url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cas/{cas}/property/CanonicalSMILES/JSON"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            if 'properties' in data and len(data['properties']) > 0:
                return data['properties'][0].get('CanonicalSMILES')
        return None
    except Exception as e:
        logger.debug(f"Error fetching SMILES for {cas}: {e}")
        return None


def get_all_chemicals(conn):
    """Get all unique chemicals from database"""
    cursor = conn.execute(
        "SELECT DISTINCT cas_number FROM rag_extractions WHERE cas_number != 'Unknown' ORDER BY cas_number"
    )
    return [row[0] for row in cursor.fetchall()]


def build_smiles_map(chemicals):
    """Fetch SMILES for all chemicals"""
    logger.info(f"📥 Fetching SMILES from PubChem for {len(chemicals)} chemicals...")

    smiles_map = {}
    for i, cas in enumerate(chemicals):
        if (i + 1) % max(1, len(chemicals) // 5) == 0:
            logger.info(f"  Progress: {i+1}/{len(chemicals)}")

        smiles = fetch_smiles_from_pubchem(cas)
        if smiles:
            smiles_map[cas] = smiles

        time.sleep(0.1)  # Rate limiting

    logger.info(f"✓ Retrieved {len(smiles_map)}/{len(chemicals)} SMILES ({len(smiles_map)/len(chemicals)*100:.1f}%)")
    return smiles_map


def get_fingerprint(smiles):
    """Generate Morgan fingerprint from SMILES"""
    try:
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return None
        return AllChem.GetMorganFingerprintAsBitVect(mol, 2, nBits=1024)
    except Exception as e:
        logger.debug(f"Error generating fingerprint for {smiles}: {e}")
        return None


def compute_tanimoto_similarity(fp1, fp2):
    """Compute Tanimoto similarity between two fingerprints"""
    if fp1 is None or fp2 is None:
        return 0.0
    return AllChem.DataStructs.TanimotoSimilarity(fp1, fp2)


def create_similarity_table(conn):
    """Create table for similarity relationships"""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS chemical_similarity (
            cas_a VARCHAR,
            cas_b VARCHAR,
            similarity_score FLOAT,
            fingerprint_type VARCHAR DEFAULT 'morgan_2_1024',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (cas_a, cas_b),
            FOREIGN KEY (cas_a) REFERENCES rag_extractions(cas_number),
            FOREIGN KEY (cas_b) REFERENCES rag_extractions(cas_number)
        )
    """)
    logger.info("✓ chemical_similarity table ready")


def build_similarity_network(smiles_map):
    """
    Build complete similarity network.
    Returns list of (cas_a, cas_b, similarity) tuples.
    """
    logger.info(f"\n🔬 Building similarity network from {len(smiles_map)} chemicals...")
    
    cas_list = sorted(smiles_map.keys())
    fingerprints = {}
    
    # Generate fingerprints
    logger.info("  Generating molecular fingerprints...")
    for cas in cas_list:
        fp = get_fingerprint(smiles_map[cas])
        if fp is not None:
            fingerprints[cas] = fp
    
    logger.info(f"✓ Generated {len(fingerprints)} fingerprints")
    
    # Compute all-pairs similarities
    logger.info(f"  Computing all-pairs similarities ({len(fingerprints)} chemicals)...")
    similarities = []
    cas_with_fp = sorted(fingerprints.keys())
    
    for i, cas_a in enumerate(cas_with_fp):
        if (i + 1) % max(1, len(cas_with_fp) // 10) == 0:
            logger.info(f"    Progress: {i+1}/{len(cas_with_fp)}")
        
        for cas_b in cas_with_fp[i+1:]:
            similarity = compute_tanimoto_similarity(
                fingerprints[cas_a],
                fingerprints[cas_b]
            )
            
            if similarity >= SIMILARITY_THRESHOLD:
                similarities.append((cas_a, cas_b, similarity))
    
    logger.info(f"✓ Found {len(similarities)} similar pairs (threshold={SIMILARITY_THRESHOLD})")
    return similarities


def insert_similarities(conn, similarities):
    """Insert similarity relationships into database"""
    logger.info(f"\n💾 Persisting {len(similarities)} similarity relationships...")
    
    # Clear existing (optional)
    conn.execute("DELETE FROM chemical_similarity")
    
    # Bulk insert
    conn.execute("""
        INSERT INTO chemical_similarity (cas_a, cas_b, similarity_score)
        SELECT * FROM ?
    """, [[(cas_a, cas_b, sim) for cas_a, cas_b, sim in similarities]])
    
    logger.info(f"✓ Inserted {len(similarities)} relationships")


def compute_graph_metrics(conn):
    """Compute graph density and coverage metrics"""
    logger.info("\n📊 Computing graph metrics...")
    
    # Count similarity relationships
    sim_count = conn.execute(
        "SELECT COUNT(*) FROM chemical_similarity"
    ).fetchone()[0]
    
    # Get coverage
    sim_chemicals = conn.execute(
        "SELECT COUNT(DISTINCT cas_a) FROM chemical_similarity"
    ).fetchone()[0]
    
    total_chemicals = conn.execute(
        "SELECT COUNT(DISTINCT cas_number) FROM rag_extractions"
    ).fetchone()[0]
    
    coverage = (sim_chemicals / total_chemicals * 100) if total_chemicals > 0 else 0
    
    return {
        'similarity_rels': sim_count,
        'chemicals_covered': sim_chemicals,
        'total_chemicals': total_chemicals,
        'coverage': coverage
    }


def get_similarity_stats(conn):
    """Get detailed similarity statistics"""
    logger.info("\n📈 Similarity Statistics:")
    
    # Top 10 most similar pairs
    cursor = conn.execute("""
        SELECT cas_a, cas_b, similarity_score 
        FROM chemical_similarity 
        ORDER BY similarity_score DESC 
        LIMIT 10
    """)
    
    print("\n  Top 10 Most Similar Pairs:")
    for cas_a, cas_b, sim in cursor:
        print(f"    {cas_a} ↔ {cas_b}: {sim:.3f}")
    
    # Similarity distribution
    cursor = conn.execute("""
        SELECT 
            ROUND(similarity_score, 1) as bin,
            COUNT(*) as count
        FROM chemical_similarity
        GROUP BY ROUND(similarity_score, 1)
        ORDER BY bin DESC
    """)
    
    print("\n  Similarity Distribution:")
    for bin_val, count in cursor:
        bar = '█' * (count // 5)
        print(f"    {bin_val}: {bar} ({count})")
    
    # Degree distribution (most connected chemicals)
    cursor = conn.execute("""
        SELECT 
            COALESCE(a.cas, b.cas) as cas,
            COUNT(*) as degree
        FROM chemical_similarity
        FULL OUTER JOIN (
            SELECT cas_a as cas FROM chemical_similarity
        ) a ON chemical_similarity.cas_a = a.cas
        FULL OUTER JOIN (
            SELECT cas_b as cas FROM chemical_similarity
        ) b ON chemical_similarity.cas_b = b.cas
        WHERE a.cas IS NOT NULL OR b.cas IS NOT NULL
        GROUP BY COALESCE(a.cas, b.cas)
        ORDER BY degree DESC
        LIMIT 5
    """)
    
    print("\n  Most Connected Chemicals (by similarity):")
    for cas, degree in cursor:
        print(f"    {cas}: {degree} similar chemicals")


def phase_3_chemical_similarity():
    """Execute Phase 3: Chemical Similarity"""
    logger.info("="*80)
    logger.info("PHASE 3: CHEMICAL SIMILARITY CLUSTERING")
    logger.info("="*80)
    
    # Load SMILES
    smiles_map = load_smiles_data()
    if not smiles_map:
        logger.error("❌ No SMILES data found in PubChem cache")
        return
    
    # Build similarity network
    similarities = build_similarity_network(smiles_map)
    
    if not similarities:
        logger.warning("⚠️  No similar pairs found above threshold")
        return
    
    # Connect to database
    conn = get_db_connection()
    
    try:
        # Create table
        create_similarity_table(conn)
        
        # Insert relationships
        insert_similarities(conn, similarities)
        
        # Compute metrics
        metrics = compute_graph_metrics(conn)
        
        logger.info(f"\n✨ Phase 3 Results:")
        logger.info(f"  Similarity relationships: {metrics['similarity_rels']}")
        logger.info(f"  Chemicals with similarities: {metrics['chemicals_covered']}/{metrics['total_chemicals']}")
        logger.info(f"  Coverage: {metrics['coverage']:.1f}%")
        
        # Show statistics
        get_similarity_stats(conn)
        
        # Total graph update
        total_rels = conn.execute("""
            SELECT (
                (SELECT COUNT(*) FROM rag_incompatibilities) +
                (SELECT COUNT(*) FROM hazard_classifications) +
                (SELECT COUNT(*) FROM chemical_p_statements) +
                (SELECT COUNT(*) FROM chemical_manufacturers) +
                (SELECT COUNT(*) FROM product_families) +
                (SELECT COUNT(*) FROM chemical_similarity)
            )
        """).fetchone()[0]
        
        density = (total_rels / 5886) * 100
        improvement = total_rels / 12
        
        logger.info(f"\n📊 CUMULATIVE GRAPH STATUS:")
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
