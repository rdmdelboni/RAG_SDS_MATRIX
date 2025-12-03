#!/usr/bin/env python3
"""
Helper script to build a PyInstaller bundle for the Qt UI.

Usage:
  ./scripts/package_ui.py --name rag-sds-matrix --onefile
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Package the UI with PyInstaller.")
    parser.add_argument("--name", default="rag-sds-matrix", help="Executable name (default: rag-sds-matrix)")
    parser.add_argument(
        "--onefile",
        action="store_true",
        help="Build a single-file bundle (slower startup, but portable). Default is one-folder.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(__file__).resolve().parent.parent
    cmd = [
        "pyinstaller",
        "--noconfirm",
        "--clean",
        "--name",
        args.name,
        "--add-data",
        f"{root / 'data'}:data",
        "--add-data",
        f"{root / 'src' / 'ui'}:src/ui",
        "--hidden-import",
        "PySide6",
        str(root / "main.py"),
    ]
    if args.onefile:
        cmd.append("--onefile")

    print("Running:", " ".join(str(c) for c in cmd))
    proc = subprocess.run(cmd, cwd=root)
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
