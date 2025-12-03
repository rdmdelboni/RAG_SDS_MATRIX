#!/usr/bin/env python3
"""
Build an experiment packet: bundle matrix exports and selected SDS PDFs into a zip.

Usage:
  ./scripts/export_experiment_packet.py --matrix data/output/matrix.csv --sds-dir data/input/harvested --cas 67-64-1 64-17-5 --out packets
"""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Iterable, List


def find_sds_files(sds_dir: Path, cas_list: Iterable[str]) -> List[Path]:
    cas_set = {c.replace("-", "").strip() for c in cas_list}
    matches: List[Path] = []
    for path in sds_dir.rglob("*.pdf"):
        norm = path.stem.replace("-", "").upper()
        if any(norm.startswith(cas.replace("-", "").upper()) for cas in cas_set):
            matches.append(path)
    return matches


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export an experiment packet zip.")
    parser.add_argument(
        "--matrix",
        type=Path,
        required=True,
        help="Path to matrix export file (CSV/XLSX/JSON).",
    )
    parser.add_argument(
        "--sds-dir",
        type=Path,
        required=True,
        help="Directory containing SDS PDFs.",
    )
    parser.add_argument(
        "--cas",
        nargs="+",
        required=True,
        help="CAS numbers to include in the packet.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("packets"),
        help="Output directory to place the zip file.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    sds_files = find_sds_files(args.sds_dir, args.cas)
    if not sds_files:
        print("No matching SDS PDFs found for given CAS list.")
        return 1

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        packet_meta = {
            "cas_numbers": args.cas,
            "matrix_file": args.matrix.name,
            "sds_files": [p.name for p in sds_files],
        }
        # copy matrix
        shutil.copy2(args.matrix, tmp / args.matrix.name)
        # copy SDS
        for pdf in sds_files:
            shutil.copy2(pdf, tmp / pdf.name)
        # metadata
        (tmp / "packet_meta.json").write_text(json.dumps(packet_meta, indent=2))

        # zip it
        zip_path = args.out / f"experiment_packet_{args.cas[0].replace('-', '')}.zip"
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for file_path in tmp.iterdir():
                zf.write(file_path, arcname=file_path.name)

    print(f"Created packet: {zip_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
