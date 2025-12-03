"""
Manufacturer Profile Router for SDS processing.
Identifies the manufacturer of an SDS to select optimized extraction profiles.
"""
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import re
from ..utils.logger import get_logger

logger = get_logger(__name__)

@dataclass
class ManufacturerProfile:
    name: str
    identifiers: List[str]  # Strings/Regex to match in header/footer/title
    layout_type: str = "standard" # standard, two_column, compact
    regex_overrides: Optional[Dict[str, str]] = None # Field-specific regex overrides

class ProfileRouter:
    """Detects manufacturer and routes to specific processing profiles."""
    
    def __init__(self):
        self.profiles = [
            ManufacturerProfile(
                name="Sigma-Aldrich",
                identifiers=["SIGMA-ALDRICH", "MERCK", "MILLIPORE"],
                layout_type="standard",
                regex_overrides={
                    "product_name": r"Product name\s*:\s*(.+?)(?:\n|$)",
                    "cas_number": r"CAS-No\.\s*:\s*(\d{2,7}-\d{2}-\d)",
                }
            ),
            ManufacturerProfile(
                name="Fisher Scientific",
                identifiers=["FISHER SCIENTIFIC", "THERMO FISHER"],
                layout_type="standard",
                regex_overrides={
                     "product_name": r"Product Name\s+(.+?)(?:\n|$)",
                }
            ),
             ManufacturerProfile(
                name="VWR",
                identifiers=["VWR INTERNATIONAL", "AVANTOR"],
                layout_type="two_column",
            ),
        ]
        # Default profile
        self.default_profile = ManufacturerProfile(
            name="Generic",
            identifiers=[],
            layout_type="standard"
        )

    def identify_profile(self, text: str) -> ManufacturerProfile:
        """
        Identify the manufacturer profile from document text.
        Uses the first 2000 characters (header area) for detection.
        """
        # Scan header area for identifiers
        header_text = text[:3000].upper()
        
        for profile in self.profiles:
            for identifier in profile.identifiers:
                if identifier in header_text:
                    logger.info(f"Detected Manufacturer Profile: {profile.name}")
                    return profile
        
        logger.debug("No specific manufacturer detected, using Generic profile")
        return self.default_profile
