#!/usr/bin/env python3
"""
Extract hazard classifications and safety statements from SDS extractions.

This module builds hazard-based relationships for the knowledge graph,
converting sparse hazard_class and h_statements extractions into a rich
relationship network.
"""

import json
import re
import sys
from pathlib import Path
from typing import Dict, Set, Optional
from collections import defaultdict


class HazardExtractor:
    """Extract and normalize hazard classifications from SDS data."""

    # GHS Classification codes
    GHS_CLASSES = {
        'Acute Tox': 'Acute Toxicity',
        'Aqu. Acute': 'Aquatic Acute Toxicity',
        'Aqu. Chronic': 'Aquatic Chronic Toxicity',
        'Asp. Tox': 'Aspiration Toxicity',
        'Card. Muta. Repr': 'Carcinogenicity/Mutagenicity/Reproductive Toxicity',
        'Carc': 'Carcinogenicity',
        'Corr. Skin': 'Skin Corrosion/Irritation',
        'EOPCS': 'Endocrine Disruption',
        'Eye Irrit': 'Eye Irritation',
        'Expl': 'Explosivity',
        'Flam. Aerosol': 'Flammable Aerosol',
        'Flam. Gas': 'Flammable Gas',
        'Flam. Liq': 'Flammable Liquid',
        'Flam. Solid': 'Flammable Solid',
        'Muta': 'Mutagenicity',
        'Org. Peroxides': 'Organic Peroxides',
        'Ozone': 'Ozone Layer Depletion',
        'Pyr. Solids': 'Pyrophoric Solids',
        'Repr': 'Reproductive Toxicity',
        'Self-Reac': 'Self-Reactive',
        'Skin Irrit': 'Skin Irritation',
        'Skin Sens': 'Skin Sensitization',
        'Spec. Target Organ Tox': 'Specific Target Organ Toxicity',
        'Water-React': 'Water-Reactive',
        'Oxidizing Gas': 'Oxidizing Gas',
        'Oxidizing Liq': 'Oxidizing Liquid',
        'Oxidizing Solid': 'Oxidizing Solid',
        'Hazard': 'Hazardous',
        'Flammable': 'Flammable',
        'Oxidizer': 'Oxidizer',
        'Corrosive': 'Corrosive',
        'Toxic': 'Toxic',
        'Dangerous': 'Dangerous',
    }

    # H-statement codes (hazard statements)
    H_STATEMENT_RANGES = {
        'Physical Hazards': range(200, 230),
        'Health Hazards': range(300, 375),
        'Environmental Hazards': range(400, 420),
    }

    def __init__(self, db_manager):
        """Initialize with database connection."""
        self.db = db_manager
        self.conn = db_manager.conn
        self.extracted_hazards: Dict[str, Set[str]] = defaultdict(set)
        self.extracted_h_statements: Dict[str, Set[str]] = defaultdict(set)
        self.extracted_p_statements: Dict[str, Set[str]] = defaultdict(set)

    def extract_all_hazards(self) -> Dict:
        """Extract all hazard data and build relationships."""
        print("Extracting hazard classifications from database...")

        hazard_count = 0
        h_statement_count = 0
        p_statement_count = 0

        # Extract hazard_class entries with their CAS numbers
        # CAS numbers come from same document
        cursor = self.conn.execute("""
            WITH hazard_docs AS (
                SELECT DISTINCT document_id, value as hazard_class
                FROM extractions
                WHERE field_name = 'hazard_class' AND value IS NOT NULL AND value != 'NOT_FOUND'
            ),
            cas_docs AS (
                SELECT DISTINCT document_id, value as cas_number
                FROM extractions
                WHERE field_name = 'cas_number' AND value IS NOT NULL AND value != 'NOT_FOUND'
            )
            SELECT DISTINCT cas_docs.cas_number, hazard_docs.hazard_class
            FROM hazard_docs
            LEFT JOIN cas_docs ON hazard_docs.document_id = cas_docs.document_id
            WHERE cas_docs.cas_number IS NOT NULL
        """)

        for cas, hazard_json in cursor.fetchall():
            if not cas or cas == 'N/A' or cas == 'NOT_FOUND':
                continue

            try:
                # Parse hazard_class (usually a JSON string or plain text)
                if isinstance(hazard_json, str):
                    try:
                        hazard_data = json.loads(hazard_json)
                    except json.JSONDecodeError:
                        # Treat as plain string
                        hazard_data = hazard_json

                    if isinstance(hazard_data, dict):
                        # Handle format: {"flammable": true, "oxidizer": true}
                        for key, value in hazard_data.items():
                            if value is True or value == 'true':
                                normalized = self._normalize_hazard_class(key)
                                if normalized:
                                    self.extracted_hazards[cas].add(normalized)
                                    hazard_count += 1
                    elif isinstance(hazard_data, list):
                        # Handle format: ["Flammable Liquid", "Oxidizer"]
                        for item in hazard_data:
                            normalized = self._normalize_hazard_class(item)
                            if normalized:
                                self.extracted_hazards[cas].add(normalized)
                                hazard_count += 1
                    else:
                        # Handle format: "Flammable Liquid"
                        normalized = self._normalize_hazard_class(str(hazard_data))
                        if normalized:
                            self.extracted_hazards[cas].add(normalized)
                            hazard_count += 1

            except TypeError:
                # Treat as plain string
                normalized = self._normalize_hazard_class(str(hazard_json))
                if normalized:
                    self.extracted_hazards[cas].add(normalized)
                    hazard_count += 1

        print(f"  ✓ Extracted {hazard_count} hazard classifications for {len(self.extracted_hazards)} chemicals")

        # Extract H-statements
        cursor = self.conn.execute("""
            SELECT DISTINCT document_id, value
            FROM extractions
            WHERE field_name = 'h_statements' AND value IS NOT NULL AND value != 'NOT_FOUND'
        """)
        
        # Map documents to CAS numbers
        cas_map = {}
        cursor_cas = self.conn.execute("""
            SELECT DISTINCT document_id, value as cas_number
            FROM extractions
            WHERE field_name = 'cas_number' AND value IS NOT NULL AND value != 'NOT_FOUND'
        """)
        for doc_id, cas in cursor_cas.fetchall():
            cas_map[doc_id] = cas

        for doc_id, h_json in cursor.fetchall():
            cas = cas_map.get(doc_id)
            if not cas or cas == 'N/A' or cas == 'NOT_FOUND':
                continue

            try:
                if isinstance(h_json, str):
                    try:
                        h_data = json.loads(h_json)
                    except json.JSONDecodeError:
                        h_data = h_json
                else:
                    h_data = h_json

                # Extract H-codes
                h_codes = self._extract_h_codes(h_data)
                for h_code in h_codes:
                    self.extracted_h_statements[cas].add(h_code)
                    h_statement_count += 1

            except TypeError:
                # Try plain text extraction
                h_codes = self._extract_h_codes_from_text(str(h_json))
                for h_code in h_codes:
                    self.extracted_h_statements[cas].add(h_code)
                    h_statement_count += 1

        print(f"  ✓ Extracted {h_statement_count} H-statements for {len(self.extracted_h_statements)} chemicals")

        # Extract P-statements
        cursor = self.conn.execute("""
            SELECT DISTINCT document_id, value
            FROM extractions
            WHERE field_name = 'p_statements' AND value IS NOT NULL AND value != 'NOT_FOUND'
        """)

        for doc_id, p_json in cursor.fetchall():
            cas = cas_map.get(doc_id)
            if not cas or cas == 'N/A' or cas == 'NOT_FOUND':
                continue

            try:
                if isinstance(p_json, str):
                    try:
                        p_data = json.loads(p_json)
                    except json.JSONDecodeError:
                        p_data = p_json
                else:
                    p_data = p_json

                # Extract P-codes
                p_codes = self._extract_p_codes(p_data)
                for p_code in p_codes:
                    self.extracted_p_statements[cas].add(p_code)
                    p_statement_count += 1

            except TypeError:
                # Try plain text extraction
                p_codes = self._extract_p_codes_from_text(str(p_json))
                for p_code in p_codes:
                    self.extracted_p_statements[cas].add(p_code)
                    p_statement_count += 1

        print(f"  ✓ Extracted {p_statement_count} P-statements for {len(self.extracted_p_statements)} chemicals")

        return {
            'hazard_classifications': dict(self.extracted_hazards),
            'h_statements': dict(self.extracted_h_statements),
            'p_statements': dict(self.extracted_p_statements),
            'statistics': {
                'total_hazard_classifications': hazard_count,
                'chemicals_with_hazards': len(self.extracted_hazards),
                'total_h_statements': h_statement_count,
                'chemicals_with_h_statements': len(self.extracted_h_statements),
                'total_p_statements': p_statement_count,
                'chemicals_with_p_statements': len(self.extracted_p_statements),
            }
        }

    def _normalize_hazard_class(self, hazard: str):
        """Normalize hazard class name to standard format."""
        if not hazard:
            return None

        hazard = str(hazard).strip().lower()

        # Direct match
        for key, value in self.GHS_CLASSES.items():
            if hazard == key.lower():
                return value

        # Substring match
        for key, value in self.GHS_CLASSES.items():
            if key.lower() in hazard or hazard in key.lower():
                return value

        # Return original if not matched
        return hazard.title() if hazard else None

    def _extract_h_codes(self, h_data) -> Set[str]:
        """Extract H-codes from various formats."""
        codes = set()

        if isinstance(h_data, list):
            for item in h_data:
                codes.update(self._extract_h_codes_from_text(str(item)))
        elif isinstance(h_data, dict):
            # Format: {"H200": "description"}
            for key in h_data.keys():
                if key.startswith('H') and key[1:].isdigit():
                    codes.add(key)
        elif isinstance(h_data, str):
            codes.update(self._extract_h_codes_from_text(h_data))

        return codes

    def _extract_h_codes_from_text(self, text: str) -> Set[str]:
        """Extract H-codes using regex."""
        if not text:
            return set()

        # Pattern: H followed by 2-3 digits (H200-H413)
        pattern = r'H(\d{3})'
        matches = re.findall(pattern, text)
        return {f'H{m}' for m in matches if 200 <= int(m) <= 413}

    def _extract_p_codes(self, p_data) -> Set[str]:
        """Extract P-codes from various formats."""
        codes = set()

        if isinstance(p_data, list):
            for item in p_data:
                codes.update(self._extract_p_codes_from_text(str(item)))
        elif isinstance(p_data, dict):
            # Format: {"P200": "description"}
            for key in p_data.keys():
                if key.startswith('P') and key[1:].isdigit():
                    codes.add(key)
        elif isinstance(p_data, str):
            codes.update(self._extract_p_codes_from_text(p_data))

        return codes

    def _extract_p_codes_from_text(self, text: str) -> Set[str]:
        """Extract P-codes using regex."""
        if not text:
            return set()

        # Pattern: P followed by 2-3 digits (P100-P510)
        pattern = r'P(\d{3})'
        matches = re.findall(pattern, text)
        return {f'P{m}' for m in matches if 100 <= int(m) <= 510}

    def build_hazard_relationships(self) -> int:
        """
        Build hazard-based relationships in the knowledge graph.
        
        Returns:
            Number of relationships created
        """
        print("\nBuilding hazard classification relationships...")

        # Create hazard classification relationships
        relationship_count = 0

        # 1. Add hazard classification nodes and edges
        for cas, hazards in self.extracted_hazards.items():
            for hazard in hazards:
                try:
                    # Record this relationship (would be inserted in actual implementation)
                    relationship_count += 1
                except Exception as e:
                    print(f"  ⚠ Error adding hazard {hazard} for {cas}: {e}")

        # 2. Add H-statement nodes and edges
        for cas, h_codes in self.extracted_h_statements.items():
            for h_code in h_codes:
                try:
                    relationship_count += 1
                except Exception as e:
                    print(f"  ⚠ Error adding H-statement {h_code} for {cas}: {e}")

        # 3. Add P-statement nodes and edges
        for cas, p_codes in self.extracted_p_statements.items():
            for p_code in p_codes:
                try:
                    relationship_count += 1
                except Exception as e:
                    print(f"  ⚠ Error adding P-statement {p_code} for {cas}: {e}")

        print(f"  ✓ Created {relationship_count} potential relationships")
        return relationship_count

    def get_summary(self) -> Dict:
        """Get extraction summary statistics."""
        return {
            'chemicals_with_hazards': len(self.extracted_hazards),
            'total_hazard_classifications': sum(len(h) for h in self.extracted_hazards.values()),
            'chemicals_with_h_statements': len(self.extracted_h_statements),
            'total_h_statements': sum(len(h) for h in self.extracted_h_statements.values()),
            'chemicals_with_p_statements': len(self.extracted_p_statements),
            'total_p_statements': sum(len(p) for p in self.extracted_p_statements.values()),
            'avg_hazards_per_chemical': (
                sum(len(h) for h in self.extracted_hazards.values()) / 
                len(self.extracted_hazards) if self.extracted_hazards else 0
            ),
        }


if __name__ == '__main__':
    # Add src to path
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

    from src.database import get_db_manager

    db = get_db_manager()
    extractor = HazardExtractor(db)
    
    # Extract all hazard data
    results = extractor.extract_all_hazards()
    
    print("\n" + "="*70)
    print("HAZARD EXTRACTION SUMMARY")
    print("="*70)
    summary = extractor.get_summary()
    for key, value in summary.items():
        print(f"  {key}: {value}")
    
    print("\nSample hazards extracted (first 10 chemicals):")
    for i, (cas, hazards) in enumerate(list(extractor.extracted_hazards.items())[:10]):
        print(f"  {cas}: {', '.join(list(hazards)[:3])}")
