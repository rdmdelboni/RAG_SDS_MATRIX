#!/usr/bin/env python3
"""Report chemicals identified from processed SDS and hazardous combinations.

Outputs:
- Chemical inventory (distinct CAS + best-effort name, doc counts)
- Hazardous combinations found in `rag_incompatibilities` within that inventory
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.database import get_db_manager


def _write_json(path: Path, chemicals, combinations) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "chemical_count": len(chemicals),
        "hazardous_combination_count": len(combinations),
        "chemicals": chemicals,
        "hazardous_combinations": combinations,
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _write_csv(path: Path, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-json", type=Path, default=None, help="Write JSON report")
    ap.add_argument("--chemicals-csv", type=Path, default=None, help="Write chemicals CSV")
    ap.add_argument("--combinations-csv", type=Path, default=None, help="Write hazardous combinations CSV")
    ap.add_argument("--no-restricted", action="store_true", help="Exclude rule=R (restricted)")
    args = ap.parse_args()

    db = get_db_manager()

    chemicals = db.get_identified_chemicals()
    combinations = db.find_hazardous_combinations(include_restricted=not args.no_restricted)

    print(f"Chemicals identified: {len(chemicals)}")
    print(f"Hazardous combinations found: {len(combinations)}")

    if args.out_json:
        _write_json(args.out_json, chemicals, combinations)
        print(f"Wrote: {args.out_json}")

    if args.chemicals_csv:
        _write_csv(args.chemicals_csv, chemicals)
        print(f"Wrote: {args.chemicals_csv}")

    if args.combinations_csv:
        _write_csv(args.combinations_csv, combinations)
        print(f"Wrote: {args.combinations_csv}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

