"""Phase 1: Quick wins - Extract existing SDS data relationships."""

import json
import sys
from pathlib import Path
from typing import Set

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.database import get_db_manager  # noqa: E402
from src.utils.logger import get_logger  # noqa: E402

logger = get_logger(__name__)


class Phase1Enricher:
    """Quick win enrichment using existing extraction data."""

    def __init__(self):
        """Initialize enricher."""
        self.db = get_db_manager()
        self.conn = self.db.conn

    def extract_manufacturer_relationships(self) -> int:
        """Extract manufacturer relationships from extractions.

        Returns:
            Number of relationships added
        """
        logger.info("Extracting manufacturer relationships...")

        query = """
            SELECT DISTINCT value
            FROM extractions
            WHERE field_name = 'manufacturer' AND value IS NOT NULL AND value != ''
        """

        manufacturers = set()
        try:
            cursor = self.conn.execute(query)
            manufacturers = {row[0] for row in cursor.fetchall()}
        except Exception as e:
            logger.error(f"Error fetching manufacturers: {e}")
            return 0

        logger.info(f"Found {len(manufacturers)} unique manufacturers")

        # Register manufacturers in the graph database
        count = 0
        for m_name in manufacturers:
            try:
                self.db.register_manufacturer(m_name, metadata={"source": "extraction"})
                count += 1
            except Exception as e:
                logger.error(f"Error registering manufacturer {m_name}: {e}")

        logger.info(f"Registered {count} manufacturer nodes")
        return count

    def extract_ghs_relationships(self) -> int:
        """Extract GHS classification relationships.

        Returns:
            Number of relationships added
        """
        logger.info("Extracting GHS classification relationships...")

        query = """
            SELECT DISTINCT value
            FROM extractions
            WHERE field_name = 'hazard_class' AND value IS NOT NULL AND value != ''
        """

        ghs_classes = set()
        try:
            cursor = self.conn.execute(query)
            ghs_classes = {row[0] for row in cursor.fetchall()}
        except Exception as e:
            logger.error(f"Error fetching GHS classes: {e}")
            return 0

        logger.info(f"Found {len(ghs_classes)} unique GHS classifications")

        # Parse GHS class patterns
        ghs_parsed = self._parse_ghs_classes(ghs_classes)
        logger.info(f"Parsed GHS classes: {ghs_parsed}")

        # Get chemical-to-GHS mappings
        query = """
            SELECT DISTINCT
                e1.value as cas,
                e2.value as ghs_class
            FROM extractions e1
            JOIN extractions e2 ON e1.document_id = e2.document_id
            WHERE e1.field_name = 'cas_number'
              AND e2.field_name = 'hazard_class'
              AND e1.value IS NOT NULL
              AND e2.value IS NOT NULL
        """

        count = 0
        try:
            cursor = self.conn.execute(query)
            chemical_ghs = cursor.fetchall()
            count = len(chemical_ghs)
            logger.info(f"Found {count} chemical-GHS mappings")

            # Example mappings
            for cas, ghs in list(chemical_ghs)[:5]:
                logger.info(f"  {cas} → {ghs}")

        except Exception as e:
            logger.error(f"Error getting chemical-GHS mappings: {e}")

        return count

    def extract_h_statement_relationships(self) -> int:
        """Extract H-statement relationships.

        Returns:
            Number of relationships added
        """
        logger.info("Extracting H-statement relationships...")

        query = """
            SELECT DISTINCT value
            FROM extractions
            WHERE field_name = 'h_statements' AND value IS NOT NULL AND value != ''
        """

        h_statements = []
        try:
            cursor = self.conn.execute(query)
            h_statements = [row[0] for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error fetching H-statements: {e}")
            return 0

        logger.info(f"Found {len(h_statements)} unique H-statement entries")

        # Parse H-statements (usually JSON or comma-separated)
        parsed_h = self._parse_h_statements(h_statements)
        logger.info(f"Parsed {len(parsed_h)} individual H-codes")

        # Get chemical-to-H mappings
        query = """
            SELECT DISTINCT
                e1.value as cas,
                e2.value as h_statements
            FROM extractions e1
            JOIN extractions e2 ON e1.document_id = e2.document_id
            WHERE e1.field_name = 'cas_number'
              AND e2.field_name = 'h_statements'
              AND e1.value IS NOT NULL
              AND e2.value IS NOT NULL
        """

        count = 0
        try:
            cursor = self.conn.execute(query)
            chemical_h = cursor.fetchall()
            count = len(chemical_h)
            logger.info(f"Found {count} chemical-H-statement mappings")

        except Exception as e:
            logger.error(f"Error getting chemical-H mappings: {e}")

        return count

    def extract_p_statement_relationships(self) -> int:
        """Extract P-statement relationships.

        Returns:
            Number of relationships added
        """
        logger.info("Extracting P-statement relationships...")

        query = """
            SELECT DISTINCT value
            FROM extractions
            WHERE field_name = 'p_statements' AND value IS NOT NULL AND value != ''
        """

        p_statements = []
        try:
            cursor = self.conn.execute(query)
            p_statements = [row[0] for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error fetching P-statements: {e}")
            return 0

        logger.info(f"Found {len(p_statements)} unique P-statement entries")

        # Parse P-statements
        parsed_p = self._parse_p_statements(p_statements)
        logger.info(f"Parsed {len(parsed_p)} individual P-codes")

        # Get chemical-to-P mappings
        query = """
            SELECT DISTINCT
                e1.value as cas,
                e2.value as p_statements
            FROM extractions e1
            JOIN extractions e2 ON e1.document_id = e2.document_id
            WHERE e1.field_name = 'cas_number'
              AND e2.field_name = 'p_statements'
              AND e1.value IS NOT NULL
              AND e2.value IS NOT NULL
        """

        count = 0
        try:
            cursor = self.conn.execute(query)
            chemical_p = cursor.fetchall()
            count = len(chemical_p)
            logger.info(f"Found {count} chemical-P-statement mappings")

        except Exception as e:
            logger.error(f"Error getting chemical-P mappings: {e}")

        return count

    @staticmethod
    def _parse_ghs_classes(ghs_classes: Set[str]) -> dict:
        """Parse GHS class strings to identify categories.

        Returns:
            Dictionary of GHS categories found
        """
        categories = {}
        for ghs_str in ghs_classes:
            if not ghs_str:
                continue

            # Try JSON parsing
            try:
                if ghs_str.startswith("{"):
                    parsed = json.loads(ghs_str)
                    for key in parsed:
                        categories[key] = categories.get(key, 0) + 1
                else:
                    # Treat as plain text category
                    categories[ghs_str] = categories.get(ghs_str, 0) + 1
            except json.JSONDecodeError:
                categories[ghs_str] = categories.get(ghs_str, 0) + 1

        return categories

    @staticmethod
    def _parse_h_statements(h_statements: list) -> Set[str]:
        """Parse H-statement strings to extract H-codes.

        Returns:
            Set of H-codes found (e.g., 'H200', 'H250')
        """
        h_codes = set()

        for h_str in h_statements:
            if not h_str:
                continue

            # Try JSON parsing
            try:
                if h_str.startswith("["):
                    parsed = json.loads(h_str)
                    for item in parsed:
                        if isinstance(item, str) and item.startswith("H"):
                            h_codes.add(item)
                elif h_str.startswith("{"):
                    parsed = json.loads(h_str)
                    h_codes.update(parsed.keys() if isinstance(parsed, dict) else [])
            except json.JSONDecodeError:
                # Try comma-separated or space-separated
                for code in h_str.replace(",", " ").split():
                    if code.startswith("H") and code[1:].isdigit():
                        h_codes.add(code)

        return h_codes

    @staticmethod
    def _parse_p_statements(p_statements: list) -> Set[str]:
        """Parse P-statement strings to extract P-codes.

        Returns:
            Set of P-codes found (e.g., 'P101', 'P271')
        """
        p_codes = set()

        for p_str in p_statements:
            if not p_str:
                continue

            # Try JSON parsing
            try:
                if p_str.startswith("["):
                    parsed = json.loads(p_str)
                    for item in parsed:
                        if isinstance(item, str) and item.startswith("P"):
                            p_codes.add(item)
                elif p_str.startswith("{"):
                    parsed = json.loads(p_str)
                    p_codes.update(parsed.keys() if isinstance(parsed, dict) else [])
            except json.JSONDecodeError:
                # Try comma-separated or space-separated
                for code in p_str.replace(",", " ").split():
                    if code.startswith("P") and code[1:].isdigit():
                        p_codes.add(code)

        return p_codes

    def run_all_phase1(self) -> dict:
        """Run all Phase 1 enrichment steps.

        Returns:
            Dictionary with counts from each enrichment
        """
        logger.info("=" * 70)
        logger.info("PHASE 1: QUICK WINS ENRICHMENT")
        logger.info("=" * 70)

        results = {
            "manufacturer_relationships": self.extract_manufacturer_relationships(),
            "ghs_relationships": self.extract_ghs_relationships(),
            "h_statement_relationships": self.extract_h_statement_relationships(),
            "p_statement_relationships": self.extract_p_statement_relationships(),
        }

        total = sum(results.values())
        logger.info("Phase 1 Summary:")
        for key, val in results.items():
            logger.info(f"  {key}: {val}")
        logger.info(f"  Total potential relationships: {total}")

        return results


if __name__ == "__main__":
    enricher = Phase1Enricher()
    results = enricher.run_all_phase1()
