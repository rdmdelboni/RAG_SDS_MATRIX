"""
PubChem enrichment module for improving and completing SDS extraction data.

This module uses PubChem API to:
1. Validate extracted chemical data
2. Fill in missing fields
3. Enrich with additional chemical properties
4. Cross-validate field consistency
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set
import requests

from ..utils.logger import get_logger
from .external_validator import PubChemClient

logger = get_logger(__name__)


@dataclass
class EnrichmentResult:
    """Result from PubChem enrichment."""
    
    field_name: str
    original_value: Optional[str]
    enriched_value: Optional[str]
    confidence: float
    source: str = "pubchem"
    additional_data: Optional[Dict[str, Any]] = None
    validation_status: str = "pending"
    issues: Optional[List[str]] = None


@dataclass
class ChemicalProperties:
    """Comprehensive chemical properties from PubChem."""
    
    # Identifiers
    cid: Optional[int] = None
    iupac_name: Optional[str] = None
    molecular_formula: Optional[str] = None
    molecular_weight: Optional[float] = None
    canonical_smiles: Optional[str] = None
    isomeric_smiles: Optional[str] = None
    inchi: Optional[str] = None
    inchi_key: Optional[str] = None
    
    # Names and identifiers
    cas_number: Optional[str] = None
    synonyms: Optional[List[str]] = None
    
    # Physical properties
    melting_point: Optional[str] = None
    boiling_point: Optional[str] = None
    flash_point: Optional[str] = None
    density: Optional[float] = None
    vapor_pressure: Optional[str] = None
    vapor_density: Optional[str] = None
    
    # Safety information
    ghs_hazard_statements: Optional[List[str]] = None
    ghs_precautionary_statements: Optional[List[str]] = None
    ghs_pictograms: Optional[List[str]] = None
    un_number: Optional[str] = None
    
    # Chemical classification
    compound_classes: Optional[List[str]] = None
    
    # Metadata
    pubchem_url: Optional[str] = None


class PubChemEnricher:
    """Enriches SDS extraction data using PubChem API."""
    
    def __init__(self, cache_ttl: int = 3600, timeout: int = 30):
        """
        Initialize PubChem enricher.
        
        Args:
            cache_ttl: Cache time-to-live in seconds
            timeout: Request timeout in seconds (default: 30)
        """
        self.client = PubChemClient(cache_ttl=cache_ttl)
        self.timeout = timeout
        logger.info(f"PubChem enricher initialized (timeout: {timeout}s)")
    
    def enrich_extraction(
        self,
        extractions: Dict[str, Dict[str, Any]],
        aggressive: bool = False
    ) -> Dict[str, EnrichmentResult]:
        """
        Enrich extraction results with PubChem data.
        
        Args:
            extractions: Dictionary of extracted fields
            aggressive: If True, attempts to fill all missing fields from PubChem
        
        Returns:
            Dictionary of enrichment results by field name
        """
        enrichments = {}
        
        # Get chemical properties first
        properties = self._fetch_chemical_properties(extractions)
        
        if not properties or not properties.cid:
            logger.debug("Could not fetch chemical properties from PubChem")
            return enrichments
        
        logger.info(f"Found PubChem CID: {properties.cid}")
        
        # Enrich each field
        enrichments.update(self._enrich_identifiers(extractions, properties))
        enrichments.update(self._enrich_physical_properties(extractions, properties))
        enrichments.update(self._enrich_safety_info(extractions, properties))
        enrichments.update(self._cross_validate_fields(extractions, properties))
        
        if aggressive:
            enrichments.update(self._fill_missing_fields(extractions, properties))
        
        return enrichments
    
    def _fetch_chemical_properties(
        self,
        extractions: Dict[str, Dict[str, Any]]
    ) -> Optional[ChemicalProperties]:
        """
        Fetch comprehensive chemical properties from PubChem.
        
        Uses multiple identifiers to find the chemical, in order of reliability:
        1. CAS number (most reliable)
        2. Product name
        3. Molecular formula (least reliable)
        
        Args:
            extractions: Extracted fields
        
        Returns:
            ChemicalProperties object or None if not found
        """
        # Try CAS number first (most reliable)
        cas_number = extractions.get("cas_number", {}).get("value")
        if cas_number:
            logger.debug(f"Looking up chemical by CAS: {cas_number}")
            data = self.client.search_by_cas(cas_number)
            if data:
                return self._parse_pubchem_data(data, cas_number)
        
        # Try product name
        product_name = extractions.get("product_name", {}).get("value")
        if product_name:
            logger.debug(f"Looking up chemical by name: {product_name}")
            data = self.client.search_by_name(product_name)
            if data:
                return self._parse_pubchem_data(data, cas_number)
        
        # Try molecular formula (least reliable - many compounds share formulas)
        molecular_formula = extractions.get("molecular_formula", {}).get("value")
        if molecular_formula:
            logger.debug(f"Looking up chemical by formula: {molecular_formula}")
            data = self._search_by_formula(molecular_formula)
            if data:
                return self._parse_pubchem_data(data, cas_number)
        
        return None
    
    def _search_by_formula(self, formula: str) -> Optional[Dict[str, Any]]:
        """
        Search PubChem by molecular formula.
        
        Args:
            formula: Molecular formula (e.g., H2SO4)
        
        Returns:
            PubChem compound data or None
        """
        encoded_formula = requests.utils.quote(formula)
        cid_url = f"{self.client.BASE_URL}/compound/fastformula/{encoded_formula}/cids/JSON?MaxRecords=1"
        
        cid_data = self.client._make_request(cid_url)
        if not cid_data or "IdentifierList" not in cid_data:
            return None
        
        cids = cid_data["IdentifierList"].get("CID", [])
        if not cids:
            return None
        
        # Get properties for first CID
        cid = cids[0]
        props_url = f"{self.client.BASE_URL}/compound/cid/{cid}/property/MolecularFormula,MolecularWeight,IUPACName,InChI,InChIKey,CanonicalSMILES,IsomericSMILES/JSON"
        
        return self.client._make_request(props_url)
    
    def _parse_pubchem_data(
        self,
        data: Dict[str, Any],
        cas_hint: Optional[str] = None
    ) -> ChemicalProperties:
        """
        Parse PubChem API response into ChemicalProperties.
        
        Args:
            data: Raw PubChem API response
            cas_hint: Optional CAS number hint for enrichment
        
        Returns:
            ChemicalProperties object
        """
        props = ChemicalProperties()
        
        # Basic properties from initial query
        props.cid = data.get("CID")
        props.molecular_formula = data.get("MolecularFormula")
        props.molecular_weight = data.get("MolecularWeight")
        props.iupac_name = data.get("IUPACName")
        props.inchi = data.get("InChI")
        props.inchi_key = data.get("InChIKey")
        props.canonical_smiles = data.get("CanonicalSMILES")
        props.isomeric_smiles = data.get("IsomericSMILES")
        props.cas_number = cas_hint
        
        if props.cid:
            props.pubchem_url = f"https://pubchem.ncbi.nlm.nih.gov/compound/{props.cid}"
            
            # Fetch additional properties
            self._fetch_synonyms(props)
            self._fetch_physical_properties(props)
            self._fetch_ghs_classification(props)
        
        return props
    
    def _fetch_synonyms(self, props: ChemicalProperties) -> None:
        """Fetch synonyms including CAS numbers."""
        if not props.cid:
            return
        
        url = f"{self.client.BASE_URL}/compound/cid/{props.cid}/synonyms/JSON"
        data = self.client._make_request(url)
        
        if data and "InformationList" in data:
            info = data["InformationList"].get("Information", [])
            if info:
                synonyms = info[0].get("Synonym", [])
                props.synonyms = synonyms[:20]  # Limit to 20 most common
                
                # Extract CAS from synonyms if not already set
                if not props.cas_number:
                    import re
                    cas_pattern = re.compile(r'\b(\d{2,7}-\d{2}-\d)\b')
                    for syn in synonyms:
                        match = cas_pattern.match(str(syn))
                        if match:
                            props.cas_number = match.group(1)
                            break
    
    def _fetch_physical_properties(self, props: ChemicalProperties) -> None:
        """Fetch physical properties like melting point, boiling point, etc."""
        if not props.cid:
            return
        
        # Get experimental properties from PubChem
        url = f"{self.client.BASE_URL}/compound/cid/{props.cid}/property/MolecularWeight,XLogP,TPSA,Complexity/JSON"
        data = self.client._make_request(url)
        
        if data and "PropertyTable" in data:
            properties = data["PropertyTable"].get("Properties", [])
            if properties:
                prop_data = properties[0]
                # Store what's available
                # Note: Physical properties like melting/boiling points
                # are typically in the "Description" section, not property API
                pass
    
    def _fetch_ghs_classification(self, props: ChemicalProperties) -> None:
        """Fetch GHS hazard classification."""
        if not props.cid:
            return
        
        url = f"{self.client.BASE_URL}/compound/cid/{props.cid}/classification/JSON"
        data = self.client._make_request(url)
        
        if not data or "Hierarchies" not in data:
            return
        
        # Extract GHS information
        ghs_h_codes = set()
        ghs_p_codes = set()
        ghs_pictograms = set()
        
        for hierarchy in data["Hierarchies"]:
            source = hierarchy.get("SourceName", "")
            if "GHS" in source.upper():
                self._extract_ghs_codes(hierarchy, ghs_h_codes, ghs_p_codes, ghs_pictograms)
        
        if ghs_h_codes:
            props.ghs_hazard_statements = sorted(list(ghs_h_codes))
        if ghs_p_codes:
            props.ghs_precautionary_statements = sorted(list(ghs_p_codes))
        if ghs_pictograms:
            props.ghs_pictograms = sorted(list(ghs_pictograms))
    
    def _extract_ghs_codes(
        self,
        node: Dict[str, Any],
        h_codes: Set[str],
        p_codes: Set[str],
        pictograms: Set[str]
    ) -> None:
        """Recursively extract GHS codes from classification tree."""
        # Check node information
        if "Information" in node:
            for info in node["Information"]:
                name = info.get("Name", "")
                
                # Extract H-codes
                if name.startswith("H") and len(name) >= 4 and name[1:4].isdigit():
                    h_codes.add(name[:4])
                
                # Extract P-codes
                elif name.startswith("P") and len(name) >= 4 and name[1:4].isdigit():
                    p_codes.add(name[:4])
                
                # Extract pictograms
                elif "pictogram" in name.lower():
                    pictograms.add(name)
        
        # Recurse into child nodes
        if "Node" in node:
            for child in node["Node"]:
                self._extract_ghs_codes(child, h_codes, p_codes, pictograms)
    
    def _enrich_identifiers(
        self,
        extractions: Dict[str, Dict[str, Any]],
        properties: ChemicalProperties
    ) -> Dict[str, EnrichmentResult]:
        """Enrich chemical identifiers (CAS, product name, formula)."""
        enrichments = {}
        
        # CAS number enrichment
        if properties.cas_number:
            extracted_cas = extractions.get("cas_number", {}).get("value")
            
            if not extracted_cas:
                # Missing CAS - add from PubChem
                enrichments["cas_number"] = EnrichmentResult(
                    field_name="cas_number",
                    original_value=None,
                    enriched_value=properties.cas_number,
                    confidence=0.85,
                    validation_status="enriched",
                    additional_data={"source": "pubchem_lookup"}
                )
            elif extracted_cas != properties.cas_number:
                # CAS mismatch - flag for review
                enrichments["cas_number"] = EnrichmentResult(
                    field_name="cas_number",
                    original_value=extracted_cas,
                    enriched_value=properties.cas_number,
                    confidence=0.60,
                    validation_status="warning",
                    issues=[f"Extracted CAS ({extracted_cas}) differs from PubChem ({properties.cas_number})"]
                )
        
        # Molecular formula enrichment
        if properties.molecular_formula:
            extracted_formula = extractions.get("molecular_formula", {}).get("value")
            
            if not extracted_formula:
                enrichments["molecular_formula"] = EnrichmentResult(
                    field_name="molecular_formula",
                    original_value=None,
                    enriched_value=properties.molecular_formula,
                    confidence=0.90,
                    validation_status="enriched"
                )
            else:
                # Validate formula
                normalized_extracted = extracted_formula.replace(" ", "").upper()
                normalized_pubchem = properties.molecular_formula.replace(" ", "").upper()
                
                if normalized_extracted != normalized_pubchem:
                    enrichments["molecular_formula"] = EnrichmentResult(
                        field_name="molecular_formula",
                        original_value=extracted_formula,
                        enriched_value=properties.molecular_formula,
                        confidence=0.65,
                        validation_status="warning",
                        issues=[f"Formula mismatch: extracted={extracted_formula}, PubChem={properties.molecular_formula}"]
                    )
        
        # IUPAC name (for reference)
        if properties.iupac_name:
            enrichments["iupac_name"] = EnrichmentResult(
                field_name="iupac_name",
                original_value=None,
                enriched_value=properties.iupac_name,
                confidence=0.95,
                validation_status="enriched",
                additional_data={"note": "IUPAC systematic name from PubChem"}
            )
        
        return enrichments
    
    def _enrich_physical_properties(
        self,
        extractions: Dict[str, Dict[str, Any]],
        properties: ChemicalProperties
    ) -> Dict[str, EnrichmentResult]:
        """Enrich physical properties (molecular weight, etc.)."""
        enrichments = {}
        
        # Molecular weight
        if properties.molecular_weight:
            # Convert to float if it's a string
            try:
                mw_value = float(properties.molecular_weight) if isinstance(properties.molecular_weight, str) else properties.molecular_weight
                enrichments["molecular_weight"] = EnrichmentResult(
                    field_name="molecular_weight",
                    original_value=extractions.get("molecular_weight", {}).get("value"),
                    enriched_value=f"{mw_value:.2f} g/mol",
                    confidence=0.95,
                    validation_status="enriched",
                    additional_data={"numeric_value": mw_value}
                )
            except (ValueError, TypeError) as e:
                logger.warning(f"Failed to convert molecular weight to float: {properties.molecular_weight} - {e}")
                # Store as-is if conversion fails
                enrichments["molecular_weight"] = EnrichmentResult(
                    field_name="molecular_weight",
                    original_value=extractions.get("molecular_weight", {}).get("value"),
                    enriched_value=str(properties.molecular_weight),
                    confidence=0.80,
                    validation_status="enriched",
                    additional_data={"note": "Could not format as numeric"}
                )
        
        # Chemical structure identifiers (for advanced users)
        if properties.canonical_smiles:
            enrichments["canonical_smiles"] = EnrichmentResult(
                field_name="canonical_smiles",
                original_value=None,
                enriched_value=properties.canonical_smiles,
                confidence=0.95,
                validation_status="enriched",
                additional_data={"note": "Canonical SMILES for structure analysis"}
            )
        
        if properties.inchi_key:
            enrichments["inchi_key"] = EnrichmentResult(
                field_name="inchi_key",
                original_value=None,
                enriched_value=properties.inchi_key,
                confidence=0.95,
                validation_status="enriched",
                additional_data={"note": "InChIKey for database lookups"}
            )
        
        return enrichments
    
    def _enrich_safety_info(
        self,
        extractions: Dict[str, Dict[str, Any]],
        properties: ChemicalProperties
    ) -> Dict[str, EnrichmentResult]:
        """Enrich safety information (H/P statements, GHS classification)."""
        enrichments = {}
        
        # H-statements (hazard statements)
        if properties.ghs_hazard_statements:
            extracted_h = extractions.get("h_statements", {}).get("value", "")
            extracted_h_set = set(extracted_h.split(",")) if extracted_h else set()
            pubchem_h_set = set(properties.ghs_hazard_statements)
            
            # Find missing H-statements
            missing_h = pubchem_h_set - extracted_h_set
            
            if missing_h:
                enrichments["h_statements"] = EnrichmentResult(
                    field_name="h_statements",
                    original_value=extracted_h or None,
                    enriched_value=", ".join(sorted(pubchem_h_set)),
                    confidence=0.80,
                    validation_status="enriched",
                    additional_data={
                        "missing_statements": sorted(list(missing_h)),
                        "note": f"Added {len(missing_h)} missing H-statements from PubChem GHS classification"
                    }
                )
        
        # P-statements (precautionary statements)
        if properties.ghs_precautionary_statements:
            extracted_p = extractions.get("p_statements", {}).get("value", "")
            extracted_p_set = set(extracted_p.split(",")) if extracted_p else set()
            pubchem_p_set = set(properties.ghs_precautionary_statements)
            
            missing_p = pubchem_p_set - extracted_p_set
            
            if missing_p:
                enrichments["p_statements"] = EnrichmentResult(
                    field_name="p_statements",
                    original_value=extracted_p or None,
                    enriched_value=", ".join(sorted(pubchem_p_set)),
                    confidence=0.80,
                    validation_status="enriched",
                    additional_data={
                        "missing_statements": sorted(list(missing_p)),
                        "note": f"Added {len(missing_p)} missing P-statements from PubChem GHS classification"
                    }
                )
        
        # GHS pictograms (for reference)
        if properties.ghs_pictograms:
            enrichments["ghs_pictograms"] = EnrichmentResult(
                field_name="ghs_pictograms",
                original_value=None,
                enriched_value=", ".join(properties.ghs_pictograms),
                confidence=0.85,
                validation_status="enriched",
                additional_data={"note": "GHS hazard pictograms from PubChem"}
            )
        
        return enrichments
    
    def _cross_validate_fields(
        self,
        extractions: Dict[str, Dict[str, Any]],
        properties: ChemicalProperties
    ) -> Dict[str, EnrichmentResult]:
        """Cross-validate extracted fields against PubChem data."""
        validations = {}
        
        # Validate product name matches chemical
        product_name = extractions.get("product_name", {}).get("value")
        if product_name and properties.synonyms:
            # Check if extracted name is in synonyms
            name_lower = product_name.lower()
            is_valid = any(name_lower in str(syn).lower() for syn in properties.synonyms)
            
            if not is_valid:
                validations["product_name_validation"] = EnrichmentResult(
                    field_name="product_name",
                    original_value=product_name,
                    enriched_value=None,
                    confidence=0.50,
                    validation_status="warning",
                    issues=[
                        f"Product name '{product_name}' not found in PubChem synonyms",
                        f"Possible alternatives: {', '.join(str(s) for s in properties.synonyms[:5])}"
                    ],
                    additional_data={"pubchem_synonyms": properties.synonyms[:10]}
                )
        
        return validations
    
    def _fill_missing_fields(
        self,
        extractions: Dict[str, Dict[str, Any]],
        properties: ChemicalProperties
    ) -> Dict[str, EnrichmentResult]:
        """Aggressively fill missing fields from PubChem (when enabled)."""
        enrichments = {}
        
        # Add PubChem reference
        if properties.pubchem_url:
            enrichments["pubchem_reference"] = EnrichmentResult(
                field_name="pubchem_reference",
                original_value=None,
                enriched_value=properties.pubchem_url,
                confidence=1.0,
                validation_status="enriched",
                additional_data={"cid": properties.cid}
            )
        
        # Add synonyms for reference
        if properties.synonyms:
            enrichments["chemical_synonyms"] = EnrichmentResult(
                field_name="chemical_synonyms",
                original_value=None,
                enriched_value="; ".join(str(s) for s in properties.synonyms[:10]),
                confidence=0.90,
                validation_status="enriched",
                additional_data={"full_list": properties.synonyms}
            )
        
        return enrichments
    
    def generate_enrichment_report(
        self,
        enrichments: Dict[str, EnrichmentResult]
    ) -> str:
        """
        Generate human-readable enrichment report.
        
        Args:
            enrichments: Dictionary of enrichment results
        
        Returns:
            Formatted report string
        """
        if not enrichments:
            return "No enrichments found."
        
        report_lines = ["=== PubChem Enrichment Report ===\n"]
        
        # Group by validation status
        enriched = [e for e in enrichments.values() if e.validation_status == "enriched"]
        warnings = [e for e in enrichments.values() if e.validation_status == "warning"]
        
        if enriched:
            report_lines.append(f"\n✅ Enriched Fields ({len(enriched)}):")
            for enrich in enriched:
                report_lines.append(f"  • {enrich.field_name}: {enrich.enriched_value}")
                if enrich.additional_data and "note" in enrich.additional_data:
                    report_lines.append(f"    └─ {enrich.additional_data['note']}")
        
        if warnings:
            report_lines.append(f"\n⚠️  Validation Warnings ({len(warnings)}):")
            for warn in warnings:
                report_lines.append(f"  • {warn.field_name}:")
                if warn.issues:
                    for issue in warn.issues:
                        report_lines.append(f"    └─ {issue}")
        
        return "\n".join(report_lines)
