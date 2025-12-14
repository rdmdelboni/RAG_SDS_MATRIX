"""
Chemical structure recognition from images in SDS documents.

Extracts chemical structures from diagrams and converts to machine-readable formats
(SMILES, InChI) with validation against PubChem.
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

from PIL import Image
import numpy as np

from ..utils.logger import get_logger
from ..utils.cache import SimpleCache

logger = get_logger(__name__)


@dataclass
class StructureRecognitionResult:
    """Result from structure recognition."""
    smiles: Optional[str] = None
    inchi: Optional[str] = None
    inchi_key: Optional[str] = None
    confidence: float = 0.0
    method: str = "unknown"
    pubchem_cid: Optional[int] = None
    matched_name: Optional[str] = None
    error: Optional[str] = None


class StructureImageExtractor:
    """Extract chemical structure diagrams from PDF pages."""
    
    def __init__(self):
        """Initialize image extractor."""
        logger.info("Structure image extractor initialized")
    
    def extract_images_from_pdf(self, pdf_path: Path) -> List[Image.Image]:
        """
        Extract images from PDF that might contain chemical structures.
        
        Args:
            pdf_path: Path to PDF file
        
        Returns:
            List of PIL Image objects
        """
        images = []
        
        try:
            import pdfplumber
            
            with pdfplumber.open(pdf_path) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    # Extract images from page
                    page_images = page.images
                    
                    for img_idx, img_info in enumerate(page_images):
                        try:
                            # Get image object
                            img = page.within_bbox(
                                (img_info['x0'], img_info['top'],
                                 img_info['x1'], img_info['bottom'])
                            ).to_image()

                            # Convert to PIL Image
                            pil_img = img.original

                            # Filter by size (chemical structures usually > 50x50 pixels)
                            if pil_img.width > 50 and pil_img.height > 50:
                                images.append(pil_img)
                                logger.debug(
                                    f"Extracted image from page {page_num}, "
                                    f"size: {pil_img.width}x{pil_img.height}"
                                )

                        except Exception as e:
                            logger.debug(f"Failed to extract image {img_idx} from page {page_num}: {e}")
                            continue
        
        except Exception as e:
            logger.error(f"Failed to extract images from PDF: {e}")
        
        return images
    
    def is_likely_structure(self, image: Image.Image) -> Tuple[bool, float]:
        """
        Determine if image is likely a chemical structure diagram.
        
        Args:
            image: PIL Image object
        
        Returns:
            Tuple of (is_structure, confidence)
        """
        try:
            # Convert to grayscale
            gray = image.convert('L')
            img_array = np.array(gray)
            
            # Basic heuristics for chemical structures:
            # 1. Moderate complexity (not too simple, not too complex)
            # 2. High contrast (black lines on white background)
            # 3. Reasonable aspect ratio (not too elongated)
            
            # Check aspect ratio
            width, height = image.size
            aspect_ratio = width / height
            if aspect_ratio < 0.3 or aspect_ratio > 3.0:
                return False, 0.1  # Too elongated
            
            # Check contrast
            std_dev = np.std(img_array)
            if std_dev < 30:  # Too uniform
                return False, 0.2
            
            # Check if mostly white (structures on white background)
            mean_brightness = np.mean(img_array)
            if mean_brightness < 150:  # Too dark
                return False, 0.3
            
            # Check for edges (structures have many lines)
            edges = np.abs(np.diff(img_array.astype(float), axis=0)).sum()
            edge_density = edges / (width * height)
            
            if edge_density < 5:  # Too few edges
                return False, 0.4
            
            # Confidence based on edge density
            confidence = min(1.0, edge_density / 20)
            
            return True, confidence
        
        except Exception as e:
            logger.error(f"Error analyzing image: {e}")
            return False, 0.0


class StructureRecognizer:
    """Recognize chemical structures from images."""
    
    def __init__(self, cache_ttl: int = 3600):
        """Initialize recognizer with caching."""
        self.cache = SimpleCache(ttl_seconds=cache_ttl, max_size=100)
        self.image_extractor = StructureImageExtractor()
        logger.info("Structure recognizer initialized")
    
    def recognize_from_image(
        self,
        image: Image.Image,
        use_ocr: bool = True,
    ) -> StructureRecognitionResult:
        """
        Recognize chemical structure from image.
        
        Args:
            image: PIL Image containing chemical structure
            use_ocr: Whether to use OCR for text recognition
        
        Returns:
            StructureRecognitionResult with SMILES/InChI if found
        """
        # Check cache
        img_hash = self._hash_image(image)
        cached = self.cache.get(img_hash)
        if cached:
            logger.debug("Structure recognition cache hit")
            return cached
        
        result = StructureRecognitionResult()
        
        # Try different methods in order of preference
        
        # Method 1: OCR for chemical names (then lookup)
        if use_ocr:
            ocr_result = self._recognize_via_ocr(image)
            if ocr_result.smiles:
                result = ocr_result
                result.method = "ocr_lookup"
                self.cache.set(img_hash, result)
                return result
        
        # Method 2: DECIMER Deep Learning Model (if available)
        decimer_result = self._recognize_via_decimer(image)
        if decimer_result.smiles:
            result = decimer_result
            result.method = "decimer"
            self.cache.set(img_hash, result)
            return result

        # Method 3: OSRA (if available)
        osra_result = self._recognize_via_osra(image)
        if osra_result.smiles:
            result = osra_result
            result.method = "osra"
            self.cache.set(img_hash, result)
            return result
        
        # Method 4: Pattern matching for simple structures
        pattern_result = self._recognize_via_patterns(image)
        if pattern_result.smiles:
            result = pattern_result
            result.method = "pattern_matching"
            self.cache.set(img_hash, result)
            return result
        
        # No recognition method succeeded
        result.error = "No recognition method succeeded"
        result.confidence = 0.0
        self.cache.set(img_hash, result)
        
        return result
    
    def _hash_image(self, image: Image.Image) -> str:
        """Generate hash of image for caching."""
        import hashlib
        
        # Resize to small size for consistent hashing
        small = image.resize((32, 32))
        img_bytes = small.tobytes()
        
        return hashlib.md5(img_bytes).hexdigest()
    
    def _recognize_via_ocr(self, image: Image.Image) -> StructureRecognitionResult:
        """Recognize structure by OCR text extraction and lookup."""
        result = StructureRecognitionResult()
        
        try:
            import pytesseract
            
            # Extract text from image
            text = pytesseract.image_to_string(image)
            
            # Look for chemical names or formulas
            # Common patterns: compound names, formulas like H2SO4, C6H12O6, etc.
            import re
            
            # Look for chemical formulas
            formula_pattern = r'[A-Z][a-z]?\d*(?:[A-Z][a-z]?\d*)*'
            formulas = re.findall(formula_pattern, text)
            
            # Try to lookup each candidate
            for candidate in formulas[:3]:  # Try top 3 candidates
                if len(candidate) > 2:  # At least 3 characters
                    lookup_result = self._lookup_in_pubchem(candidate)
                    if lookup_result.smiles:
                        return lookup_result
            
        except ImportError:
            logger.debug("pytesseract not available for OCR")
        except Exception as e:
            logger.debug(f"OCR recognition failed: {e}")
        
        return result
    
    def _recognize_via_decimer(self, image: Image.Image) -> StructureRecognitionResult:
        """Recognize structure using DECIMER (Deep Learning for Chemical Image Recognition)."""
        result = StructureRecognitionResult()
        
        try:
            from DECIMER import predict_SMILES
            
            # Save image to temporary file as DECIMER might need path or work with PIL
            # The library usually takes a path string.
            import tempfile
            import os
            
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp_img:
                image.save(temp_img.name)
                temp_path = temp_img.name
            
            try:
                # Predict SMILES
                smiles = predict_SMILES(temp_path)

                if smiles:
                    result.smiles = smiles
                    result.confidence = 0.9  # DECIMER usually has high confidence if it returns something

                    # Generate InChI if possible
                    try:
                        from rdkit import Chem
                        mol = Chem.MolFromSmiles(smiles)
                        if mol:
                            result.inchi = Chem.MolToInchi(mol)
                            result.inchi_key = Chem.MolToInchiKey(mol)
                    except:
                        pass
            finally:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)

        except ImportError:
            logger.debug("DECIMER not available")
        except Exception as e:
            logger.debug(f"DECIMER recognition failed: {e}")

        return result

    def _recognize_via_osra(self, image: Image.Image) -> StructureRecognitionResult:
        """Recognize structure using OSRA (Optical Structure Recognition Application)."""
        result = StructureRecognitionResult()
        
        try:
            import subprocess
            import tempfile
            import os
            import shutil

            # Check if OSRA is installed
            if not shutil.which("osra"):
                logger.debug("OSRA binary not found in path")
                return result

            # Save image to temporary file
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp_img:
                image.save(temp_img.name)
                temp_path = temp_img.name

            try:
                # Run OSRA
                # osra -f smi <image_file>
                process = subprocess.Popen(
                    ["osra", "-f", "smi", temp_path],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                stdout, stderr = process.communicate()

                if process.returncode == 0:
                    output = stdout.decode("utf-8").strip()
                    # OSRA output might contain the filename and then the SMILES, or just SMILES
                    # Typically: "SMILES_STRING" or "filename: SMILES_STRING"

                    parts = output.split()
                    if parts:
                        smiles = parts[-1] # Assume last part is SMILES
                        if len(smiles) > 1:
                            result.smiles = smiles
                            result.confidence = 0.8

                            # Generate InChI
                            try:
                                from rdkit import Chem
                                mol = Chem.MolFromSmiles(smiles)
                                if mol:
                                    result.inchi = Chem.MolToInchi(mol)
                                    result.inchi_key = Chem.MolToInchiKey(mol)
                            except:
                                pass
            finally:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)

        except Exception as e:
            logger.debug(f"OSRA recognition failed: {e}")

        return result
    
    def _recognize_via_patterns(self, image: Image.Image) -> StructureRecognitionResult:
        """Recognize simple structures via pattern matching."""
        result = StructureRecognitionResult()
        
        try:
            import cv2
            
            # Convert PIL Image to numpy array (OpenCV format)
            # PIL is RGB, OpenCV is BGR
            img_array = np.array(image)
            
            # Handle RGBA
            if img_array.shape[-1] == 4:
                img_array = cv2.cvtColor(img_array, cv2.COLOR_RGBA2BGR)
            # Handle RGB
            elif len(img_array.shape) == 3:
                img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
            # Handle Grayscale
            elif len(img_array.shape) == 2:
                img_array = cv2.cvtColor(img_array, cv2.COLOR_GRAY2BGR)

            # Convert to grayscale for processing
            gray = cv2.cvtColor(img_array, cv2.COLOR_BGR2GRAY)

            # Blur to reduce noise
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)

            # Threshold to binary (inverse, assuming black structures on white background)
            # Using Otsu's binarization
            _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

            # Find contours
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            # Sort contours by area (largest first)
            contours = sorted(contours, key=cv2.contourArea, reverse=True)

            # Check for simple shapes
            for contour in contours:
                # Filter small noise
                area = cv2.contourArea(contour)
                if area < 100:  # Minimum area threshold
                    continue

                # Approximate the contour
                perimeter = cv2.arcLength(contour, True)
                epsilon = 0.04 * perimeter
                approx = cv2.approxPolyDP(contour, epsilon, True)

                # Number of vertices
                vertices = len(approx)

                # Check convexity
                if not cv2.isContourConvex(approx):
                    continue

                # Pattern Matching Heuristics

                # Hexagon (6 vertices) -> Potential Benzene Ring
                if vertices == 6:
                    # Check aspect ratio to ensure it's roughly regular
                    x, y, w, h = cv2.boundingRect(approx)
                    aspect_ratio = float(w) / h

                    if 0.8 <= aspect_ratio <= 1.2:
                        # Likely a benzene ring or cyclohexane
                        # For simplicity in "simple pattern matching", we assume aromatic benzene
                        # as it's a very common solvent/chemical.
                        result.smiles = "c1ccccc1"
                        result.matched_name = "Benzene (Pattern)"
                        result.confidence = 0.6
                        result.method = "pattern_matching"

                        # Generate InChI
                        try:
                            from rdkit import Chem
                            mol = Chem.MolFromSmiles(result.smiles)
                            if mol:
                                result.inchi = Chem.MolToInchi(mol)
                                result.inchi_key = Chem.MolToInchiKey(mol)
                        except Exception as e:
                            logger.debug(f"RDKit conversion failed in pattern recognition: {e}")

                        return result

                # Pentagon (5 vertices) -> Potential Cyclopentane/Furan
                elif vertices == 5:
                    x, y, w, h = cv2.boundingRect(approx)
                    aspect_ratio = float(w) / h

                    if 0.8 <= aspect_ratio <= 1.2:
                        result.smiles = "C1CCCC1"  # Cyclopentane
                        result.matched_name = "Cyclopentane (Pattern)"
                        result.confidence = 0.5
                        result.method = "pattern_matching"

                        try:
                            from rdkit import Chem
                            mol = Chem.MolFromSmiles(result.smiles)
                            if mol:
                                result.inchi = Chem.MolToInchi(mol)
                                result.inchi_key = Chem.MolToInchiKey(mol)
                        except Exception as e:
                            logger.debug(f"RDKit conversion failed in pattern recognition: {e}")

                        return result

            logger.debug(f"No recognizable patterns found in {len(contours)} contours")

        except ImportError as e:
            if 'cv2' in str(e):
                logger.debug("OpenCV (cv2) not available for pattern recognition")
            else:
                logger.debug(f"Import error in pattern recognition: {e}")
        except Exception as e:
            logger.debug(f"Pattern recognition failed: {e}")
        
        return result
    
    def _lookup_in_pubchem(self, query: str) -> StructureRecognitionResult:
        """Lookup structure in PubChem by name or formula."""
        result = StructureRecognitionResult()
        
        try:
            import requests
            
            # Search PubChem by name/formula (URL-encode to handle special characters)
            encoded_query = requests.utils.quote(query)
            url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{encoded_query}/property/CanonicalSMILES,InChI,InChIKey/JSON"
            
            response = requests.get(url, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                props = data.get("PropertyTable", {}).get("Properties", [])
                
                if props:
                    prop = props[0]
                    result.smiles = prop.get("CanonicalSMILES")
                    result.inchi = prop.get("InChI")
                    result.inchi_key = prop.get("InChIKey")
                    result.pubchem_cid = prop.get("CID")
                    result.matched_name = query
                    result.confidence = 0.85
                    
                    logger.debug(f"Found structure in PubChem: {query}")
        
        except Exception as e:
            logger.debug(f"PubChem lookup failed: {e}")
        
        return result
    
    def validate_structure(
        self,
        smiles: str,
        product_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Validate recognized structure against known data.
        
        Args:
            smiles: SMILES string to validate
            product_name: Optional product name for cross-validation
        
        Returns:
            Validation results
        """
        validation = {
            "is_valid": False,
            "confidence": 0.0,
            "matches_name": False,
            "canonical_smiles": None,
        }
        
        try:
            from rdkit import Chem
            
            # Parse SMILES
            mol = Chem.MolFromSmiles(smiles)
            
            if mol is None:
                validation["error"] = "Invalid SMILES"
                return validation
            
            # Valid molecule
            validation["is_valid"] = True
            validation["confidence"] = 0.7
            validation["canonical_smiles"] = Chem.MolToSmiles(mol)
            
            # Cross-validate with product name if provided
            if product_name:
                lookup = self._lookup_in_pubchem(product_name)
                if lookup.smiles:
                    # Compare structures
                    mol_lookup = Chem.MolFromSmiles(lookup.smiles)
                    if mol_lookup and Chem.MolToInchi(mol) == Chem.MolToInchi(mol_lookup):
                        validation["matches_name"] = True
                        validation["confidence"] = 0.95
        
        except ImportError:
            logger.debug("RDKit not available for structure validation")
            validation["error"] = "RDKit not available"
        except Exception as e:
            logger.error(f"Structure validation error: {e}")
            validation["error"] = str(e)
        
        return validation
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return self.cache.get_stats()
    
    def clear_cache(self):
        """Clear recognition cache."""
        self.cache.clear()


