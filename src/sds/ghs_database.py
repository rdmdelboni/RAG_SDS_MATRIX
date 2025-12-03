"""GHS Classification Database for accurate hazard determination.

This module provides structured CAS → Hazard mappings from authoritative sources
instead of keyword matching. Integrates with:
- ECHA C&L Inventory (EU)
- NIOSH Chemical Database (US)
- PubChem GHS classifications
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional

try:
    from ..config.settings import get_settings
    from ..utils.logger import get_logger
except ImportError:
    # Fallback for direct module usage
    def get_settings():
        from types import SimpleNamespace
        return SimpleNamespace(paths=SimpleNamespace(data_dir=Path("data")))
    
    def get_logger(name):
        import logging
        return logging.getLogger(name)

logger = get_logger(__name__)


@dataclass
class GHSClassification:
    """GHS hazard classification for a chemical."""
    
    cas_number: str
    hazard_code: str  # e.g., H225, H315, H350
    category: str  # e.g., 1, 1A, 2
    hazard_class: str  # e.g., Flammable liquids, Skin corrosion/irritation
    statement: str  # e.g., "Highly flammable liquid and vapor"
    source: str  # e.g., ECHA, NIOSH, PubChem
    confidence: float = 1.0  # 0-1, based on source authority


class GHSDatabase:
    """SQLite-based GHS classification database.
    
    Database schema:
        classifications (
            cas_number TEXT,
            hazard_code TEXT,
            category TEXT,
            hazard_class TEXT,
            statement TEXT,
            source TEXT,
            confidence REAL,
            PRIMARY KEY (cas_number, hazard_code, source)
        )
        
        components (
            parent_cas TEXT,
            component_cas TEXT,
            min_concentration REAL,
            max_concentration REAL,
            component_name TEXT,
            PRIMARY KEY (parent_cas, component_cas)
        )
    """
    
    def __init__(self, db_path: Optional[Path] = None):
        """Initialize GHS database.
        
        Args:
            db_path: Path to SQLite database (default: data/ghs/classifications.db)
        """
        if db_path is None:
            settings = get_settings()
            db_path = settings.paths.data_dir / "ghs" / "classifications.db"
        
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self._init_schema()
        logger.info("GHS database initialized: %s", self.db_path)
    
    def _init_schema(self) -> None:
        """Create database tables if they don't exist."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS classifications (
                    cas_number TEXT NOT NULL,
                    hazard_code TEXT NOT NULL,
                    category TEXT,
                    hazard_class TEXT,
                    statement TEXT,
                    source TEXT NOT NULL,
                    confidence REAL DEFAULT 1.0,
                    PRIMARY KEY (cas_number, hazard_code, source)
                )
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_cas
                ON classifications(cas_number)
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS components (
                    parent_cas TEXT NOT NULL,
                    component_cas TEXT NOT NULL,
                    min_concentration REAL,
                    max_concentration REAL,
                    component_name TEXT,
                    PRIMARY KEY (parent_cas, component_cas)
                )
            """)
            
            conn.commit()
    
    def get_classifications(self, cas_number: str) -> List[GHSClassification]:
        """Get all GHS classifications for a CAS number.
        
        Args:
            cas_number: CAS registry number (with or without dashes)
            
        Returns:
            List of GHS classifications, ordered by confidence (high to low)
        """
        # Normalize CAS number
        cas_clean = cas_number.replace("-", "").strip()
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT cas_number, hazard_code, category, hazard_class,
                       statement, source, confidence
                FROM classifications
                WHERE REPLACE(cas_number, '-', '') = ?
                ORDER BY confidence DESC, source
            """, (cas_clean,))
            
            return [
                GHSClassification(
                    cas_number=row['cas_number'],
                    hazard_code=row['hazard_code'],
                    category=row['category'] or "",
                    hazard_class=row['hazard_class'] or "",
                    statement=row['statement'] or "",
                    source=row['source'],
                    confidence=row['confidence']
                )
                for row in cursor.fetchall()
            ]
    
    def add_classification(self, classification: GHSClassification) -> None:
        """Add or update a GHS classification."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO classifications
                    (cas_number, hazard_code, category, hazard_class,
                     statement, source, confidence)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                classification.cas_number,
                classification.hazard_code,
                classification.category,
                classification.hazard_class,
                classification.statement,
                classification.source,
                classification.confidence
            ))
            conn.commit()
    
    def bulk_import_echa(self, json_path: Path) -> int:
        """Import ECHA C&L Inventory data.
        
        Download from: https://echa.europa.eu/information-on-chemicals/cl-inventory-database
        
        Args:
            json_path: Path to ECHA JSON export
            
        Returns:
            Number of classifications imported
        """
        count = 0
        data = json.loads(json_path.read_text())
        
        with sqlite3.connect(self.db_path) as conn:
            for entry in data:
                cas = entry.get('cas_number')
                if not cas:
                    continue
                
                for hazard in entry.get('hazards', []):
                    conn.execute("""
                        INSERT OR IGNORE INTO classifications
                            (cas_number, hazard_code, category, hazard_class,
                             statement, source, confidence)
                        VALUES (?, ?, ?, ?, ?, 'ECHA', 0.95)
                    """, (
                        cas,
                        hazard.get('code'),
                        hazard.get('category'),
                        hazard.get('class'),
                        hazard.get('statement'),
                    ))
                    count += 1
            
            conn.commit()
        
        logger.info("Imported %d ECHA classifications", count)
        return count
    
    def bulk_import_pubchem(self, json_path: Path) -> int:
        """Import PubChem GHS data.
        
        Use PubChem API or bulk downloads:
        https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{CID}/JSON
        
        Args:
            json_path: Path to PubChem JSON data
            
        Returns:
            Number of classifications imported
        """
        count = 0
        data = json.loads(json_path.read_text())
        
        with sqlite3.connect(self.db_path) as conn:
            for compound in data:
                cas = None
                for prop in compound.get('props', []):
                    if prop.get('urn', {}).get('label') == 'CAS':
                        cas = prop.get('value', {}).get('sval')
                        break
                
                if not cas:
                    continue
                
                # Extract GHS from sections
                for section in compound.get('sections', []):
                    if 'GHS' in section.get('heading', ''):
                        for info in section.get('information', []):
                            hazard_code = info.get('code')
                            if hazard_code and hazard_code.startswith('H'):
                                conn.execute("""
                                    INSERT OR IGNORE INTO classifications
                                        (cas_number, hazard_code, category,
                                         statement, source, confidence)
                                    VALUES (?, ?, ?, ?, 'PubChem', 0.85)
                                """, (
                                    cas,
                                    hazard_code,
                                    info.get('category'),
                                    info.get('statement'),
                                ))
                                count += 1
            
            conn.commit()
        
        logger.info("Imported %d PubChem classifications", count)
        return count
    
    def get_mixture_hazards(
        self,
        components: List[Dict[str, any]]
    ) -> List[GHSClassification]:
        """Calculate mixture hazards based on component concentrations.
        
        Applies GHS mixture rules (Chapter 1.1.3) for hazard classification
        based on component concentrations and hazard classes.
        
        Args:
            components: List of dicts with keys:
                - cas_number: str
                - min_concentration: float (% w/w)
                - max_concentration: float (% w/w)
                - name: str (optional)
        
        Returns:
            Calculated mixture hazards
        """
        mixture_hazards: Dict[str, GHSClassification] = {}
        
        for component in components:
            cas = component.get('cas_number')
            max_conc = component.get('max_concentration', 0)
            
            if not cas or max_conc <= 0:
                continue
            
            classifications = self.get_classifications(cas)
            
            for classification in classifications:
                # Apply concentration limits per GHS rules
                threshold = self._get_concentration_threshold(
                    classification.hazard_code,
                    classification.category
                )
                
                if max_conc >= threshold:
                    # Mixture inherits this hazard
                    key = f"{classification.hazard_code}_{classification.category}"
                    
                    if key not in mixture_hazards:
                        mixture_hazards[key] = GHSClassification(
                            cas_number="MIXTURE",
                            hazard_code=classification.hazard_code,
                            category=classification.category,
                            hazard_class=classification.hazard_class,
                            statement=classification.statement,
                            source=f"Calculated from {component.get('name', cas)}",
                            confidence=0.9
                        )
        
        return list(mixture_hazards.values())
    
    def _get_concentration_threshold(
        self,
        hazard_code: str,
        category: str
    ) -> float:
        """Get GHS concentration threshold for mixture classification.
        
        Based on GHS Chapter 1.1.3 and CLP Regulation Annex I Part 1.
        """
        # Simplified thresholds - full implementation would be more complex
        thresholds = {
            # Acute toxicity
            'H300': {'1': 0.1, '2': 1.0, '3': 5.0, '4': 25.0},  # Oral
            'H310': {'1': 0.1, '2': 1.0, '3': 5.0, '4': 25.0},  # Dermal
            'H330': {'1': 0.1, '2': 0.5, '3': 1.0, '4': 5.0},   # Inhalation
            
            # Skin/eye irritation
            'H314': {'1A': 1.0, '1B': 5.0, '1C': 5.0},  # Skin corrosion
            'H315': {'2': 10.0},  # Skin irritation
            'H318': {'1': 10.0},  # Eye damage
            'H319': {'2': 10.0},  # Eye irritation
            
            # Respiratory sensitization
            'H334': {'1': 0.1, '1A': 0.1, '1B': 1.0},
            
            # Skin sensitization
            'H317': {'1': 0.1, '1A': 0.1, '1B': 1.0},
            
            # Carcinogenicity
            'H350': {'1A': 0.1, '1B': 0.1, '2': 1.0},
            'H351': {'2': 1.0},
            
            # Mutagenicity
            'H340': {'1A': 0.1, '1B': 0.1, '2': 1.0},
            'H341': {'2': 1.0},
            
            # Reproductive toxicity
            'H360': {'1A': 0.3, '1B': 0.3, '2': 3.0},
            'H361': {'2': 3.0},
            
            # Flammable liquids
            'H225': {'2': 10.0},
            'H226': {'3': 10.0},
        }
        
        return thresholds.get(hazard_code, {}).get(category, 100.0)


@lru_cache(maxsize=1)
def get_ghs_database() -> GHSDatabase:
    """Get cached GHS database instance."""
    return GHSDatabase()
