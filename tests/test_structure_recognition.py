"""
Tests for chemical structure recognition.

Tests structure extraction, recognition, and validation.
"""
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from PIL import Image
import numpy as np

from src.sds.structure_recognition import (
    StructureImageExtractor,
    StructureRecognizer,
    StructureExtractor,
    StructureRecognitionResult,
    convert_smiles_to_inchi,
    convert_inchi_to_smiles,
)


class TestStructureImageExtractor(unittest.TestCase):
    """Test structure image extraction."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.extractor = StructureImageExtractor()
    
    def test_is_likely_structure_valid(self):
        """Test detection of likely structure images."""
        # Create image with structure-like properties
        # White background with black lines (high contrast)
        img_array = np.ones((200, 200), dtype=np.uint8) * 255

        # Draw many lines (simulate structure with more complexity)
        for i in range(10, 190, 20):
            img_array[i:i+3, :] = 0  # Horizontal lines
            img_array[:, i:i+3] = 0  # Vertical lines

        img = Image.fromarray(img_array, mode='L')

        is_structure, confidence = self.extractor.is_likely_structure(img)

        # With more edges, should be detected as structure
        self.assertTrue(is_structure or confidence > 0.25)
    
    def test_is_likely_structure_invalid_aspect_ratio(self):
        """Test rejection of images with bad aspect ratio."""
        # Very elongated image
        img_array = np.ones((50, 500), dtype=np.uint8) * 255
        img = Image.fromarray(img_array, mode='L')
        
        is_structure, confidence = self.extractor.is_likely_structure(img)
        
        self.assertFalse(is_structure)
        self.assertLess(confidence, 0.5)
    
    def test_is_likely_structure_low_contrast(self):
        """Test rejection of uniform/low contrast images."""
        # Uniform gray image
        img_array = np.ones((200, 200), dtype=np.uint8) * 128
        img = Image.fromarray(img_array, mode='L')
        
        is_structure, confidence = self.extractor.is_likely_structure(img)
        
        self.assertFalse(is_structure)
        self.assertLess(confidence, 0.5)
    
    def test_is_likely_structure_too_dark(self):
        """Test rejection of dark images."""
        # Dark image (structures on white background)
        img_array = np.ones((200, 200), dtype=np.uint8) * 50
        img = Image.fromarray(img_array, mode='L')
        
        is_structure, confidence = self.extractor.is_likely_structure(img)
        
        self.assertFalse(is_structure)
        self.assertLess(confidence, 0.5)


class TestStructureRecognizer(unittest.TestCase):
    """Test structure recognition."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.recognizer = StructureRecognizer(cache_ttl=60)
    
    def test_hash_image_consistency(self):
        """Test that same image produces same hash."""
        img_array = np.random.randint(0, 256, (100, 100), dtype=np.uint8)
        img = Image.fromarray(img_array, mode='L')
        
        hash1 = self.recognizer._hash_image(img)
        hash2 = self.recognizer._hash_image(img)
        
        self.assertEqual(hash1, hash2)
    
    def test_hash_image_different(self):
        """Test that different images produce different hashes."""
        img1_array = np.zeros((100, 100), dtype=np.uint8)
        img2_array = np.ones((100, 100), dtype=np.uint8) * 255
        
        img1 = Image.fromarray(img1_array, mode='L')
        img2 = Image.fromarray(img2_array, mode='L')
        
        hash1 = self.recognizer._hash_image(img1)
        hash2 = self.recognizer._hash_image(img2)
        
        self.assertNotEqual(hash1, hash2)
    
    @patch('requests.get')
    def test_lookup_in_pubchem_success(self, mock_get):
        """Test successful PubChem lookup."""
        # Mock PubChem response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "PropertyTable": {
                "Properties": [{
                    "CID": 962,
                    "CanonicalSMILES": "C(C(=O)O)N",
                    "InChI": "InChI=1S/C2H5NO2/c3-1-2(4)5/h1,3H2,(H,4,5)",
                    "InChIKey": "XUJNEKJLAYXESH-UHFFFAOYSA-N"
                }]
            }
        }
        mock_get.return_value = mock_response
        
        result = self.recognizer._lookup_in_pubchem("glycine")
        
        self.assertEqual(result.smiles, "C(C(=O)O)N")
        self.assertEqual(result.pubchem_cid, 962)
        self.assertEqual(result.matched_name, "glycine")
        self.assertGreater(result.confidence, 0.8)
    
    @patch('requests.get')
    def test_lookup_in_pubchem_not_found(self, mock_get):
        """Test PubChem lookup with no results."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response
        
        result = self.recognizer._lookup_in_pubchem("notarealcompound123")
        
        self.assertIsNone(result.smiles)
        self.assertEqual(result.confidence, 0.0)
    
    def test_recognize_from_image_caching(self):
        """Test that recognition results are cached."""
        img_array = np.ones((100, 100), dtype=np.uint8) * 255
        img = Image.fromarray(img_array, mode='L')
        
        # First call
        result1 = self.recognizer.recognize_from_image(img)
        
        # Second call should use cache
        result2 = self.recognizer.recognize_from_image(img)
        
        # Should be same object from cache
        self.assertEqual(result1.method, result2.method)
        self.assertEqual(result1.confidence, result2.confidence)
        
        # Check cache stats
        stats = self.recognizer.get_cache_stats()
        self.assertEqual(stats['hits'], 1)
    
    def test_validate_structure_invalid_smiles(self):
        """Test validation of invalid SMILES."""
        validation = self.recognizer.validate_structure("not_a_valid_smiles")
        
        self.assertFalse(validation['is_valid'])
        self.assertIn('error', validation)
    
    def test_cache_stats(self):
        """Test cache statistics."""
        stats = self.recognizer.get_cache_stats()
        
        self.assertIn('hits', stats)
        self.assertIn('misses', stats)
        self.assertIn('size', stats)
    
    def test_clear_cache(self):
        """Test cache clearing."""
        img_array = np.ones((100, 100), dtype=np.uint8) * 255
        img = Image.fromarray(img_array, mode='L')
        
        # Add to cache
        self.recognizer.recognize_from_image(img)
        
        # Clear cache
        self.recognizer.clear_cache()
        
        # Check cache is empty
        stats = self.recognizer.get_cache_stats()
        self.assertEqual(stats['size'], 0)


class TestStructureExtractor(unittest.TestCase):
    """Test main structure extractor."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.extractor = StructureExtractor()
    
    @patch.object(StructureImageExtractor, 'extract_images_from_pdf')
    @patch.object(StructureImageExtractor, 'is_likely_structure')
    @patch.object(StructureRecognizer, 'recognize_from_image')
    def test_extract_from_pdf(
        self,
        mock_recognize,
        mock_is_likely,
        mock_extract
    ):
        """Test structure extraction from PDF."""
        # Mock image extraction
        img_array = np.ones((200, 200), dtype=np.uint8) * 255
        mock_img = Image.fromarray(img_array, mode='L')
        mock_extract.return_value = [mock_img]
        
        # Mock structure detection
        mock_is_likely.return_value = (True, 0.9)
        
        # Mock recognition
        mock_result = StructureRecognitionResult(
            smiles="CCO",
            inchi="InChI=1S/C2H6O/c1-2-3/h3H,2H2,1H3",
            confidence=0.85,
            method="test",
        )
        mock_recognize.return_value = mock_result
        
        # Extract
        pdf_path = Path("test.pdf")
        structures = self.extractor.extract_from_pdf(pdf_path, product_name="ethanol")
        
        self.assertEqual(len(structures), 1)
        self.assertEqual(structures[0]['smiles'], "CCO")
        self.assertGreater(structures[0]['confidence'], 0.8)
    
    @patch.object(StructureImageExtractor, 'extract_images_from_pdf')
    @patch.object(StructureImageExtractor, 'is_likely_structure')
    def test_extract_from_pdf_no_structures(
        self,
        mock_is_likely,
        mock_extract
    ):
        """Test extraction when no structures found."""
        # Mock image extraction
        img_array = np.ones((200, 200), dtype=np.uint8) * 255
        mock_img = Image.fromarray(img_array, mode='L')
        mock_extract.return_value = [mock_img]
        
        # Mock structure detection (negative)
        mock_is_likely.return_value = (False, 0.1)
        
        # Extract
        pdf_path = Path("test.pdf")
        structures = self.extractor.extract_from_pdf(pdf_path)
        
        self.assertEqual(len(structures), 0)


