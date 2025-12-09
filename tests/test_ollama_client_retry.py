"""Tests for OllamaClient retry mechanism with exponential backoff."""

import time
from unittest.mock import MagicMock, patch

import pytest

from src.models.ollama_client import OllamaClient, ExtractionResult


class TestOllamaClientRetry:
    """Test suite for retry with exponential backoff."""

    def test_retry_succeeds_after_temporary_failure(self):
        """Test that retry succeeds after a temporary connection error."""
        client = OllamaClient()

        call_count = 0

        def failing_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Temporary network error")
            return "success"

        result = client._call_with_retry(failing_func, max_retries=3)

        assert result == "success"
        assert call_count == 3

    def test_retry_fails_after_max_retries(self):
        """Test that retry raises exception after max retries exceeded."""
        client = OllamaClient()

        def always_fails():
            raise ConnectionError("Network error")

        with pytest.raises(ConnectionError):
            client._call_with_retry(always_fails, max_retries=2)

    def test_retry_doesnt_retry_non_network_errors(self):
        """Test that non-network errors are not retried."""
        client = OllamaClient()

        call_count = 0

        def non_network_error():
            nonlocal call_count
            call_count += 1
            raise ValueError("Invalid argument")

        with pytest.raises(ValueError):
            client._call_with_retry(non_network_error, max_retries=3)

        # Should only call once - no retries for non-network errors
        assert call_count == 1

    def test_retry_exponential_backoff_timing(self):
        """Test that exponential backoff timing is correct."""
        client = OllamaClient()

        call_times = []

        def track_timing():
            call_times.append(time.time())
            if len(call_times) < 3:
                raise ConnectionError("Temporary error")
            return "success"

        start = time.time()
        result = client._call_with_retry(track_timing, max_retries=3)
        elapsed = time.time() - start

        assert result == "success"
        # Should have retried twice with 1s and 2s waits = 3s total minimum
        assert elapsed >= 3.0
        # Account for processing time, allow up to 3.5s
        assert elapsed < 3.5

    def test_extraction_field_uses_retry(self):
        """Test that extract_field uses retry mechanism."""
        client = OllamaClient()

        call_count = 0

        # Patch the _call_with_retry to track calls
        original_retry = client._call_with_retry

        def patched_retry(func, *args, **kwargs):
            nonlocal call_count
            call_count += 1
            # Mock successful response
            return '{"value": "test", "confidence": 0.9, "context": "test context"}'

        with patch.object(client, "_call_with_retry", side_effect=patched_retry):
            result = client.extract_field(
                text="Test text",
                field_name="test_field",
                prompt_template="Extract: {text}",
            )

        assert call_count == 1
        assert result.value == "test"
        assert result.confidence == 0.9

    def test_timeout_error_is_retried(self):
        """Test that timeout errors trigger retry mechanism."""
        import httpx

        client = OllamaClient()

        call_count = 0

        def timeout_then_success():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise httpx.TimeoutException("Request timeout")
            return "success"

        result = client._call_with_retry(timeout_then_success, max_retries=2)

        assert result == "success"
        assert call_count == 2
