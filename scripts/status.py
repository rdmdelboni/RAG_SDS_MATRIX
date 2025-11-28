#!/usr/bin/env python3
"""Print basic health/status metrics for the RAG SDS Matrix."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.database import get_db_manager  # noqa: E402
from src.rag.vector_store import get_vector_store  # noqa: E402


def main() -> int:
    db = get_db_manager()
    stats = db.get_statistics()

    print("== Database stats ==")
    for k, v in stats.items():
        print(f"{k}: {v}")

    # MRLP counts
    with db._lock:
        incompat_count = db.conn.execute("SELECT COUNT(*) FROM rag_incompatibilities").fetchone()[0]
        hazard_count = db.conn.execute("SELECT COUNT(*) FROM rag_hazards").fetchone()[0]
        snapshots = db.conn.execute("SELECT COUNT(*) FROM mrlp_snapshots").fetchone()[0]
        decisions = db.conn.execute("SELECT COUNT(*) FROM matrix_decisions").fetchone()[0]
    print("\n== MRLP ==")
    print(f"incompatibilities: {incompat_count}")
    print(f"hazards: {hazard_count}")
    print(f"snapshots: {snapshots}")
    print(f"matrix decisions logged: {decisions}")

    # Vector store
    try:
        vs = get_vector_store()
        collection_stats = vs.get_collection_stats()
        print("\n== Vector store (Chroma) ==")
        for k, v in collection_stats.items():
            print(f"{k}: {v}")
    except Exception as exc:
        print("\nVector store unavailable:", exc)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
