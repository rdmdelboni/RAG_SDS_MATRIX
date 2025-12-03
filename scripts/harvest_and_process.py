#!/usr/bin/env python3
"""
Harvest SDS by CAS list and optionally process them with the SDS pipeline.

Usage:
  ./scripts/harvest_and_process.py --cas-file cas_list.txt --output data/input/harvested --process
  ./scripts/harvest_and_process.py 67-64-1 64-17-5 --process
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable, List

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.harvester.core import SDSHarvester  # noqa: E402
from src.harvester.inventory_sync import InventorySync  # noqa: E402
from src.sds.processor import SDSProcessor  # noqa: E402
from src.utils.logger import get_logger  # noqa: E402


logger = get_logger("harvest_and_process")


def read_cas_from_file(path: Path) -> List[str]:
    cas_numbers = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        cas_numbers.append(line)
    return cas_numbers


def harvest(cas_numbers: Iterable[str], output_dir: Path, download_limit: int) -> List[Path]:
    harvester = SDSHarvester()
    sync = InventorySync()
    downloaded: List[Path] = []

    logger.info("Initialized harvester with %d providers", len(harvester.providers))
    if sync.enabled:
        logger.info("Inventory sync enabled (mode=%s)", sync.mode)

    output_dir.mkdir(parents=True, exist_ok=True)

    for cas in cas_numbers:
        logger.info("Searching for CAS %s", cas)
        results = harvester.find_sds(cas)
        if not results:
            logger.warning("No SDS found for %s", cas)
            continue

        for res in results[:download_limit]:
            logger.info("Downloading %s from %s", res.url, res.source)
            file_path = harvester.download_sds(res, output_dir)
            if file_path:
                downloaded.append(file_path)
                # inventory_sync now handles database recording automatically
                sync.sync_download(cas, file_path, source=res.source, url=res.url)
            else:
                # inventory_sync now handles database recording automatically
                sync.mark_missing(cas, source=res.source, url=res.url, error_message="download failed")
    return downloaded


def process_files(file_paths: List[Path], use_rag: bool = True) -> None:
    if not file_paths:
        logger.info("No files to process.")
        return

    processor = SDSProcessor()
    for file_path in file_paths:
        try:
            res = processor.process(file_path, use_rag=use_rag)
            logger.info(
                "Processed %s (status=%s, completeness=%.2f)",
                file_path.name,
                res.status,
                res.completeness,
            )
        except Exception as exc:
            logger.warning("Processing failed for %s: %s", file_path, exc)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Harvest SDS by CAS and optionally process them."
    )
    parser.add_argument("cas_numbers", nargs="*", help="CAS numbers (if no --cas-file).")
    parser.add_argument(
        "--cas-file",
        type=Path,
        help="Path to a text file with one CAS per line.",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=Path("data/input/harvested"),
        help="Folder to store downloaded SDS files.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=3,
        help="Max downloads per CAS (default: 3).",
    )
    parser.add_argument(
        "--process",
        action="store_true",
        help="Immediately process downloaded SDS files with the SDS pipeline.",
    )
    parser.add_argument(
        "--no-rag",
        action="store_true",
        help="Disable RAG enrichment during processing.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    cas_numbers = args.cas_numbers or []
    if args.cas_file:
        cas_numbers.extend(read_cas_from_file(args.cas_file))
    cas_numbers = [c.strip() for c in cas_numbers if c.strip()]
    if not cas_numbers:
        logger.error("No CAS numbers provided.")
        return 1

    downloads = harvest(cas_numbers, args.output, args.limit)
    logger.info("Downloads complete: %d files", len(downloads))

    if args.process:
        process_files(downloads, use_rag=not args.no_rag)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
