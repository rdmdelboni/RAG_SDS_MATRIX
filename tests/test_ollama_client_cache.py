"""Tests for OllamaClient extraction cache with LRU eviction."""

from unittest.mock import MagicMock, patch

import pytest

from src.models.ollama_client import OllamaClient, SimpleLRUCache, ExtractionResult


class TestSimpleLRUCache:
    """Test suite for SimpleLRUCache implementation."""

    def test_cache_stores_and_retrieves_items(self):
        """Test basic cache storage and retrieval."""
        cache = SimpleLRUCache(max_size=10)

        cache.put("key1", "value1")
        assert cache.get("key1") == "value1"

    def test_cache_returns_none_for_missing_key(self):
        """Test that cache returns None for missing keys."""
        cache = SimpleLRUCache(max_size=10)

        assert cache.get("nonexistent") is None

    def test_cache_evicts_oldest_item_when_full(self):
        """Test that oldest item is evicted when cache is full."""
        cache = SimpleLRUCache(max_size=3)

        cache.put("key1", "value1")
        cache.put("key2", "value2")
        cache.put("key3", "value3")

        # Access key1 to mark it as recently used
        cache.get("key1")

        # Add new item - should evict key2 (oldest unused)
        cache.put("key4", "value4")

        assert cache.get("key1") is not None
        assert cache.get("key2") is None  # Should be evicted
        assert cache.get("key3") is not None
        assert cache.get("key4") is not None

    def test_cache_lru_ordering(self):
        """Test that LRU ordering is maintained correctly."""
        cache = SimpleLRUCache(max_size=2)

        cache.put("a", 1)
        cache.put("b", 2)

        # Access 'a' - marks as recently used
        cache.get("a")

        # Add 'c' - should evict 'b' since 'a' was accessed more recently
        cache.put("c", 3)

        assert cache.get("a") is not None
        assert cache.get("b") is None  # Evicted
        assert cache.get("c") is not None

    def test_cache_stats(self):
        """Test cache statistics."""
        cache = SimpleLRUCache(max_size=10)

        cache.put("key1", "value1")
        cache.put("key2", "value2")

        stats = cache.stats()

        assert stats["size"] == 2
        assert stats["max_size"] == 10

    def test_cache_clear(self):
        """Test cache clearing."""
        cache = SimpleLRUCache(max_size=10)

        cache.put("key1", "value1")
        cache.put("key2", "value2")

        cache.clear()

        assert cache.get("key1") is None
        assert cache.get("key2") is None
        assert cache.stats()["size"] == 0


class TestOllamaClientCache:
    """Test suite for OllamaClient caching functionality."""

    def test_extraction_cache_hit(self):
        """Test that extraction results are cached."""
        client = OllamaClient()

        # Mock the LLM response
        with patch.object(client, "_chat_completion") as mock_chat:
            mock_chat.return_value = '{"value": "test", "confidence": 0.9, "context": "ctx"}'

            text = "Test document content"
            field = "product_name"

            # First call - should hit LLM
            result1 = client.extract_field(text, field, "Extract: {text}")
            assert result1.value == "test"
            assert mock_chat.call_count == 1

            # Second call - should hit cache
            result2 = client.extract_field(text, field, "Extract: {text}")
            assert result2.value == "test"
            assert mock_chat.call_count == 1  # No additional call

            # Verify results are identical
            assert result1.value == result2.value
            assert result1.confidence == result2.confidence

    def test_extraction_cache_miss_different_field(self):
        """Test that different fields are cached separately."""
        client = OllamaClient()

        with patch.object(client, "_chat_completion") as mock_chat:
            mock_chat.side_effect = [
                '{"value": "value1", "confidence": 0.9}',
                '{"value": "value2", "confidence": 0.8}',
            ]

            text = "Test document"

            # Extract different fields
            result1 = client.extract_field(text, "field1", "Extract: {text}")
            result2 = client.extract_field(text, "field2", "Extract: {text}")

            # Both should have called LLM (different cache keys)
            assert mock_chat.call_count == 2
            assert result1.value == "value1"
            assert result2.value == "value2"

    def test_extraction_cache_miss_different_text(self):
        """Test that different text inputs are cached separately."""
        client = OllamaClient()

        with patch.object(client, "_chat_completion") as mock_chat:
            mock_chat.side_effect = [
                '{"value": "extracted1", "confidence": 0.9}',
                '{"value": "extracted2", "confidence": 0.8}',
            ]

            # Extract same field from different texts
            result1 = client.extract_field("Text A", "field1", "Extract: {text}")
            result2 = client.extract_field("Text B", "field1", "Extract: {text}")

            # Both should have called LLM (different cache keys)
            assert mock_chat.call_count == 2
            assert result1.value == "extracted1"
            assert result2.value == "extracted2"

    def test_extraction_cache_can_be_disabled(self):
        """Test that cache can be disabled per extraction."""
        client = OllamaClient()

        with patch.object(client, "_chat_completion") as mock_chat:
            mock_chat.return_value = '{"value": "test", "confidence": 0.9}'

            text = "Test document"
            field = "field1"

            # Extract with cache disabled
            result1 = client.extract_field(text, field, "Extract: {text}", use_cache=False)
            result2 = client.extract_field(text, field, "Extract: {text}", use_cache=False)

            # Both calls should hit LLM (cache disabled)
            assert mock_chat.call_count == 2

    def test_clear_extraction_cache(self):
        """Test clearing the extraction cache."""
        client = OllamaClient()

        with patch.object(client, "_chat_completion") as mock_chat:
            mock_chat.return_value = '{"value": "test", "confidence": 0.9}'

            text = "Test document"

            # Extract once (cached)
            client.extract_field(text, "field1", "Extract: {text}")
            assert mock_chat.call_count == 1

            # Clear cache
            client.clear_extraction_cache()

            # Extract again - should hit LLM again
            client.extract_field(text, "field1", "Extract: {text}")
            assert mock_chat.call_count == 2

    def test_get_cache_stats(self):
        """Test retrieving cache statistics."""
        client = OllamaClient()

        with patch.object(client, "_chat_completion") as mock_chat:
            mock_chat.return_value = '{"value": "test", "confidence": 0.9}'

            # Extract a few times
            client.extract_field("Text 1", "field1", "Extract: {text}")
            client.extract_field("Text 2", "field2", "Extract: {text}")

            stats = client.get_cache_stats()

            assert "size" in stats
            assert "max_size" in stats
            assert stats["size"] == 2
            assert stats["max_size"] == 1000  # Default max size