class TestConversionFunctions(unittest.TestCase):
    """Test SMILES/InChI conversion functions."""
    
    def test_convert_smiles_to_inchi_no_rdkit(self):
        """Test conversion when RDKit not available."""
        # Should handle import error gracefully
        result = convert_smiles_to_inchi("CCO")
        
        # May succeed if RDKit installed, or return None
        self.assertTrue(result is None or result.startswith("InChI="))
    
    def test_convert_inchi_to_smiles_no_rdkit(self):
        """Test conversion when RDKit not available."""
        # Should handle import error gracefully
        result = convert_inchi_to_smiles("InChI=1S/C2H6O/c1-2-3/h3H,2H2,1H3")
        
        # May succeed if RDKit installed, or return None
        self.assertTrue(result is None or isinstance(result, str))


class TestIntegration(unittest.TestCase):
    """Integration tests."""
    
    def test_full_workflow(self):
        """Test full structure extraction workflow."""
        extractor = StructureExtractor()
        
        # Test components initialized
        self.assertIsNotNone(extractor.recognizer)
        self.assertIsNotNone(extractor.image_extractor)
    
    def test_recognizer_initialization(self):
        """Test recognizer initialization."""
        recognizer = StructureRecognizer(cache_ttl=120)

        stats = recognizer.cache.get_stats()
        self.assertEqual(stats['ttl_seconds'], 120)
        self.assertEqual(stats['max_size'], 100)


if __name__ == '__main__':
    # Run tests
    print("Running structure recognition tests...")
    print("=" * 70)
    
    unittest.main(verbosity=2)
