"""
External validation module using PubChem API for chemical data verification.
"""
import time
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Optional, Dict, Any, List
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import re

from ..utils.logger import get_logger
from ..utils.cache import SimpleCache

logger = get_logger(__name__)


@dataclass
class ValidationResult:
    """Result from external validation."""
    is_valid: bool
    confidence_boost: float  # Add to field confidence if valid
    source: str
    matched_data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class RateLimiter:
    """Thread-safe rate limiter for parallel requests."""
    
    def __init__(self, max_per_second: int = 5):
        self.max_per_second = max_per_second
        self.min_interval = 1.0 / max_per_second
        self._last_request = 0.0
        self._lock = threading.Lock()
    
    async def acquire_async(self):
        """Async rate limiting."""
        # Using threading.Lock keeps behaviour consistent between sync/async callers
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self.acquire)
    
    def acquire(self):
        """Sync rate limiting."""
        with self._lock:
            elapsed = time.time() - self._last_request
            if elapsed < self.min_interval:
                time.sleep(self.min_interval - elapsed)
            self._last_request = time.time()


@dataclass
class BatchValidationItem:
    """Item for batch validation."""
    index: int
    product_name: Optional[str] = None
    cas_number: Optional[str] = None
    formula: Optional[str] = None


@dataclass
class BatchValidationResult:
    """Result from batch validation."""
    index: int
    product_name_result: Optional[ValidationResult] = None
    cas_number_result: Optional[ValidationResult] = None
    formula_result: Optional[ValidationResult] = None
    error: Optional[str] = None


