#!/usr/bin/env python3
"""Ingest structured MRLP datasets (incompatibilities and hazards) into DuckDB."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure project root on path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.rag.ingestion_service import KnowledgeIngestionService  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest structured MRLP JSONL datasets.")
    parser.add_argument(
        "--incompatibilities",
        type=Path,
        help="Path to JSONL file with cas_a, cas_b, rule, source, justification (optional).",
    )
    parser.add_argument(
        "--hazards",
        type=Path,
        help="Path to JSONL file with cas, hazard_flags, idlh/pel/rel/env_risk, source (optional).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    service = KnowledgeIngestionService()

    if args.incompatibilities:
        summary = service.ingest_structured_incompatibilities(args.incompatibilities)
        print(f"[Incompatibilities] processed={summary.processed} skipped={summary.skipped} errors={summary.errors}")

    if args.hazards:
        summary = service.ingest_structured_hazards(args.hazards)
        print(f"[Hazards] processed={summary.processed} skipped={summary.skipped} errors={summary.errors}")

    if not args.incompatibilities and not args.hazards:
        print("Nothing to ingest. Provide --incompatibilities and/or --hazards.")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
