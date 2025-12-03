#!/usr/bin/env python3
"""Test suite for the three new solutions:
1. Browser Provider (bot protection)
2. GHS Database (hazard classifications)
3. Regex Profile Validator
"""

import sys
from pathlib import Path

import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestBrowserProvider:
    """Test browser provider base class and anti-detection features."""
    
    def test_imports(self):
        """Test that browser_provider module can be imported."""
        try:
            from harvester.browser_provider import BrowserSDSProvider
            assert BrowserSDSProvider is not None
        except ImportError as e:
            pytest.skip(f"Playwright not installed: {e}")
    
    def test_base_class_structure(self):
        """Test BrowserSDSProvider has required methods."""
        try:
            from harvester.browser_provider import BrowserSDSProvider
            
            assert hasattr(BrowserSDSProvider, '_ensure_browser')
            assert hasattr(BrowserSDSProvider, '_get_page')
            assert hasattr(BrowserSDSProvider, 'close')
            assert hasattr(BrowserSDSProvider, '__enter__')
            assert hasattr(BrowserSDSProvider, '__exit__')
        except ImportError:
            pytest.skip("Playwright not installed")
    
    def test_context_manager(self):
        """Test context manager protocol."""
        try:
            from harvester.browser_provider import FisherBrowserProvider
            
            # Should not raise
            with FisherBrowserProvider() as provider:
                assert provider is not None
                
        except ImportError:
            pytest.skip("Playwright not installed")
        except Exception as e:
            # Browser may fail to launch in CI, but structure should work
            assert "browser" in str(e).lower() or "playwright" in str(e).lower()
    
    def test_lazy_initialization(self):
        """Test browser is not created until needed."""
        try:
            from harvester.browser_provider import FisherBrowserProvider
            
            provider = FisherBrowserProvider()
            
            # Browser should not be initialized yet
            assert provider._browser is None
            assert provider._context is None
            assert provider._page is None
            
            provider.close()
        except ImportError:
            pytest.skip("Playwright not installed")


class TestGHSDatabase:
    """Test GHS classification database."""
    
    def test_imports(self):
        """Test that ghs_database module can be imported."""
        from sds.ghs_database import GHSDatabase, GHSClassification, get_ghs_database
        
        assert GHSDatabase is not None
        assert GHSClassification is not None
        assert get_ghs_database is not None
    
    def test_database_initialization(self, tmp_path):
        """Test database schema creation."""
        from sds.ghs_database import GHSDatabase
        
        db_path = tmp_path / "test_ghs.db"
        GHSDatabase(db_path)
        
        assert db_path.exists()
        
        # Check tables exist
        import sqlite3
        conn = sqlite3.connect(db_path)
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        tables = {row[0] for row in cursor.fetchall()}
        
        assert 'classifications' in tables
        assert 'components' in tables
        
        conn.close()
    
    def test_add_and_get_classification(self, tmp_path):
        """Test adding and retrieving classifications."""
        from sds.ghs_database import GHSDatabase, GHSClassification
        
        db_path = tmp_path / "test_ghs.db"
        db = GHSDatabase(db_path)
        
        # Add classification
        classification = GHSClassification(
            cas_number="67-64-1",
            hazard_code="H225",
            category="2",
            hazard_class="Flammable liquids",
            statement="Highly flammable liquid and vapor",
            source="TEST",
            confidence=1.0
        )
        
        db.add_classification(classification)
        
        # Retrieve
        results = db.get_classifications("67-64-1")
        
        assert len(results) == 1
        assert results[0].cas_number == "67-64-1"
        assert results[0].hazard_code == "H225"
        assert results[0].statement == "Highly flammable liquid and vapor"
    
    def test_cas_normalization(self, tmp_path):
        """Test CAS number with/without dashes."""
        from sds.ghs_database import GHSDatabase, GHSClassification
        
        db_path = tmp_path / "test_ghs.db"
        db = GHSDatabase(db_path)
        
        # Add with dashes
        classification = GHSClassification(
            cas_number="67-64-1",
            hazard_code="H225",
            category="2",
            hazard_class="Flammable liquids",
            statement="Test",
            source="TEST",
            confidence=1.0
        )
        db.add_classification(classification)
        
        # Query without dashes
        results = db.get_classifications("67641")
        assert len(results) == 1
        
        # Query with dashes
        results = db.get_classifications("67-64-1")
        assert len(results) == 1
    
    def test_multiple_sources(self, tmp_path):
        """Test multiple sources for same CAS/hazard."""
        from sds.ghs_database import GHSDatabase, GHSClassification
        
        db_path = tmp_path / "test_ghs.db"
        db = GHSDatabase(db_path)
        
        # Add from ECHA
        db.add_classification(GHSClassification(
            cas_number="67-64-1",
            hazard_code="H225",
            category="2",
            hazard_class="Flammable liquids",
            statement="Highly flammable liquid and vapor",
            source="ECHA",
            confidence=0.95
        ))
        
        # Add from PubChem
        db.add_classification(GHSClassification(
            cas_number="67-64-1",
            hazard_code="H225",
            category="2",
            hazard_class="Flammable liquids",
            statement="Highly flammable liquid and vapor",
            source="PubChem",
            confidence=0.85
        ))
        
        results = db.get_classifications("67-64-1")
        
        # Should have both sources
        assert len(results) == 2
        sources = {r.source for r in results}
        assert sources == {"ECHA", "PubChem"}
        
        # Should be sorted by confidence (ECHA first)
        assert results[0].source == "ECHA"
        assert results[0].confidence == 0.95
    
    def test_mixture_hazards(self, tmp_path):
        """Test mixture hazard calculation."""
        from sds.ghs_database import GHSDatabase, GHSClassification
        
        db_path = tmp_path / "test_ghs.db"
        db = GHSDatabase(db_path)
        
        # Add classifications for acetone
        db.add_classification(GHSClassification(
            cas_number="67-64-1",
            hazard_code="H225",  # Flammable
            category="2",
            hazard_class="Flammable liquids",
            statement="Highly flammable liquid and vapor",
            source="TEST",
            confidence=1.0
        ))
        
        db.add_classification(GHSClassification(
            cas_number="67-64-1",
            hazard_code="H319",  # Eye irritation
            category="2",
            hazard_class="Eye irritation",
            statement="Causes serious eye irritation",
            source="TEST",
            confidence=1.0
        ))
        
        # Test mixture with high concentration (should inherit hazards)
        components = [
            {
                "cas_number": "67-64-1",
                "min_concentration": 40.0,
                "max_concentration": 45.0,
                "name": "Acetone"
            }
        ]
        
        mixture_hazards = db.get_mixture_hazards(components)
        
        # Should inherit both hazards (above thresholds)
        assert len(mixture_hazards) > 0
        hazard_codes = {h.hazard_code for h in mixture_hazards}
        assert "H225" in hazard_codes  # Flammable threshold ~10%
        assert "H319" in hazard_codes  # Eye irritation threshold ~10%
    
    def test_concentration_thresholds(self, tmp_path):
        """Test concentration threshold logic."""
        from sds.ghs_database import GHSDatabase
        
        db_path = tmp_path / "test_ghs.db"
        db = GHSDatabase(db_path)
        
        # Test various hazard thresholds
        assert db._get_concentration_threshold("H225", "2") == 10.0  # Flammable
        assert db._get_concentration_threshold("H300", "1") == 0.1   # Acute toxicity
        assert db._get_concentration_threshold("H350", "1A") == 0.1  # Carcinogen
        assert db._get_concentration_threshold("H315", "2") == 10.0  # Skin irritation
    
    def test_singleton_cache(self):
        """Test get_ghs_database returns cached instance."""
        from sds.ghs_database import get_ghs_database
        
        db1 = get_ghs_database()
        db2 = get_ghs_database()
        
        # Should be same instance
        assert db1 is db2


