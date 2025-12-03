#!/usr/bin/env python3
"""Migrate database to add missing metadata column."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.database import get_db_manager

print("=" * 60)
print("Database Migration: Add metadata column to extractions")
print("=" * 60)

db = get_db_manager()

try:
    print("\n1. Checking if metadata column exists...")
    result = db.conn.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'extractions' AND column_name = 'metadata'"
    ).fetchall()
    
    if result:
        print("   ✓ metadata column already exists!")
    else:
        print("   ✗ metadata column missing, adding it...")
        db.conn.execute(
            "ALTER TABLE extractions ADD COLUMN metadata TEXT DEFAULT NULL;"
        )
        print("   ✓ Column added successfully!")
    
    print("\n2. Verifying column was added...")
    result = db.conn.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'extractions' AND column_name = 'metadata'"
    ).fetchall()
    
    if result:
        print("   ✓ Column verified!")
    else:
        print("   ✗ Column verification failed")
        sys.exit(1)
    
    print("\n" + "=" * 60)
    print("✅ Migration completed successfully!")
    print("=" * 60)
    print("\nYour RAG data and extractions are preserved.")
    print("You can now run: python main.py")
    
except Exception as e:
    print(f"\n✗ Migration failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
