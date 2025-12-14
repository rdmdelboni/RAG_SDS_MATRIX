#!/usr/bin/env python3
"""Backfill Section 3 ingredient extraction for already-registered SDS documents."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.database import get_db_manager
from src.sds.extractor import SDSExtractor
from src.sds.ingredient_extractor import IngredientExtractor


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="Max documents to process (0 = no limit)")
    args = ap.parse_args()

    db = get_db_manager()
    extractor = SDSExtractor()
    ing_extractor = IngredientExtractor()

    with db._lock:
        rows = db.conn.execute(
            """
            SELECT id, file_path
            FROM documents
            WHERE file_path IS NOT NULL
            ORDER BY id;
            """
        ).fetchall()

    processed = 0
    skipped = 0

    for doc_id, file_path in rows:
        if args.limit and processed >= args.limit:
            break

        path = Path(file_path)
        if not path.exists():
            skipped += 1
            continue

        extracted = extractor.extract_document(path)
        text = extracted.get("text", "") or ""
        sections = extracted.get("sections", {}) or {}

        ingredients = ing_extractor.extract(text, sections)
        db.replace_document_ingredients(
            int(doc_id),
            [
                {
                    "cas_number": ing.cas_number,
                    "chemical_name": ing.chemical_name,
                    "concentration_text": ing.concentration_text,
                    "concentration_min": ing.concentration_min,
                    "concentration_max": ing.concentration_max,
                    "concentration_unit": ing.concentration_unit,
                    "confidence": ing.confidence,
                    "evidence": ing.evidence,
                    "source": "heuristic",
                }
                for ing in ingredients
            ],
        )
        processed += 1

    print(f"Processed: {processed}")
    print(f"Skipped (missing file): {skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

