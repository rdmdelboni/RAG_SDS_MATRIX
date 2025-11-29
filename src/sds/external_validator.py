"""
External validation module using PubChem API for chemical data verification.
"""
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Optional, Dict, Any, List
import requests

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
        # Avoid creating a loop in worker threads; only initialize lock if a loop exists
        try:
            asyncio.get_running_loop()
            self._lock = asyncio.Lock()
        except RuntimeError:
            self._lock = None
    
    async def acquire_async(self):
        """Async rate limiting."""
        if self._lock is None:
            self._lock = asyncio.Lock()
        
        async with self._lock:
            elapsed = time.time() - self._last_request
            if elapsed < self.min_interval:
                await asyncio.sleep(self.min_interval - elapsed)
            self._last_request = time.time()
    
    def acquire(self):
        """Sync rate limiting."""
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
    
    def __init__(self, cache_ttl: int = 3600):
        self._last_request_time = 0.0
        self._cache = SimpleCache(ttl_seconds=cache_ttl, max_size=500)
        logger.info(f"PubChem client initialized with {cache_ttl}s cache TTL")
    
    def _rate_limit(self):
        """Enforce rate limiting to respect PubChem usage policy (5 req/s max)."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.RATE_LIMIT_DELAY:
            time.sleep(self.RATE_LIMIT_DELAY - elapsed)
        self._last_request_time = time.time()
    
    def _make_request(self, url: str, timeout: int = 10) -> Optional[Dict[str, Any]]:
        """Make rate-limited request to PubChem API."""
        self._rate_limit()
        try:
            response = requests.get(url, timeout=timeout)
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                logger.debug(f"PubChem: No match found for {url}")
                return None
            elif response.status_code == 503:
                logger.warning("PubChem service temporarily unavailable")
                return None
            else:
                logger.warning(f"PubChem API error {response.status_code}: {url}")
                return None
        except requests.Timeout:
            logger.warning(f"PubChem API timeout: {url}")
            return None
        except requests.RequestException as e:
            logger.warning(f"PubChem API request failed: {e}")
            return None
    
    def search_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Search PubChem by chemical name.
        Returns compound properties if found.
        """
        if not name or len(name) < 3:
            return None
        
        # Check cache first
        cache_key = f"name:{name.lower()}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            logger.debug(f"PubChem cache hit for name: {name}")
            return cached
        
        # URL encode the name
        encoded_name = requests.utils.quote(name)
        url = f"{self.BASE_URL}/compound/name/{encoded_name}/property/MolecularFormula,MolecularWeight,IUPACName,InChI,InChIKey/JSON"
        
        logger.debug(f"PubChem search by name: {name}")
        data = self._make_request(url)
        
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
        
        # First get CID from CAS (via xref search)
        encoded_cas = requests.utils.quote(cas_number)
        cid_url = f"{self.BASE_URL}/compound/name/{encoded_cas}/cids/JSON"
        
        logger.debug(f"PubChem search by CAS: {cas_number}")
        cid_data = self._make_request(cid_url)
        
        if not cid_data or "IdentifierList" not in cid_data:
            return None
        
        cids = cid_data["IdentifierList"].get("CID", [])
        if not cids:
            return None
        
        # Get properties for first CID
        cid = cids[0]
        props_url = f"{self.BASE_URL}/compound/cid/{cid}/property/MolecularFormula,MolecularWeight,IUPACName,InChI,InChIKey/JSON"
        
        data = self._make_request(props_url)
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
        self._rate_limiter = RateLimiter(max_per_second=5)
    
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
                self._rate_limiter.acquire()
                
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
