"""Manufacturer profile routing and regex overrides."""
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import re

from ..utils.logger import get_logger
from .regex_catalog import RegexCatalog, get_regex_catalog

logger = get_logger(__name__)


@dataclass
class ManufacturerProfile:
    name: str
    identifiers: List[str]  # Strings/regex to match in header/footer/title
    layout_type: str = "standard"  # standard, two_column, compact
    regex_overrides: Optional[Dict[str, re.Pattern]] = None  # Field-specific regex overrides
    version: str = "builtin"
    source: str = "builtin"


class ProfileRouter:
    """Detects manufacturer and routes to specific processing profiles."""

    def __init__(self, regex_catalog: Optional[RegexCatalog] = None):
        self.catalog = regex_catalog or get_regex_catalog()
        self.profiles = self._load_profiles()
        self.default_profile = ManufacturerProfile(
            name="Generic", identifiers=[], layout_type="standard"
        )

    def _load_profiles(self) -> List[ManufacturerProfile]:
        profiles: List[ManufacturerProfile] = []
        for profile_def in self.catalog.profiles:
            compiled = self.catalog.compiled_patterns_for(profile_def)
            profiles.append(
                ManufacturerProfile(
                    name=profile_def.name,
                    identifiers=profile_def.identifiers,
                    layout_type="standard",
                    regex_overrides=compiled or None,
                    version=profile_def.version,
                    source="catalog",
                )
            )
        return profiles

    def identify_profile(self, text: str, preferred: str | None = None) -> ManufacturerProfile:
        """
        Identify the manufacturer profile from document text.
        Uses the first 3000 characters (header area) for detection.
        """
        if preferred:
            for profile in self.profiles:
                if profile.name.lower() == preferred.lower():
                    logger.info("Using preferred manufacturer profile: %s", profile.name)
                    return profile

        header_text = text[:3000]
        header_upper = header_text.upper()

        for profile in self.profiles:
            for identifier in profile.identifiers:
                try:
                    # Try regex match first, then substring fallback
                    if re.search(identifier, header_text, re.IGNORECASE):
                        logger.info("Detected Manufacturer Profile (regex): %s", profile.name)
                        return profile
                except re.error:
                    pass
                if identifier.upper() in header_upper:
                    logger.info("Detected Manufacturer Profile (substring): %s", profile.name)
                    return profile

        logger.debug("No specific manufacturer detected, using Generic profile")
        return self.default_profile

    def list_profiles(self) -> List[str]:
        """Return available profile names for UI/CLI surfacing."""
        return [p.name for p in self.profiles]
