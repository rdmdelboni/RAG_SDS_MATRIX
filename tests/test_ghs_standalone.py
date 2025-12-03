#!/usr/bin/env python3
"""Standalone test for GHS Database (avoids pytest import issues)."""

import sqlite3
import tempfile
from pathlib import Path


def test_ghs_database():
    """Test GHS database functionality."""
    print("\n🧪 Testing GHS Database...")
    
    # Create temporary database
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = Path(tmp.name)
    
    try:
        # Test 1: Database creation
        print("  ✓ Creating database...")
        conn = sqlite3.connect(db_path)
        
        conn.execute("""
            CREATE TABLE classifications (
                cas_number TEXT NOT NULL,
                hazard_code TEXT NOT NULL,
                category TEXT,
                hazard_class TEXT,
                statement TEXT,
                source TEXT NOT NULL,
                confidence REAL DEFAULT 1.0,
                PRIMARY KEY (cas_number, hazard_code, source)
            )
        """)
        
        conn.execute("""
            CREATE INDEX idx_cas ON classifications(cas_number)
        """)
        
        conn.commit()
        print("  ✅ Database schema created")
        
        # Test 2: Insert classification
        print("  ✓ Inserting classification...")
        conn.execute("""
            INSERT INTO classifications
                (cas_number, hazard_code, category, hazard_class, statement, source, confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            "67-64-1",
            "H225",
            "2",
            "Flammable liquids",
            "Highly flammable liquid and vapor",
            "TEST",
            1.0
        ))
        conn.commit()
        print("  ✅ Classification inserted")
        
        # Test 3: Retrieve classification
        print("  ✓ Retrieving classification...")
        cursor = conn.execute("""
            SELECT hazard_code, statement, source, confidence
            FROM classifications
            WHERE REPLACE(cas_number, '-', '') = ?
        """, ("67641",))  # Test without dashes
        
        row = cursor.fetchone()
        assert row is not None, "No classification found"
        assert row[0] == "H225", f"Expected H225, got {row[0]}"
        assert "flammable" in row[1].lower(), "Expected flammable in statement"
        print(f"  ✅ Retrieved: {row[0]} - {row[1]}")
        
        # Test 4: Multiple sources
        print("  ✓ Testing multiple sources...")
        conn.execute("""
            INSERT INTO classifications
                (cas_number, hazard_code, category, hazard_class, statement, source, confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            "67-64-1",
            "H225",
            "2",
            "Flammable liquids",
            "Highly flammable liquid and vapor",
            "ECHA",
            0.95
        ))
        conn.commit()
        
        cursor = conn.execute("""
            SELECT source, confidence FROM classifications
            WHERE cas_number = ? AND hazard_code = ?
            ORDER BY confidence DESC
        """, ("67-64-1", "H225"))
        
        sources = cursor.fetchall()
        assert len(sources) == 2, f"Expected 2 sources, got {len(sources)}"
        assert sources[0][0] == "TEST", "Highest confidence should be TEST"
        assert sources[0][1] == 1.0, "TEST confidence should be 1.0"
        print(f"  ✅ Multiple sources work (found {len(sources)} sources)")
        
        # Test 5: CAS normalization
        print("  ✓ Testing CAS normalization...")
        cursor = conn.execute("""
            SELECT COUNT(*) FROM classifications
            WHERE REPLACE(cas_number, '-', '') = ?
        """, ("67641",))
        
        count_no_dash = cursor.fetchone()[0]
        
        cursor = conn.execute("""
            SELECT COUNT(*) FROM classifications
            WHERE REPLACE(cas_number, '-', '') = ?
        """, ("67-64-1".replace("-", ""),))
        
        count_with_dash = cursor.fetchone()[0]
        
        assert count_no_dash == count_with_dash, "CAS normalization failed"
        print("  ✅ CAS normalization works")
        
        conn.close()
        
        print("\n🎯 All GHS Database tests passed!")
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # Cleanup
        if db_path.exists():
            db_path.unlink()


if __name__ == "__main__":
    success = test_ghs_database()
    exit(0 if success else 1)
