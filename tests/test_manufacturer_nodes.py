import os
import sys
import unittest
from pathlib import Path
import json

# Add parent path to import src
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database.db_manager import DatabaseManager
from src.graph.phase1_enricher import Phase1Enricher

class TestManufacturerNodes(unittest.TestCase):
    def setUp(self):
        # Use in-memory DB for testing
        os.environ["RAG_SDS_MATRIX_DB_MODE"] = "memory"
        self.db = DatabaseManager(db_path=Path(":memory:"))

        # Populate extractions table with some mock data
        self.db.conn.execute("CREATE SEQUENCE IF NOT EXISTS extractions_seq START 1;")
        self.db.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS extractions (
                id BIGINT PRIMARY KEY DEFAULT nextval('extractions_seq'),
                document_id BIGINT NOT NULL,
                field_name VARCHAR NOT NULL,
                value TEXT,
                confidence DOUBLE,
                context TEXT,
                validation_status VARCHAR,
                validation_message TEXT,
                source VARCHAR DEFAULT 'heuristic',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(document_id, field_name)
            );
            """
        )

        self.db.conn.execute(
            """
            INSERT INTO extractions (document_id, field_name, value)
            VALUES
                (1, 'manufacturer', 'Acme Corp'),
                (2, 'manufacturer', 'Globex Corporation'),
                (3, 'manufacturer', 'Acme Corp')
            """
        )

    def test_register_manufacturer(self):
        # Direct test of db_manager method
        mid1 = self.db.register_manufacturer("Test Corp", {"type": "test"})
        mid2 = self.db.register_manufacturer("Test Corp", {"type": "test"}) # Duplicate
        mid3 = self.db.register_manufacturer("New Corp")

        self.assertEqual(mid1, mid2)
        self.assertNotEqual(mid1, mid3)

        manufacturers = self.db.get_all_manufacturers()
        self.assertEqual(len(manufacturers), 2)

        names = {m['name'] for m in manufacturers}
        self.assertIn("Test Corp", names)
        self.assertIn("New Corp", names)

    def test_enricher_extraction(self):
        # Test Phase1Enricher integration
        enricher = Phase1Enricher()
        # Mock enricher db to use our test db instance
        enricher.db = self.db
        enricher.conn = self.db.conn

        count = enricher.extract_manufacturer_relationships()

        # Should find 2 unique manufacturers: Acme Corp, Globex Corporation
        self.assertEqual(count, 2)

        manufacturers = self.db.get_all_manufacturers()
        self.assertEqual(len(manufacturers), 2)

        names = {m['name'] for m in manufacturers}
        self.assertIn("Acme Corp", names)
        self.assertIn("Globex Corporation", names)

if __name__ == '__main__':
    unittest.main()
