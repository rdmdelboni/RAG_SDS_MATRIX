#!/usr/bin/env python3
"""
Periodic harvester runner: read CAS list from a file and run harvest (+ optional processing) on a schedule.

Example:
  ./scripts/harvest_scheduler.py --cas-file cas_list.txt --interval 60 --process --output data/input/harvested
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import List

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.harvester.core import SDSHarvester  # noqa: E402
from src.harvester.inventory_sync import InventorySync  # noqa: E402
from src.sds.processor import SDSProcessor  # noqa: E402
from src.utils.logger import get_logger  # noqa: E402

logger = get_logger("harvest_scheduler")


def read_cas(path: Path) -> List[str]:
    return [line.strip() for line in path.read_text().splitlines() if line.strip() and not line.startswith("#")]


def run_once(cas_numbers: List[str], output_dir: Path, limit: int, process: bool, use_rag: bool) -> None:
    harvester = SDSHarvester()
    sync = InventorySync()
    processor = SDSProcessor() if process else None

    output_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Harvester providers: %d", len(harvester.providers))
    if sync.enabled:
        logger.info("Inventory sync enabled (mode=%s)", sync.mode)

    for cas in cas_numbers:
        results = harvester.find_sds(cas)
        if not results:
            logger.info("No SDS found for %s", cas)
            continue
        for res in results[:limit]:
            path = harvester.download_sds(res, output_dir)
            if path:
                # inventory_sync now handles database recording automatically
                sync.sync_download(cas, path, source=res.source, url=res.url)
                if processor:
                    try:
                        processor.process(path, use_rag=use_rag)
                    except Exception as exc:  # pragma: no cover
                        logger.warning("Processing failed for %s: %s", path, exc)
            else:
                # inventory_sync now handles database recording automatically
                sync.mark_missing(cas, source=res.source, url=res.url, error_message="download failed")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run harvester on a schedule.")
    parser.add_argument("--cas-file", type=Path, required=True, help="Path to file with CAS numbers (one per line).")
    parser.add_argument("--interval", type=int, default=60, help="Interval in minutes between runs (default: 60).")
    parser.add_argument("--iterations", type=int, default=0, help="Number of iterations (0 = infinite).")
    parser.add_argument("--output", type=Path, default=Path("data/input/harvested"), help="Download folder.")
    parser.add_argument("--limit", type=int, default=3, help="Max downloads per CAS per run.")
    parser.add_argument("--process", action="store_true", help="Process downloaded SDS immediately.")
    parser.add_argument("--no-rag", action="store_true", help="Disable RAG during processing.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    cas_numbers = read_cas(args.cas_file)
    if not cas_numbers:
        logger.error("No CAS numbers found in %s", args.cas_file)
        return 1

    iteration = 0
    while True:
        iteration += 1
        logger.info("=== Harvest run %d ===", iteration)
        run_once(
            cas_numbers=cas_numbers,
            output_dir=args.output,
            limit=args.limit,
            process=args.process,
            use_rag=not args.no_rag,
        )
        if args.iterations and iteration >= args.iterations:
            break
        logger.info("Sleeping for %d minutes", args.interval)
        time.sleep(args.interval * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
