"""Extract chemical ingredients (Section 3) from SDS text.

Goal: identify *all* chemicals listed in an SDS (typically Section 3: composition),
including CAS numbers and, when available, concentration ranges.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable


_DASHES = "\u2010\u2011\u2012\u2013\u2014\u2212"


@dataclass(frozen=True)
class Ingredient:
    cas_number: str | None
    chemical_name: str | None
    concentration_text: str | None
    concentration_min: float | None
    concentration_max: float | None
    concentration_unit: str | None  # typically "%"
    confidence: float
    evidence: str


class IngredientExtractor:
    """Heuristic extractor for SDS ingredient lists."""

    CAS_STRICT_RE = re.compile(r"\b(\d{2,7}-\d{2}-\d)\b")
    # OCR-friendly: allow weird dashes + common last-digit confusions (S->5, O->0, l->1)
    CAS_RELAXED_RE = re.compile(
        rf"\b(\d{{2,7}})[{_DASHES}-](\d{{2}})[{_DASHES}-]([0-9SOlI])\b"
    )

    # Percent concentration patterns commonly found in SDS tables
    PERCENT_RANGE_RE = re.compile(
        r"(?P<min>\d+(?:[.,]\d+)?)\s*(?:-|–|—|~|to|a|até)\s*(?P<max>\d+(?:[.,]\d+)?)\s*%",
        re.IGNORECASE,
    )
    PERCENT_SINGLE_RE = re.compile(r"(?P<val>\d+(?:[.,]\d+)?)\s*%")
    PERCENT_BOUNDED_RE = re.compile(
        r"(?P<op>>=|=>|>|<=|=<|<)\s*(?P<val>\d+(?:[.,]\d+)?)\s*%?",
        re.IGNORECASE,
    )

    # Noise tokens that often appear near composition tables
    _NAME_STOPWORDS = {
        "cas",
        "nº",
        "no",
        "nr",
        "número",
        "numero",
        "number",
        "concentração",
        "concentracao",
        "concentration",
        "componente",
        "component",
        "ingrediente",
        "ingredient",
        "mistura",
        "mixture",
        "substância",
        "substancia",
        "substance",
        "identificação",
        "identificacao",
        "classificação",
        "classificacao",
    }

    def extract(self, text: str, sections: dict[int, str] | None = None) -> list[Ingredient]:
        """Extract a best-effort ingredient list from SDS text.

        Prefers Section 3 if available; falls back to whole document text.
        """
        composition = (sections or {}).get(3) or text
        lines = _iter_reasonable_lines(composition)

        best_by_key: dict[tuple[str | None, str | None], Ingredient] = {}
        for line in lines:
            for ingredient in self._extract_from_line(line):
                key = (ingredient.cas_number, (ingredient.chemical_name or "").lower().strip() or None)
                existing = best_by_key.get(key)
                if existing is None or ingredient.confidence > existing.confidence:
                    best_by_key[key] = ingredient

        # De-dupe further by CAS: keep highest confidence CAS entry
        best_by_cas: dict[str, Ingredient] = {}
        no_cas: list[Ingredient] = []
        for ing in best_by_key.values():
            if ing.cas_number:
                prev = best_by_cas.get(ing.cas_number)
                if prev is None or ing.confidence > prev.confidence:
                    best_by_cas[ing.cas_number] = ing
            else:
                no_cas.append(ing)

        # Return CAS-bearing ingredients first (more useful for matrix/rules joins)
        ingredients = sorted(best_by_cas.values(), key=lambda i: (-i.confidence, i.cas_number or ""))
        ingredients.extend(sorted(no_cas, key=lambda i: (-i.confidence, i.chemical_name or "")))
        return ingredients

    def _extract_from_line(self, line: str) -> Iterable[Ingredient]:
        line_norm = _normalize_line(line)
        if not line_norm:
            return []

        cas_hits = list(self.CAS_RELAXED_RE.finditer(line_norm))
        if not cas_hits:
            # Some SDS list chemicals without CAS; avoid trying to guess from free text.
            return []

        results: list[Ingredient] = []
        for m in cas_hits:
            cas_candidate = self._normalize_cas_match(m)
            if not cas_candidate:
                continue

            name = _extract_name_near_span(line_norm, m.start(), m.end())
            conc = self._extract_concentration(line_norm)

            conf = 0.60
            if "cas" in line_norm.lower():
                conf += 0.10
            if name:
                conf += 0.15
            if conc[0] or conc[1] or conc[2]:
                conf += 0.10
            conf = min(0.99, conf)

            results.append(
                Ingredient(
                    cas_number=cas_candidate,
                    chemical_name=name,
                    concentration_text=conc[0],
                    concentration_min=conc[1],
                    concentration_max=conc[2],
                    concentration_unit=conc[3],
                    confidence=conf,
                    evidence=line.strip(),
                )
            )
        return results

    def _normalize_cas_match(self, match: re.Match[str]) -> str | None:
        # Either strict group(0) or relaxed groups (1,2,3)
        if match.re is self.CAS_STRICT_RE:
            candidate = match.group(1)
            return candidate if is_valid_cas(candidate) else None

        g1, g2, g3 = match.group(1), match.group(2), match.group(3)
        last = g3
        last = {"S": "5", "O": "0", "l": "1", "I": "1"}.get(last, last)
        candidate = f"{g1}-{g2}-{last}"
        return candidate if is_valid_cas(candidate) else None

    def _extract_concentration(self, line: str) -> tuple[str | None, float | None, float | None, str | None]:
        # Range like "60-70%" or "60 – 70 %"
        m = self.PERCENT_RANGE_RE.search(line)
        if m:
            mn = _to_float(m.group("min"))
            mx = _to_float(m.group("max"))
            if mn is not None and mx is not None:
                return (m.group(0).strip(), min(mn, mx), max(mn, mx), "%")

        # Bounded like ">= 90%" or "< 1%"
        m = self.PERCENT_BOUNDED_RE.search(line)
        if m:
            op = m.group("op")
            val = _to_float(m.group("val"))
            if val is not None:
                if op in (">", ">=", "=>"):
                    return (m.group(0).strip(), val, None, "%")
                if op in ("<", "<=", "=<"):
                    return (m.group(0).strip(), None, val, "%")

        # Single percentage
        m = self.PERCENT_SINGLE_RE.search(line)
        if m:
            val = _to_float(m.group("val"))
            if val is not None:
                return (m.group(0).strip(), val, val, "%")

        return (None, None, None, None)


def is_valid_cas(cas: str) -> bool:
    """Validate CAS format and check digit."""
    cas = cas.strip()
    if not re.match(r"^\d{2,7}-\d{2}-\d$", cas):
        return False

    left, mid, check = cas.split("-")
    digits = f"{left}{mid}"
    try:
        check_digit = int(check)
    except ValueError:
        return False

    total = 0
    multiplier = 1
    for ch in reversed(digits):
        total += int(ch) * multiplier
        multiplier += 1

    return (total % 10) == check_digit


def _normalize_line(line: str) -> str:
    if not line:
        return ""
    # Normalize dash variants and collapse whitespace
    for d in _DASHES:
        line = line.replace(d, "-")
    line = re.sub(r"\s+", " ", line).strip()
    return line


def _iter_reasonable_lines(text: str) -> Iterable[str]:
    # Keep enough granularity for table rows while avoiding huge blocks.
    for raw in re.split(r"[\r\n]+", text):
        line = raw.strip()
        if not line:
            continue
        if len(line) < 6:
            continue
        if len(line) > 400:
            # Very long OCR lines tend to be merged paragraphs; splitting improves locality.
            for part in re.split(r"\s{2,}", line):
                part = part.strip()
                if 6 <= len(part) <= 200:
                    yield part
            continue
        yield line


def _looks_like_name(s: str) -> bool:
    if not s:
        return False
    # Require at least 3 letters overall
    if len(re.findall(r"[A-Za-zÀ-ÿ]", s)) < 3:
        return False
    # Avoid obvious header-ish tokens
    low = s.lower()
    if any(tok in low.split() for tok in IngredientExtractor._NAME_STOPWORDS):
        # Still allow if there's a clear chemical name around the stopwords
        if len(low.split()) <= 2:
            return False
    return True


def _clean_name_candidate(s: str) -> str:
    s = s.strip().strip(":-–—|")
    s = re.sub(r"\([^)]*\)$", "", s).strip()
    s = re.sub(r"\b(?:CAS|N[ºo]|No\.?|Número|Numero|Number)\b.*$", "", s, flags=re.IGNORECASE).strip()
    s = re.sub(r"\b\d+(?:[.,]\d+)?\s*%.*$", "", s).strip()
    s = re.sub(r"\s{2,}", " ", s).strip()
    return s


def _extract_name_near_span(line: str, start: int, end: int) -> str | None:
    # Prefer text immediately before the CAS (common in tables)
    before = line[max(0, start - 90) : start]
    after = line[end : min(len(line), end + 90)]

    before = _clean_name_candidate(before)
    after = _clean_name_candidate(after)

    before_parts = [p.strip() for p in re.split(r"[;|,/]", before) if p.strip()]
    after_parts = [p.strip() for p in re.split(r"[;|,/]", after) if p.strip()]

    # Heuristic pick: last meaningful chunk before CAS, else first chunk after CAS
    for cand in reversed(before_parts):
        cand = cand.strip("() ").strip()
        if len(cand) > 2:
            # If "CAS" appears, take chunk before it
            cand = re.sub(r"\bcas\b.*$", "", cand, flags=re.IGNORECASE).strip()
            if _looks_like_name(cand):
                return cand[:120]

    for cand in after_parts:
        cand = cand.strip("() ").strip()
        if _looks_like_name(cand):
            return cand[:120]

    # As a last attempt: capture a name-like token sequence right before CAS
    m = re.search(r"([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ0-9 .,'+/\\-]{2,80})\s*$", before)
    if m:
        cand = _clean_name_candidate(m.group(1))
        if _looks_like_name(cand):
            return cand[:120]

    return None


def _to_float(s: str) -> float | None:
    try:
        return float(s.replace(",", "."))
    except Exception:
        return None
