"""Chemical name normalization utilities.

Non-destructive: keeps original value, returns a normalized variant
for internal use. Downstream code may choose which to display.
"""

from __future__ import annotations

import re
from typing import Tuple

# Simple synonym / formula mapping (extendable)
_FORMULA_SYNONYMS = {
    "H2SO4": "Ácido Sulfúrico",
    "HCL": "Ácido Clorídrico",
    "HNO3": "Ácido Nítrico",
    "H2O2": "Peróxido de Hidrogênio",
    "NAOH": "Hidróxido de Sódio",
    "KOH": "Hidróxido de Potássio",
    "NH3": "Amônia",
    "H3PO4": "Ácido Fosfórico",
    "C2H5OH": "Ethanol",
    "CH3OH": "Methanol",
}

_BRAND_TOKENS = {
    "ACME",
    "BRAND",
    "TRADE",
    "INDÚSTRIA",
    "FABRICANTE",
}

_CONCENTRATION_PATTERN = re.compile(r"\b(\d{1,3})%\b")
_PURITY_PATTERN = re.compile(r"\b(>\s*\d{1,3}%|\d{1,3}\s*%\s*pure)\b", re.IGNORECASE)


def normalize_product_name(value: str) -> Tuple[str, bool]:
    """Return normalized chemical name and whether it changed.

    Rules (non-destructive):
    - Map exact formula tokens to canonical names
    - Remove trailing concentration (e.g., "Ácido Sulfúrico 98%" → "Ácido Sulfúrico")
    - Remove purity markers ("> 99% pure")
    - Strip obvious brand tokens at start/end (ACME, BRAND)
    - Trim whitespace
    """
    original = value or ""
    working = original.strip()
    changed = False

    # Early exit if too short or looks like a code
    if len(working) < 4:
        return original, False

    # Formula mapping (exact match, case-insensitive)
    upper = working.upper()
    if upper in _FORMULA_SYNONYMS:
        working = _FORMULA_SYNONYMS[upper]
        changed = True

    # Remove trailing concentration
    m = _CONCENTRATION_PATTERN.search(working)
    if m:
        # Only drop if concentration near end
        start, end = m.span()
        if end >= len(working) - 4:  # near end
            working = working[:start].rstrip(" -:,/")
            changed = True

    # Remove purity markers
    working = _PURITY_PATTERN.sub("", working).strip()

    # Remove brand tokens at edges
    tokens = working.split()
    if tokens and tokens[0].upper() in _BRAND_TOKENS:
        tokens = tokens[1:]
        changed = True
    if tokens and tokens[-1].upper() in _BRAND_TOKENS:
        tokens = tokens[:-1]
        changed = True
    working = " ".join(tokens).strip()

    # Final collapse of multiple spaces
    working = re.sub(r"\s{2,}", " ", working).strip()

    # Avoid over-normalization: if result becomes empty, revert
    if not working:
        return original, False

    return (working, working != original or changed)


__all__ = ["normalize_product_name"]
