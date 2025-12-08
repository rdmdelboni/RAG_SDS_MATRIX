#!/usr/bin/env python3
"""
Extract incompatibilities from SDS documents more effectively.

The current extraction has low efficiency (4.1%) because:
1. Many LLM responses are "not applicable" type responses
2. Responses contain Portuguese chemical names that need mapping
3. Some responses are meta-discussion about CAS numbers rather than data

This module implements a better extraction strategy:
1. Filter for actual incompatibility lists (keywords: "incompatible", "incompatível", "evitar", "avoid")
2. Parse chemical lists and names
3. Cross-reference with known CAS numbers
4. Build proper incompatibility pairs
"""

import sys
import re
from pathlib import Path
from typing import Dict, List, Tuple

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.database import get_db_manager


class IncompatibilityExtractor:
    """Extract and normalize chemical incompatibilities from SDS text."""

    # Common chemical name translations and aliases
    CHEMICAL_ALIASES = {
        'água': 'water',
        'ácidos': 'acids',
        'álcalis': 'bases',
        'álcalis cáusticas': 'caustic bases',
        'soluções cáusticas': 'caustic solutions',
        'agentes oxidantes': 'oxidizing agents',
        'oxidantes': 'oxidizers',
        'ácido': 'acid',
        'bases': 'bases',
        'nitritos': 'nitrites',
        'cloretos': 'chlorides',
        'cloretos inorgânicos': 'inorganic chlorides',
        'cloritos': 'chlorites',
        'percloratos': 'perchlorates',
        'agentes redutores': 'reducing agents',
        'metais': 'metals',
        'compostos organometálicos': 'organometallic compounds',
        'aminas': 'amines',
        'sulfetos': 'sulfides',
        'fosfetos': 'phosphides',
    }

    # Keywords that indicate incompatibility data is present
    INCOMP_KEYWORDS = [
        'incompatível', 'incompatible',
        'evitar', 'avoid',
        'não misturar', 'do not mix',
        'reage com', 'reacts with',
        'perigoso', 'dangerous',
        'explosivo', 'explosive',
        'excesso de calor', 'excess heat',
    ]

    # Keywords that indicate NO incompatibility data
    NO_DATA_KEYWORDS = [
        'não aplicável', 'not applicable', 'n/a',
        'nenhum', 'none',
        'desconhecido', 'unknown',
        'infelizmente', 'unfortunately',
        'não há informação', 'no information',
        'não encontr', 'not found',
        'i do not',
        'erro', 'mistake',
        'diferente', 'different',
    ]

    def __init__(self, db_manager):
        """Initialize with database connection."""
        self.db = db_manager
        self.conn = db_manager.conn
        self.incompatibilities: Dict[Tuple[str, str], str] = {}
        self.cas_map = {}  # CAS number mapping

    def build_cas_map(self):
        """Build a map of CAS numbers from database."""
        print("Building CAS number map...")
        cursor = self.conn.execute("""
            SELECT DISTINCT value FROM extractions
            WHERE field_name = 'cas_number' 
              AND value IS NOT NULL 
              AND value NOT IN ('NOT_FOUND', 'N/A')
        """)

        for (cas,) in cursor.fetchall():
            self.cas_map[cas] = cas

        print(f"  ✓ Mapped {len(self.cas_map)} unique CAS numbers")

    def extract_incompatibilities(self) -> int:
        """
        Extract incompatibilities from raw extraction data.

        Returns:
            Number of incompatibility pairs extracted
        """
        print("\nExtracting incompatibilities from SDS data...")

        # Get incompatibility records with their CAS numbers
        cursor = self.conn.execute("""
            SELECT DISTINCT
                cas.value as cas_number,
                e.value as incomp_text,
                e.document_id
            FROM extractions e
            JOIN extractions cas ON e.document_id = cas.document_id 
                                   AND cas.field_name = 'cas_number'
            WHERE e.field_name = 'incompatibilities'
              AND e.value IS NOT NULL
              AND cas.value IS NOT NULL
              AND cas.value NOT IN ('NOT_FOUND', 'N/A')
        """)

        valid_records = 0
        invalid_records = 0

        for cas, incomp_text, doc_id in cursor.fetchall():
            if not incomp_text or not cas:
                continue

            incomp_text = str(incomp_text).strip().lower()

            # Filter out non-applicable responses
            if self._is_no_data_response(incomp_text):
                invalid_records += 1
                continue

            # Filter out meta-discussion responses
            if self._is_meta_response(incomp_text):
                invalid_records += 1
                continue

            # Check if this record has actual incompatibility keywords
            if not self._has_incomp_keywords(incomp_text):
                invalid_records += 1
                continue

            # Extract chemical names from the text
            chemicals = self._extract_chemical_names(incomp_text)

            if chemicals:
                for chemical_name in chemicals:
                    # Try to map chemical name to a CAS number
                    matched_cas = self._find_matching_cas(chemical_name)
                    if matched_cas and matched_cas != cas:
                        # Create incompatibility pair
                        pair = tuple(sorted([cas, matched_cas]))
                        if pair not in self.incompatibilities:
                            self.incompatibilities[pair] = f"Extracted from SDS doc {doc_id}"
                            valid_records += 1

        print(f"  ✓ Valid records with incompatibilities: {valid_records}")
        print(f"  ✗ Invalid/empty records: {invalid_records}")
        print(f"  ✓ Incompatibility pairs extracted: {len(self.incompatibilities)}")

        return len(self.incompatibilities)

    def _is_no_data_response(self, text: str) -> bool:
        """Check if text indicates no incompatibility data is available."""
        text = text.lower()[:200]  # Check first 200 chars

        for keyword in self.NO_DATA_KEYWORDS:
            if keyword in text:
                return True

        return False

    def _is_meta_response(self, text: str) -> bool:
        """Check if text is meta-discussion about CAS numbers rather than data."""
        meta_patterns = [
            r'based on.*context',
            r'it seems.*mistake',
            r'there is.*no.*cas',
            r'looking for.*different',
            r'appears.*different',
        ]

        text = text.lower()
        for pattern in meta_patterns:
            if re.search(pattern, text):
                return True

        return False

    def _has_incomp_keywords(self, text: str) -> bool:
        """Check if text contains incompatibility-related keywords."""
        for keyword in self.INCOMP_KEYWORDS:
            if keyword in text:
                return True

        return False

    def _extract_chemical_names(self, text: str) -> List[str]:
        """Extract chemical names from incompatibility text."""
        chemicals = []

        # Split on common separators
        for part in re.split(r'[,;/\n]', text):
            part = part.strip()
            if len(part) > 3 and len(part) < 100:
                # Skip parenthetical content
                part = re.sub(r'\([^)]*\)', '', part).strip()

                if part and len(part) > 3:
                    chemicals.append(part)

        return chemicals[:10]  # Limit to 10 chemicals per record

    def _find_matching_cas(self, chemical_name: str) -> str:
        """
        Try to find a CAS number matching a chemical name.

        This is a heuristic approach that:
        1. Normalizes the name
        2. Checks aliases
        3. Uses fuzzy matching on known chemicals
        """
        chemical_name = chemical_name.lower().strip()

        # Direct alias match
        if chemical_name in self.CHEMICAL_ALIASES:
            alias = self.CHEMICAL_ALIASES[chemical_name]
            # Try to find CAS by product name or IUPAC name
            cursor = self.conn.execute("""
                SELECT DISTINCT cas.value
                FROM extractions cas
                JOIN extractions prod ON cas.document_id = prod.document_id
                WHERE cas.field_name = 'cas_number'
                  AND (prod.field_name = 'iupac_name' OR prod.field_name = 'product_name')
                  AND LOWER(prod.value) LIKE ?
                  AND cas.value NOT IN ('NOT_FOUND', 'N/A')
                LIMIT 1
            """, [f"%{alias}%"])

            result = cursor.fetchone()
            if result:
                return result[0]

        # Generic matching (if chemical name is in any product/IUPAC name)
        if len(chemical_name) > 3:
            cursor = self.conn.execute("""
                SELECT DISTINCT cas.value
                FROM extractions cas
                JOIN extractions prod ON cas.document_id = prod.document_id
                WHERE cas.field_name = 'cas_number'
                  AND (prod.field_name = 'iupac_name' OR prod.field_name = 'product_name')
                  AND LOWER(prod.value) LIKE ?
                  AND cas.value NOT IN ('NOT_FOUND', 'N/A')
                LIMIT 1
            """, [f"%{chemical_name}%"])

            result = cursor.fetchone()
            if result:
                return result[0]

        return None

    def save_incompatibilities(self) -> int:
        """
        Save extracted incompatibilities to database.

        Returns:
            Number of incompatibilities saved
        """
        print("\nSaving incompatibilities to database...")

        saved = 0
        for (cas_a, cas_b), justification in self.incompatibilities.items():
            try:
                self.conn.execute("""
                    INSERT INTO rag_incompatibilities (cas_a, cas_b, rule, justification, indexed_at)
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT DO NOTHING
                """, [cas_a, cas_b, "E", justification])
                saved += 1
            except Exception as e:
                print(f"  ⚠ Error saving {cas_a} ↔ {cas_b}: {e}")

        self.conn.commit()
        print(f"  ✓ Saved {saved} incompatibility pairs")

        return saved


def main():
    """Main extraction workflow."""
    db = get_db_manager()

    print("\n" + "="*80)
    print("IMPROVED INCOMPATIBILITY EXTRACTION")
    print("="*80)

    extractor = IncompatibilityExtractor(db)

    # Step 1: Build CAS map
    extractor.build_cas_map()

    # Step 2: Extract incompatibilities
    extracted = extractor.extract_incompatibilities()

    # Step 3: Save to database
    if extracted > 0:
        saved = extractor.save_incompatibilities()

        # Report results
        cursor = db.conn.execute("SELECT COUNT(*) FROM rag_incompatibilities")
        total = cursor.fetchone()[0]

        print(f"\n" + "="*80)
        print(f"INCOMPATIBILITY EXTRACTION RESULTS")
        print(f"="*80)
        print(f"  Before: 12 relationships")
        print(f"  Extracted: {extracted} pairs")
        print(f"  Saved: {saved} pairs")
        print(f"  Total in database: {total}")
        print(f"  Graph improvement: {total/12:.1f}x\n")
    else:
        print("  ✗ No incompatibilities extracted")


if __name__ == '__main__':
    main()
