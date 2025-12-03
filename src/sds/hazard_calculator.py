"""
Hazard Logic Calculator for validating SDS consistency.
Calculates expected hazards based on mixture composition and GHS rules.
"""
from typing import List, Dict, Any, Optional
import re
from dataclasses import dataclass
from ..utils.logger import get_logger

logger = get_logger(__name__)

@dataclass
class Component:
    name: str
    cas: Optional[str]
    min_conc: float
    max_conc: float
    
@dataclass
class CalculatedHazard:
    hazard_code: str
    category: str
    basis: str  # Explanation (e.g., "= 10% of Component A")

class HazardCalculator:
    """Calculates expected GHS hazards from component data."""
    
    def __init__(self):
        # Simplified GHS Rules Knowledge Base
        # Format: {HazardCode: {ComponentKeyword: Threshold}}
        # Real implementation would link CAS to Hazard Class, here we use keywords for prototype
        self.rules = {
            "H314": [ # Causes severe skin burns and eye damage
                {"keywords": ["SULFURIC ACID", "HYDROCHLORIC ACID", "SODIUM HYDROXIDE"], "threshold": 10.0, "category": "1A"},
                {"keywords": ["PHOSPHORIC ACID"], "threshold": 25.0, "category": "1B"}
            ],
            "H315": [ # Causes skin irritation
                {"keywords": ["SULFURIC ACID", "HYDROCHLORIC ACID", "SODIUM HYDROXIDE"], "threshold": 1.0, "category": "2"},
                {"keywords": ["XYLENE", "TOLUENE"], "threshold": 10.0, "category": "2"}
            ],
            "H225": [ # Highly flammable liquid and vapour
                {"keywords": ["ACETONE", "ETHANOL", "METHANOL"], "threshold": 50.0, "category": "2"}
            ],
            "H350": [ # May cause cancer
                {"keywords": ["BENZENE", "FORMALDEHYDE"], "threshold": 0.1, "category": "1A"}
            ]
        }

    def parse_composition(self, composition_text: str) -> List[Component]:
        """
        Parse composition text into structured components.
        Expected format: "Name (CAS: X-X-X) ... Conc: Y-Z%" or similar.
        This is a best-effort parser for the prototype.
        """
        components = []
        # Simple line-based parser assuming the extractor provided a list or clear text
        lines = composition_text.split('\n')
        
        for line in lines:
            # Extract CAS
            cas_match = re.search(r'\b(\d{2,7}-\d{2}-\d)\b', line)
            cas = cas_match.group(1) if cas_match else None
            
            # Extract Concentration
            # Matches: "5-10%", "< 5%", "10 %", etc.
            conc_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:-\s*(\d+(?:\.\d+)?))?\s*%', line)
            
            if conc_match:
                min_val = float(conc_match.group(1))
                max_val = float(conc_match.group(2)) if conc_match.group(2) else min_val
                
                # Extract Name (cleanup remainder)
                name = line
                if cas: name = name.replace(cas, "")
                if conc_match.group(0): name = name.replace(conc_match.group(0), "")
                name = re.sub(r'[(),:;]', '', name).strip()
                
                components.append(Component(name, cas, min_val, max_val))
                
        return components

    def calculate_hazards(self, components: List[Component]) -> List[CalculatedHazard]:
        """Apply GHS rules to components to find expected hazards."""
        results = []
        
        for code, rules_list in self.rules.items():
            for rule in rules_list:
                for comp in components:
                    # Check if component matches rule keywords
                    is_match = any(k in comp.name.upper() for k in rule["keywords"])
                    
                    if is_match:
                        # Use max concentration for worst-case scenario classification
                        if comp.max_conc >= rule["threshold"]:
                            results.append(CalculatedHazard(
                                hazard_code=code,
                                category=rule["category"],
                                basis=f"{comp.name} ({comp.max_conc}%) >= {rule['threshold']}%"
                            ))
                            
        return results

    def validate_against_declared(self, calculated: List[CalculatedHazard], declared_h_codes: List[str]) -> Dict[str, Any]:
        """
        Compare calculated hazards vs declared H-codes.
        Returns a validation report.
        """
        declared_set = set(code.strip() for code in declared_h_codes)
        missing = []
        
        for calc in calculated:
            if calc.hazard_code not in declared_set:
                missing.append(calc)
                
        status = "valid"
        if missing:
            status = "inconsistent"
            
        return {
            "status": status,
            "missing_hazards": [vars(m) for m in missing],
            "calculated_count": len(calculated),
            "declared_count": len(declared_set)
        }
