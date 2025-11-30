"""Unit tests for LLM result normalization in SDSProcessor."""

import pytest
from src.sds.processor import SDSProcessor


@pytest.fixture
def processor():
    """Create processor instance for testing."""
    return SDSProcessor()


class TestNormalizeLLMResult:
    """Test suite for _normalize_llm_result method."""

    def test_dict_with_value_passes_through(self, processor):
        """Test that a proper dict with 'value' key passes through."""
        result = {
            "value": "UN1234",
            "confidence": 0.95,
            "method": "llm",
            "context": "Section 14"
        }
        normalized = processor._normalize_llm_result(result)
        
        assert normalized["value"] == "UN1234"
        assert normalized["confidence"] == 0.95
        assert normalized["method"] == "llm"
        assert normalized["context"] == "Section 14"

    def test_dict_without_value_lifts_text_key(self, processor):
        """Test that dict with 'text' key gets normalized."""
        result = {"text": "Hazard Class 3", "confidence": 0.80}
        normalized = processor._normalize_llm_result(result)
        
        assert normalized["value"] == "Hazard Class 3"
        assert normalized["confidence"] == 0.80
        assert normalized["method"] == "llm"

    def test_dict_without_value_lifts_answer_key(self, processor):
        """Test that dict with 'answer' key gets normalized."""
        result = {"answer": "64-17-5", "score": 0.88}
        normalized = processor._normalize_llm_result(result)
        
        assert normalized["value"] == "64-17-5"
        assert normalized["confidence"] == 0.70  # default when not present
        assert normalized["method"] == "llm"

    def test_dict_without_value_lifts_result_key(self, processor):
        """Test that dict with 'result' key gets normalized."""
        result = {"result": "Ethanol", "model": "llama"}
        normalized = processor._normalize_llm_result(result)
        
        assert normalized["value"] == "Ethanol"
        assert normalized["confidence"] == 0.70
        assert normalized["method"] == "llm"

    def test_dict_without_recognized_keys_stringifies(self, processor):
        """Test that dict without known keys gets stringified."""
        result = {"foo": "bar", "baz": 123}
        normalized = processor._normalize_llm_result(result)
        
        assert "foo" in normalized["value"]
        assert "bar" in normalized["value"]
        assert normalized["confidence"] == 0.70
        assert normalized["method"] == "llm"

    def test_plain_string_wrapped_as_value(self, processor):
        """Test that plain string gets wrapped in dict schema."""
        result = "Simple text value"
        normalized = processor._normalize_llm_result(result)
        
        assert normalized["value"] == "Simple text value"
        assert normalized["confidence"] == 0.70
        assert normalized["method"] == "llm"

    def test_json_string_gets_parsed(self, processor):
        """Test that JSON string gets parsed and normalized."""
        result = '{"value": "UN2789", "confidence": 0.92}'
        normalized = processor._normalize_llm_result(result)
        
        assert normalized["value"] == "UN2789"
        assert normalized["confidence"] == 0.92
        assert normalized["method"] == "llm"

    def test_json_string_with_text_key_gets_parsed_and_lifted(self, processor):
        """Test that JSON string with 'text' key gets parsed and lifted."""
        result = '{"text": "Acetic acid", "confidence": 0.85}'
        normalized = processor._normalize_llm_result(result)
        
        assert normalized["value"] == "Acetic acid"
        assert normalized["confidence"] == 0.85
        assert normalized["method"] == "llm"

    def test_malformed_json_string_wrapped_as_value(self, processor):
        """Test that malformed JSON string gets wrapped as plain string."""
        result = '{"incomplete": "json"'
        normalized = processor._normalize_llm_result(result)
        
        assert normalized["value"] == '{"incomplete": "json"'
        assert normalized["confidence"] == 0.70
        assert normalized["method"] == "llm"

    def test_empty_string_wrapped(self, processor):
        """Test that empty string gets wrapped."""
        result = ""
        normalized = processor._normalize_llm_result(result)
        
        assert normalized["value"] == ""
        assert normalized["confidence"] == 0.70
        assert normalized["method"] == "llm"

    def test_numeric_value_coerced_to_string(self, processor):
        """Test that numeric values get coerced to string."""
        result = 12345
        normalized = processor._normalize_llm_result(result)
        
        assert normalized["value"] == "12345"
        assert normalized["confidence"] == 0.70
        assert normalized["method"] == "llm"

    def test_none_value_coerced_to_string(self, processor):
        """Test that None gets coerced to string."""
        result = None
        normalized = processor._normalize_llm_result(result)
        
        assert normalized["value"] == "None"
        assert normalized["confidence"] == 0.70
        assert normalized["method"] == "llm"

    def test_list_value_coerced_to_string(self, processor):
        """Test that list gets coerced to string."""
        result = ["H301", "H315", "H319"]
        normalized = processor._normalize_llm_result(result)
        
        assert "H301" in normalized["value"]
        assert "H315" in normalized["value"]
        assert normalized["confidence"] == 0.70
        assert normalized["method"] == "llm"

    def test_dict_preserves_extra_fields(self, processor):
        """Test that extra fields in valid dict are preserved."""
        result = {
            "value": "Flammable liquid",
            "confidence": 0.88,
            "method": "llm",
            "context": "Section 9",
            "source": "page 3",
            "custom_field": "extra_data"
        }
        normalized = processor._normalize_llm_result(result)
        
        assert normalized["value"] == "Flammable liquid"
        assert normalized["confidence"] == 0.88
        assert normalized["method"] == "llm"
        assert normalized["context"] == "Section 9"
        assert normalized["source"] == "page 3"
        assert normalized["custom_field"] == "extra_data"

    def test_dict_adds_default_confidence_if_missing(self, processor):
        """Test that missing confidence gets default value."""
        result = {"value": "Test value", "method": "rag"}
        normalized = processor._normalize_llm_result(result)
        
        assert normalized["confidence"] == 0.70
        assert normalized["method"] == "rag"

    def test_dict_adds_default_method_if_missing(self, processor):
        """Test that missing method gets default value."""
        result = {"value": "Test value", "confidence": 0.99}
        normalized = processor._normalize_llm_result(result)
        
        assert normalized["method"] == "llm"
        assert normalized["confidence"] == 0.99

    def test_whitespace_only_string(self, processor):
        """Test that whitespace-only string gets wrapped."""
        result = "   \n\t  "
        normalized = processor._normalize_llm_result(result)
        
        assert normalized["value"] == ""  # .strip() is applied
        assert normalized["confidence"] == 0.70
        assert normalized["method"] == "llm"

    def test_json_array_string_gets_parsed(self, processor):
        """Test that JSON array string gets parsed and coerced."""
        result = '["H301", "H315", "H319"]'
        normalized = processor._normalize_llm_result(result)
        
        # Array gets parsed then coerced to string since it's not a dict
        assert "H301" in normalized["value"]
        assert normalized["confidence"] == 0.70
        assert normalized["method"] == "llm"

    def test_nested_dict_with_value(self, processor):
        """Test that nested structures are preserved when value exists."""
        result = {
            "value": "Complex value",
            "confidence": 0.85,
            "metadata": {"nested": "data", "level": 2}
        }
        normalized = processor._normalize_llm_result(result)
        
        assert normalized["value"] == "Complex value"
        assert normalized["confidence"] == 0.85
        assert normalized["metadata"]["nested"] == "data"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