class TestRegexValidator:
    """Test regex profile validation tool."""
    
    def test_imports(self):
        """Test that validation script imports work."""
        # This will import the script's functions
        sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
        
        try:
            from validate_regex_profile import load_profile, test_pattern
            assert load_profile is not None
            assert test_pattern is not None
        except ImportError as e:
            if "rich" in str(e).lower():
                pytest.skip("Rich library not installed")
            else:
                raise
    
    def test_load_valid_profile(self, tmp_path):
        """Test loading a valid profile."""
        import json
        sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
        
        try:
            from validate_regex_profile import load_profile
        except ImportError:
            pytest.skip("Rich library not installed")
        
        # Create valid profile
        profile = {
            "manufacturer": "Test Manufacturer",
            "priority": 50,
            "patterns": {
                "product_name": r"Product\s*Name:\s*([^\n]+)",
                "cas_number": r"\b\d{1,7}-\d{2}-\d\b"
            }
        }
        
        profile_path = tmp_path / "test_profile.json"
        profile_path.write_text(json.dumps(profile))
        
        loaded = load_profile(profile_path)
        
        assert loaded is not None
        assert loaded["manufacturer"] == "Test Manufacturer"
        assert loaded["priority"] == 50
    
    def test_load_invalid_json(self, tmp_path):
        """Test loading invalid JSON."""
        sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
        
        try:
            from validate_regex_profile import load_profile
        except ImportError:
            pytest.skip("Rich library not installed")
        
        profile_path = tmp_path / "invalid.json"
        profile_path.write_text("{ invalid json }")
        
        loaded = load_profile(profile_path)
        assert loaded is None
    
    def test_pattern_matching(self):
        """Test pattern matching function."""
        sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
        
        try:
            from validate_regex_profile import test_pattern
        except ImportError:
            pytest.skip("Rich library not installed")
        
        text = "Product Name: Test Chemical\nCAS No: 67-64-1"
        
        # Test successful match
        success, value, confidence = test_pattern(
            r"Product\s*Name:\s*([^\n]+)",
            text,
            "product_name"
        )
        
        assert success is True
        assert "Test Chemical" in value
        assert confidence > 0.5
        
        # Test failed match
        success, value, confidence = test_pattern(
            r"Not\s*Found:\s*([^\n]+)",
            text,
            "missing_field"
        )
        
        assert success is False
        assert confidence == 0.0


class TestIntegration:
    """Integration tests across modules."""
    
    def test_file_structure(self):
        """Test that all expected files exist."""
        base = Path(__file__).parent.parent
        
        # Core files
        assert (base / "src" / "harvester" / "browser_provider.py").exists()
        assert (base / "src" / "sds" / "ghs_database.py").exists()
        assert (base / "scripts" / "validate_regex_profile.py").exists()
        
        # Documentation
        assert (base / "REGEX_CONTRIBUTION_GUIDE.md").exists()
        assert (base / "THREE_LIMITATIONS_SOLVED.md").exists()
    
    def test_no_syntax_errors(self):
        """Test all new Python files compile without syntax errors."""
        base = Path(__file__).parent.parent
        
        files = [
            base / "src" / "harvester" / "browser_provider.py",
            base / "src" / "sds" / "ghs_database.py",
            base / "scripts" / "validate_regex_profile.py",
        ]
        
        for file in files:
            if file.exists():
                with open(file) as f:
                    code = f.read()
                try:
                    compile(code, str(file), 'exec')
                except SyntaxError as e:
                    pytest.fail(f"Syntax error in {file}: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
