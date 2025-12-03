"""Regex catalog loader for manufacturer-specific extraction profiles."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional

from ..config.settings import get_settings
from ..utils.logger import get_logger

logger = get_logger(__name__)


def _compile_flags(flag_string: str) -> int:
    """Convert a short flags string (e.g., 'im') to a re flags bitmask."""
    flags = 0
    for ch in flag_string.lower():
        if ch == "i":
            flags |= re.IGNORECASE
        elif ch == "m":
            flags |= re.MULTILINE
        elif ch == "s":
            flags |= re.DOTALL
        elif ch == "x":
            flags |= re.VERBOSE
    return flags


@dataclass(frozen=True)
class RegexPatternDef:
    pattern: str
    flags: str = "im"


@dataclass(frozen=True)
class RegexProfileDef:
    name: str
    identifiers: List[str]
    regexes: Dict[str, RegexPatternDef]
    version: str = "builtin"
    notes: Optional[str] = None


def _builtin_profiles() -> List[RegexProfileDef]:
    """Hard-coded starter profiles (used if no catalog is present)."""
    return [
        RegexProfileDef(
            name="Sigma-Aldrich",
            identifiers=["SIGMA-ALDRICH", "MERCK", "MILLIPORE"],
            regexes={
                "product_name": RegexPatternDef(
                    pattern=r"Product name\s*:\s*(.+?)(?:\n|$)"
                ),
                "cas_number": RegexPatternDef(
                    pattern=r"CAS-No\.\s*:\s*(\d{2,7}-\d{2}-\d)"
                ),
                "hazard_class": RegexPatternDef(
                    pattern=r"Classification\s*:\s*UN\s*\d{4}\s*[,;-]?\s*Class\s*([\d.]+)"
                ),
            },
        ),
        RegexProfileDef(
            name="Fisher Scientific",
            identifiers=["FISHER SCIENTIFIC", "THERMO FISHER"],
            regexes={
                "product_name": RegexPatternDef(
                    pattern=r"Product Name\s*[:\-]\s*([^\n]{4,120})"
                ),
                "cas_number": RegexPatternDef(
                    pattern=r"CAS\s*(?:No|Number)\s*[:\-]?\s*(\d{2,7}-\d{2}-\d)"
                ),
            },
        ),
        RegexProfileDef(
            name="VWR",
            identifiers=["VWR INTERNATIONAL", "AVANTOR"],
            regexes={
                "product_name": RegexPatternDef(
                    pattern=r"Product identifier\s*[:\-]\s*([^\n]{4,120})"
                ),
                "cas_number": RegexPatternDef(
                    pattern=r"CAS\s*No\.\s*[:\-]?\s*(\d{2,7}-\d{2}-\d)"
                ),
            },
        ),
    ]


class RegexCatalog:
    """Load manufacturer regex profiles from JSON, with built-in defaults."""

    def __init__(self, catalog_path: Optional[Path] = None) -> None:
        settings = get_settings()
        default_path = settings.paths.data_dir / "regex" / "regexes.json"
        env_path = os.getenv("REGEX_CATALOG_PATH")
        self.catalog_path = Path(catalog_path or env_path or default_path)
        self.catalog_path.parent.mkdir(parents=True, exist_ok=True)
        self._profiles: List[RegexProfileDef] = self._load_profiles()

    def _load_profiles(self) -> List[RegexProfileDef]:
        profiles: Dict[str, RegexProfileDef] = {
            p.name.lower(): p for p in _builtin_profiles()
        }

        if self.catalog_path.exists():
            try:
                with self.catalog_path.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                for raw in data.get("profiles", []):
                    name = raw.get("name")
                    if not name:
                        continue
                    regexes: Dict[str, RegexPatternDef] = {}
                    for field, body in raw.get("regexes", {}).items():
                        if isinstance(body, dict) and "pattern" in body:
                            regexes[field] = RegexPatternDef(
                                pattern=body["pattern"], flags=body.get("flags", "im")
                            )
                    if not regexes:
                        continue
                    profile = RegexProfileDef(
                        name=name,
                        identifiers=raw.get("identifiers", []),
                        regexes=regexes,
                        version=raw.get("version", data.get("version", "custom")),
                        notes=raw.get("notes"),
                    )
                    profiles[name.lower()] = profile
                logger.info(
                    "Loaded %d regex profiles from %s",
                    len(data.get("profiles", [])),
                    self.catalog_path,
                )
            except Exception as exc:  # pragma: no cover - best effort
                logger.warning(
                    "Failed to load regex catalog %s: %s", self.catalog_path, exc
                )

        return list(profiles.values())

    def list_profiles(self) -> List[str]:
        return [p.name for p in self._profiles]

    def get_profile(self, name: str) -> Optional[RegexProfileDef]:
        key = name.lower().strip()
        for profile in self._profiles:
            if profile.name.lower() == key:
                return profile
        return None

    def compiled_patterns_for(self, profile: RegexProfileDef) -> Dict[str, re.Pattern]:
        compiled: Dict[str, re.Pattern] = {}
        for field, pattern_def in profile.regexes.items():
            try:
                compiled[field] = re.compile(
                    pattern_def.pattern, _compile_flags(pattern_def.flags)
                )
            except re.error as exc:
                logger.debug("Failed compiling %s.%s: %s", profile.name, field, exc)
        return compiled

    @property
    def profiles(self) -> List[RegexProfileDef]:
        return self._profiles


@lru_cache(maxsize=1)
def get_regex_catalog() -> RegexCatalog:
    """Cached catalog accessor."""
    return RegexCatalog()
