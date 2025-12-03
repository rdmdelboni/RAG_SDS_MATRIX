#!/usr/bin/env python3
"""
Generate a stub SDS PDF from JSON data (CLP-style).

Example:
  ./scripts/generate_sds_stub.py --data examples/sds_stub.json --out output/sds_stub.pdf
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict

from src.sds.sds_generator import SDSGenerator
from src.sds.hazard_calculator import HazardCalculator


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a stub SDS PDF from JSON.")
    parser.add_argument("--data", type=Path, required=True, help="Path to JSON with SDS fields.")
    parser.add_argument("--out", type=Path, required=True, help="Output PDF path.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload: Dict[str, Any] = json.loads(Path(args.data).read_text())

    # Optional hazard calculation if composition present
    hazards = None
    if "composition" in payload:
        calc = HazardCalculator()
        comps = payload.get("composition") or []
        hazards = calc.calculate_hazards(comps)  # type: ignore[arg-type]

    gen = SDSGenerator()
    gen.generate(payload, hazards, args.out)
    print(f"Generated SDS PDF at {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