class StructureExtractor:
    """Main class for extracting structures from SDS documents."""
    
    def __init__(self):
        """Initialize structure extractor."""
        self.recognizer = StructureRecognizer()
        self.image_extractor = StructureImageExtractor()
        logger.info("Structure extractor initialized")
    
    def extract_from_pdf(
        self,
        pdf_path: Path,
        product_name: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Extract chemical structures from SDS PDF.
        
        Args:
            pdf_path: Path to PDF file
            product_name: Optional product name for validation
        
        Returns:
            List of extracted structures with metadata
        """
        structures = []
        
        # Extract images
        logger.info(f"Extracting images from {pdf_path.name}")
        images = self.image_extractor.extract_images_from_pdf(pdf_path)
        logger.info(f"Found {len(images)} images")
        
        # Process each image
        for idx, image in enumerate(images):
            # Check if likely structure
            is_structure, confidence = self.image_extractor.is_likely_structure(image)
            
            if not is_structure:
                logger.debug(f"Image {idx} unlikely to be structure (confidence: {confidence:.2f})")
                continue
            
            logger.info(f"Processing potential structure image {idx}")
            
            # Recognize structure
            result = self.recognizer.recognize_from_image(image)
            
            if result.smiles:
                # Validate structure
                validation = self.recognizer.validate_structure(
                    result.smiles,
                    product_name
                )
                
                structure_info = {
                    "image_index": idx,
                    "smiles": result.smiles,
                    "inchi": result.inchi,
                    "inchi_key": result.inchi_key,
                    "confidence": result.confidence,
                    "method": result.method,
                    "pubchem_cid": result.pubchem_cid,
                    "matched_name": result.matched_name,
                    "validation": validation,
                }
                
                structures.append(structure_info)
                logger.info(f"Extracted structure: {result.smiles} (confidence: {result.confidence:.2f})")
        
        return structures


def convert_smiles_to_inchi(smiles: str) -> Optional[str]:
    """Convert SMILES to InChI format."""
    try:
        from rdkit import Chem
        mol = Chem.MolFromSmiles(smiles)
        if mol:
            return Chem.MolToInchi(mol)
    except:
        pass
    return None


def convert_inchi_to_smiles(inchi: str) -> Optional[str]:
    """Convert InChI to SMILES format."""
    try:
        from rdkit import Chem
        mol = Chem.MolFromInchi(inchi)
        if mol:
            return Chem.MolToSmiles(mol)
    except:
        pass
    return None