class PubChemClient:
    """Client for PubChem REST API validation."""
    
    BASE_URL = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
    MAX_REQUESTS_PER_SECOND = 5
    RATE_LIMIT_DELAY = 0.21  # Slightly over 1/5 second to stay under limit
    # Minimal offline fixtures so validation works without network access
    OFFLINE_FIXTURES = {
        "sulfuric acid": {
            "CID": 1118,
            "MolecularFormula": "H2SO4",
            "MolecularWeight": 98.079,
            "IUPACName": "sulfuric acid",
            "InChI": "InChI=1S/H2O4S/c1-5(2,3)4/h(H2,1,2,3,4)/p-2",
            "InChIKey": "QAOWNCQODCNURD-UHFFFAOYSA-N",
            "CAS": "7664-93-9",
        },
        "sodium chloride": {
            "CID": 5234,
            "MolecularFormula": "ClNa",
            "MolecularWeight": 58.44,
            "IUPACName": "sodium chloride",
            "InChI": "InChI=1S/ClH.Na/h1H;/q;+1/p-1",
            "InChIKey": "FAPWRFPIFSIZLT-UHFFFAOYSA-M",
            "CAS": "7647-14-5",
        },
        "water": {
            "CID": 962,
            "MolecularFormula": "H2O",
            "MolecularWeight": 18.015,
            "IUPACName": "water",
            "InChI": "InChI=1S/H2O/h1H2",
            "InChIKey": "XLYOFNOQVPJJNP-UHFFFAOYSA-N",
            "CAS": "7732-18-5",
        },
        "ethanol": {
            "CID": 702,
            "MolecularFormula": "C2H6O",
            "MolecularWeight": 46.068,
            "IUPACName": "ethanol",
            "InChI": "InChI=1S/C2H6O/c1-2-3/h3H,2H2,1H3",
            "InChIKey": "LFQSCWFLJHTTHZ-UHFFFAOYSA-N",
            "CAS": "64-17-5",
        },
        "methanol": {
            "CID": 887,
            "MolecularFormula": "CH4O",
            "MolecularWeight": 32.042,
            "IUPACName": "methanol",
            "InChI": "InChI=1S/CH4O/c1-2/h2H,1H3",
            "InChIKey": "OKKJLVBELUTLKV-UHFFFAOYSA-N",
            "CAS": "67-56-1",
        },
        "acetone": {
            "CID": 180,
            "MolecularFormula": "C3H6O",
            "MolecularWeight": 58.08,
            "IUPACName": "propan-2-one",
            "InChI": "InChI=1S/C3H6O/c1-3(2)4/h1-2H3",
            "InChIKey": "CSCPPACGZOOCGX-UHFFFAOYSA-N",
            "CAS": "67-64-1",
        },
        "hydrochloric acid": {
            "CID": 313,
            "MolecularFormula": "ClH",
            "MolecularWeight": 36.46,
            "IUPACName": "hydrochloric acid",
            "InChI": "InChI=1S/ClH/h1H",
            "InChIKey": "VEXZGXHMUGYJMC-UHFFFAOYSA-N",
            "CAS": "7647-01-0",
        },
    }
    OFFLINE_HAZARDS = {
        1118: ["H314", "H290"],
        5234: ["H319"],
        962: [],
        702: ["H225", "H319"],
        887: ["H225", "H301"],
        180: ["H225", "H319"],
        313: ["H290", "H314"],
    }
    
    def __init__(self, cache_ttl: int = 3600):
        self._last_request_time = 0.0
        self._cache = SimpleCache(ttl_seconds=cache_ttl, max_size=500)
        self._lock = threading.Lock()
        self._offline_mode = False
        self._fixtures_by_cas = {
            data["CAS"]: {**data} for data in self.OFFLINE_FIXTURES.values()
        }
        
        # Create persistent session with connection pooling for faster requests
        self._session = requests.Session()
        adapter = HTTPAdapter(
            pool_connections=3,      # Number of connection pools to cache
            pool_maxsize=3,           # Maximum number of connections per pool
            max_retries=Retry(
                total=3,
                backoff_factor=0.5,
                status_forcelist=[500, 502, 503, 504]
            )
        )
        self._session.mount('https://', adapter)
        self._session.mount('http://', adapter)
        
        logger.info(f"PubChem client initialized with {cache_ttl}s cache TTL and connection pooling")

    
    def _rate_limit(self):
        """Enforce rate limiting to respect PubChem usage policy (5 req/s max)."""
        with self._lock:
            elapsed = time.time() - self._last_request_time
            if elapsed < self.RATE_LIMIT_DELAY:
                time.sleep(self.RATE_LIMIT_DELAY - elapsed)
            self._last_request_time = time.time()
    
    def _make_request(
        self,
        url: str,
        timeout: int = 30,
        apply_rate_limit: bool = True,
        max_retries: int = 3
    ) -> Optional[Dict[str, Any]]:
        """Make rate-limited request to PubChem API with retry logic.
        
        Uses persistent session with connection pooling for faster repeated requests.
        """
        if self._offline_mode:
            return None

        for attempt in range(max_retries):
            if apply_rate_limit:
                self._rate_limit()

            try:
                # Use session instead of requests.get for connection pooling
                response = self._session.get(url, timeout=timeout)
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 404:
                    logger.debug(f"PubChem: No match found for {url}")
                    return None
                elif response.status_code == 503:
                    if attempt < max_retries - 1:
                        wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                        logger.warning(f"PubChem service temporarily unavailable, retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})")
                        time.sleep(wait_time)
                        continue
                    else:
                        logger.warning("PubChem service temporarily unavailable after all retries")
                        return None
                else:
                    logger.warning(f"PubChem API error {response.status_code}: {url}")
                    return None
            except requests.Timeout as e:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    logger.warning(f"PubChem API timeout (attempt {attempt + 1}/{max_retries}), retrying in {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                else:
                    logger.warning(f"PubChem API request timed out after {max_retries} attempts: {e}")
                    return None
            except requests.RequestException as e:
                logger.warning(f"PubChem API request failed: {e}")
                # Don't set offline mode immediately, could be transient
                if attempt == max_retries - 1:
                    # Only set offline after all retries exhausted
                    self._offline_mode = True
                return None
        
        return None

    def _get_offline_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Return fixture data if available for the given name."""
        return self.OFFLINE_FIXTURES.get(name.lower())

    def _get_offline_by_cas(self, cas_number: str) -> Optional[Dict[str, Any]]:
        """Return fixture data if available for the given CAS."""
        return self._fixtures_by_cas.get(cas_number)
    
    def search_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Search PubChem by chemical name.
        Returns compound properties if found.
        """
        if not name or len(name) < 3:
            return None

        # Sanitize to avoid multi-line/metadata inputs (e.g., product codes)
        cleaned = re.sub(r"[\r\n\t]+", " ", name).strip()
        cleaned = re.sub(r"\s+", " ", cleaned)

        # Drop trailing product code labels if present
        cleaned = re.split(r"(?i)codigo do produto:?", cleaned)[0].strip()

        # Skip obviously invalid names
        if not cleaned or len(cleaned) < 3 or " " not in cleaned and cleaned.isdigit():
            logger.debug(f"PubChem search skipped due to invalid name input: {name!r}")
            return None
        
        # Check cache first
        cache_key = f"name:{cleaned.lower()}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            logger.debug(f"PubChem cache hit for name: {cleaned}")
            return cached

        # Apply rate limit once per cache miss
        self._rate_limit()

        # Offline fixtures avoid network dependence for common chemicals
        fixture = self._get_offline_by_name(cleaned)
        if fixture:
            self._cache.set(cache_key, fixture)
            return fixture
        
        # URL encode the name
        encoded_name = requests.utils.quote(cleaned)
        url = f"{self.BASE_URL}/compound/name/{encoded_name}/property/MolecularFormula,MolecularWeight,IUPACName,InChI,InChIKey/JSON"
        
        logger.debug(f"PubChem search by name: {cleaned}")
        data = self._make_request(url, apply_rate_limit=False)
        
        if data and "PropertyTable" in data and "Properties" in data["PropertyTable"]:
            props = data["PropertyTable"]["Properties"]
            if props:
                result = props[0]  # Return first match
                self._cache.set(cache_key, result)
                return result
        
        # Cache negative result too (avoid repeated failed lookups)
        self._cache.set(cache_key, None)
        return None
    
    def search_by_cas(self, cas_number: str) -> Optional[Dict[str, Any]]:
        """
        Search PubChem by CAS number.
        CAS numbers are stored as xrefs in PubChem.
        """
        if not cas_number:
            return None
        
        # Check cache first
        cache_key = f"cas:{cas_number}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            logger.debug(f"PubChem cache hit for CAS: {cas_number}")
            return cached

        # Apply rate limit once for the lookup
        self._rate_limit()

        # Try offline fixture first
        fixture = self._get_offline_by_cas(cas_number)
        if fixture:
            self._cache.set(cache_key, fixture)
            return fixture
        
        # First get CID from CAS (via xref search)
        encoded_cas = requests.utils.quote(cas_number)
        cid_url = f"{self.BASE_URL}/compound/name/{encoded_cas}/cids/JSON"
        
        logger.debug(f"PubChem search by CAS: {cas_number}")
        cid_data = self._make_request(cid_url, apply_rate_limit=False)
        
        if not cid_data or "IdentifierList" not in cid_data:
            return None
        
        cids = cid_data["IdentifierList"].get("CID", [])
        if not cids:
            return None

        # Respect rate limit between chained requests
        self._rate_limit()
        
        # Get properties for first CID
        cid = cids[0]
        props_url = f"{self.BASE_URL}/compound/cid/{cid}/property/MolecularFormula,MolecularWeight,IUPACName,InChI,InChIKey/JSON"
        
        data = self._make_request(props_url, apply_rate_limit=False)
        if data and "PropertyTable" in data and "Properties" in data["PropertyTable"]:
            props = data["PropertyTable"]["Properties"]
            if props:
                result = props[0]
                self._cache.set(cache_key, result)
                return result
        
        self._cache.set(cache_key, None)
        return None
    
    def get_hazard_info(self, cid: int) -> Optional[Dict[str, Any]]:
        """
        Get GHS hazard classification from PubChem.
        Returns classification data if available.
        """
        # Offline fixtures for common CIDs
        offline_codes = self.OFFLINE_HAZARDS.get(cid)
        if offline_codes is not None:
            node = {
                "Information": [{"Name": code} for code in offline_codes]
            }
            return {
                "Hierarchies": [{
                    "SourceName": "GHS Classification",
                    "Node": [node]
                }]
            }

        url = f"{self.BASE_URL}/compound/cid/{cid}/classification/JSON"
        
        logger.debug(f"PubChem get hazard info for CID: {cid}")
        data = self._make_request(url)
        
        if data and "Hierarchies" in data:
            # Filter for GHS classification
            for hierarchy in data["Hierarchies"]:
                if "GHS" in hierarchy.get("SourceName", ""):
                    return hierarchy
        
        return None


class ExternalValidator:
    """Validates extracted SDS fields against external databases."""
    
    def __init__(self, cache_ttl: int = 3600):
        self.pubchem = PubChemClient(cache_ttl=cache_ttl)
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache performance statistics."""
        return self.pubchem._cache.get_stats()
    
    def clear_cache(self) -> None:
        """Clear the PubChem response cache."""
        self.pubchem._cache.clear()
    
    def validate_product_name(self, product_name: str, cas_number: Optional[str] = None) -> ValidationResult:
        """
        Validate product name against PubChem database.
        
        Args:
            product_name: Chemical product name to validate
            cas_number: Optional CAS number for cross-validation
        
        Returns:
            ValidationResult with confidence boost if validated
        """
        if not product_name:
            return ValidationResult(
                is_valid=False,
                confidence_boost=0.0,
                source="pubchem",
                error="Empty product name"
            )
        
        # Try search by name
        name_match = self.pubchem.search_by_name(product_name)
        
        if name_match:
            confidence_boost = 0.10  # Base boost for name match
            
            # Cross-validate with CAS if provided
            if cas_number:
                cas_match = self.pubchem.search_by_cas(cas_number)
                if cas_match and cas_match.get("CID") == name_match.get("CID"):
                    confidence_boost = 0.15  # Higher boost for consistent CAS+name
            
            return ValidationResult(
                is_valid=True,
                confidence_boost=confidence_boost,
                source="pubchem",
                matched_data=name_match
            )
        
        # If name fails but CAS provided, try CAS only
        if cas_number:
            cas_match = self.pubchem.search_by_cas(cas_number)
            if cas_match:
                return ValidationResult(
                    is_valid=True,
                    confidence_boost=0.08,  # Lower boost (name mismatch)
                    source="pubchem",
                    matched_data=cas_match
                )
        
        return ValidationResult(
            is_valid=False,
            confidence_boost=0.0,
            source="pubchem",
            error="No match found in PubChem"
        )
    
    def validate_cas_number(self, cas_number: str) -> ValidationResult:
        """
        Validate CAS number format and existence in PubChem.
        
        Args:
            cas_number: CAS registry number to validate
        
        Returns:
            ValidationResult with confidence boost if validated
        """
        if not cas_number:
            return ValidationResult(
                is_valid=False,
                confidence_boost=0.0,
                source="pubchem",
                error="Empty CAS number"
            )
        
        # Basic format check: XXX-XX-X or longer
        parts = cas_number.split("-")
        if len(parts) != 3:
            return ValidationResult(
                is_valid=False,
                confidence_boost=0.0,
                source="format_check",
                error="Invalid CAS format (expected XXX-XX-X)"
            )
        
        # Search in PubChem
        match = self.pubchem.search_by_cas(cas_number)
        
        if match:
            return ValidationResult(
                is_valid=True,
                confidence_boost=0.12,
                source="pubchem",
                matched_data=match
            )
        
        return ValidationResult(
            is_valid=False,
            confidence_boost=0.0,
            source="pubchem",
            error="CAS number not found in PubChem"
        )
    
    def validate_chemical_formula(self, formula: str, product_name: Optional[str] = None) -> ValidationResult:
        """
        Validate chemical formula against PubChem data.
        
        Args:
            formula: Chemical formula (e.g., H2SO4)
            product_name: Optional product name for cross-validation
        
        Returns:
            ValidationResult with confidence boost if validated
        """
        if not formula:
            return ValidationResult(
                is_valid=False,
                confidence_boost=0.0,
                source="pubchem",
                error="Empty formula"
            )
        
        # If product name provided, check formula consistency
        if product_name:
            name_match = self.pubchem.search_by_name(product_name)
            if name_match:
                pubchem_formula = name_match.get("MolecularFormula", "")
                if pubchem_formula.replace(" ", "") == formula.replace(" ", ""):
                    return ValidationResult(
                        is_valid=True,
                        confidence_boost=0.10,
                        source="pubchem",
                        matched_data=name_match
                    )
                else:
                    return ValidationResult(
                        is_valid=False,
                        confidence_boost=0.0,
                        source="pubchem",
                        error=f"Formula mismatch: got {formula}, PubChem has {pubchem_formula}"
                    )
        
        # Search by formula alone (less reliable)
        encoded_formula = requests.utils.quote(formula)
        url = f"{self.pubchem.BASE_URL}/compound/fastformula/{encoded_formula}/cids/JSON?MaxRecords=1"
        
        data = self.pubchem._make_request(url)
        if data and "IdentifierList" in data and data["IdentifierList"].get("CID"):
            return ValidationResult(
                is_valid=True,
                confidence_boost=0.05,  # Low boost (formula alone is ambiguous)
                source="pubchem"
            )
        
        return ValidationResult(
            is_valid=False,
            confidence_boost=0.0,
            source="pubchem",
            error="Formula not found in PubChem"
        )
    
    def enrich_hazard_classification(self, product_name: str) -> Optional[List[str]]:
        """
        Get GHS hazard classifications from PubChem for enrichment.
        
        Args:
            product_name: Chemical name to look up
        
        Returns:
            List of GHS hazard codes if found, None otherwise
        """
        name_match = self.pubchem.search_by_name(product_name)
        if not name_match:
            return None
        
        cid = name_match.get("CID")
        if not cid:
            return None
        
        hazard_info = self.pubchem.get_hazard_info(cid)
        if not hazard_info:
            return None
        
        # Extract hazard codes from classification tree
        hazard_codes = []
        
        def extract_codes(node: Dict[str, Any]):
            """Recursively extract GHS codes from tree."""
            if "Information" in node:
                for info in node["Information"]:
                    name = info.get("Name", "")
                    if name.startswith("H") and name[1:].isdigit():
                        hazard_codes.append(name)
            
            if "Node" in node:
                for child in node["Node"]:
                    extract_codes(child)
        
        extract_codes(hazard_info)
        
        return hazard_codes if hazard_codes else None
    
    def validate_batch(
        self,
        items: List[BatchValidationItem],
        max_workers: int = 5
    ) -> List[BatchValidationResult]:
        """
        Validate multiple chemicals in parallel with rate limiting.
        
        Args:
            items: List of chemicals to validate
            max_workers: Maximum parallel workers (default 5 to match rate limit)
        
        Returns:
            List of validation results in the same order as input
        """
        if not items:
            return []
        
        logger.info(f"Starting batch validation of {len(items)} items with {max_workers} workers")
        start_time = time.time()
        
        results = {}
        
        def validate_item(item: BatchValidationItem) -> BatchValidationResult:
            """Validate a single item with rate limiting."""
            try:
                result = BatchValidationResult(index=item.index)
                
                # Validate product name
                if item.product_name:
                    result.product_name_result = self.validate_product_name(
                        item.product_name,
                        item.cas_number
                    )
                
                # Validate CAS number
                if item.cas_number:
                    result.cas_number_result = self.validate_cas_number(item.cas_number)
                
                # Validate formula
                if item.formula:
                    result.formula_result = self.validate_chemical_formula(
                        item.formula,
                        item.product_name
                    )
                
                return result
                
            except Exception as e:
                logger.error(f"Error validating item {item.index}: {e}")
                return BatchValidationResult(
                    index=item.index,
                    error=str(e)
                )
        
        # Use ThreadPoolExecutor for parallel validation
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_item = {
                executor.submit(validate_item, item): item for item in items
            }
            
            for future in as_completed(future_to_item):
                result = future.result()
                results[result.index] = result
        
        # Sort results by index to maintain input order
        sorted_results = [results[i] for i in sorted(results.keys())]
        
        elapsed = time.time() - start_time
        logger.info(
            f"Batch validation completed in {elapsed:.2f}s "
            f"({len(items)/elapsed:.1f} items/sec)"
        )
        
        return sorted_results
    
    def validate_batch_simple(
        self,
        product_names: List[str],
        cas_numbers: Optional[List[str]] = None
    ) -> List[ValidationResult]:
        """
        Simplified batch validation for product names with optional CAS numbers.
        
        Args:
            product_names: List of product names to validate
            cas_numbers: Optional list of CAS numbers (same length as product_names)
        
        Returns:
            List of validation results for product names
        """
        if cas_numbers and len(cas_numbers) != len(product_names):
            raise ValueError("cas_numbers must have same length as product_names")
        
        items = []
        for i, name in enumerate(product_names):
            cas = cas_numbers[i] if cas_numbers else None
            items.append(BatchValidationItem(
                index=i,
                product_name=name,
                cas_number=cas
            ))
        
        batch_results = self.validate_batch(items)
        
        # Extract just the product name results
        return [
            result.product_name_result or ValidationResult(
                is_valid=False,
                confidence_boost=0.0,
                source="batch",
                error=result.error or "No result"
            )
            for result in batch_results
        ]
