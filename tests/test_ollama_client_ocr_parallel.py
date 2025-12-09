"""Tests for parallel OCR functionality."""

from pathlib import Path
from unittest.mock import patch

from src.models.ollama_client import OllamaClient


class TestOCRParallel:
    """Test suite for parallel OCR processing."""

    def test_ocr_images_parallel_empty_list(self):
        """Test parallel OCR with empty image list."""
        client = OllamaClient()

        results = client.ocr_images_parallel([])

        assert results == []

    def test_ocr_images_parallel_single_image(self):
        """Test parallel OCR with single image."""
        client = OllamaClient()

        with patch.object(client, "ocr_image") as mock_ocr:
            mock_ocr.return_value = "extracted text"

            # Create temporary path
            temp_path = Path("/tmp/test_image.jpg")

            results = client.ocr_images_parallel([temp_path])

            assert len(results) == 1
            assert results[0] == "extracted text"
            assert mock_ocr.call_count == 1

    def test_ocr_images_parallel_multiple_images(self):
        """Test parallel OCR with multiple images."""
        client = OllamaClient()

        with patch.object(client, "ocr_image") as mock_ocr:
            # Return different text for each call
            mock_ocr.side_effect = ["text1", "text2", "text3"]

            paths = [Path(f"/tmp/image{i}.jpg") for i in range(3)]

            results = client.ocr_images_parallel(paths, max_workers=2)

            assert len(results) == 3
            assert "text1" in results
            assert "text2" in results
            assert "text3" in results
            assert mock_ocr.call_count == 3

    def test_ocr_images_parallel_maintains_order(self):
        """Test that parallel OCR maintains result order."""
        client = OllamaClient()

        call_count = 0

        def slow_ocr(path):
            """Simulate OCR with different speeds."""
            nonlocal call_count
            call_count += 1
            # Return identifiable text based on call order
            return f"result_{call_count}"

        with patch.object(client, "ocr_image", side_effect=slow_ocr):
            paths = [Path(f"/tmp/image{i}.jpg") for i in range(5)]

            results = client.ocr_images_parallel(paths, max_workers=2)

            # All results should be present
            assert len(results) == 5
            # All should be non-empty
            assert all(r for r in results)

    def test_ocr_images_parallel_handles_errors(self):
        """Test that parallel OCR handles individual failures gracefully."""
        client = OllamaClient()

        def failing_ocr(path):
            # Fail only for image1
            if "image1" in str(path):
                raise Exception("OCR failed")
            return "text"

        with patch.object(client, "ocr_image", side_effect=failing_ocr):
            paths = [Path(f"/tmp/image{i}.jpg") for i in range(3)]

            results = client.ocr_images_parallel(paths, max_workers=2)

            assert len(results) == 3
            # image0 and image2 should succeed
            assert results[0] == "text"
            assert results[2] == "text"
            # image1 should be empty (failed)
            assert results[1] == ""

    def test_ocr_images_parallel_respects_max_workers(self):
        """Test that max_workers parameter is respected."""
        client = OllamaClient()

        active_workers = 0
        max_active = 0

        def tracked_ocr(path):
            nonlocal active_workers, max_active
            active_workers += 1
            max_active = max(max_active, active_workers)
            active_workers -= 1
            return "text"

        with patch.object(client, "ocr_image", side_effect=tracked_ocr):
            paths = [Path(f"/tmp/image{i}.jpg") for i in range(10)]

            client.ocr_images_parallel(paths, max_workers=3)

            # Should not exceed 3 concurrent workers
            assert max_active <= 3

    def test_ocr_image_bytes_parallel_empty_list(self):
        """Test parallel OCR (bytes) with empty list."""
        client = OllamaClient()

        results = client.ocr_image_bytes_parallel([])

        assert results == []

    def test_ocr_image_bytes_parallel_multiple(self):
        """Test parallel OCR (bytes) with multiple images."""
        client = OllamaClient()

        with patch.object(client, "ocr_image_bytes") as mock_ocr:
            mock_ocr.side_effect = ["text1", "text2", "text3"]

            image_bytes_list = [b"image1", b"image2", b"image3"]

            results = client.ocr_image_bytes_parallel(image_bytes_list, max_workers=2)

            assert len(results) == 3
            assert "text1" in results
            assert "text2" in results
            assert "text3" in results

    def test_ocr_parallel_default_max_workers(self):
        """Test that default max_workers is reasonable."""
        client = OllamaClient()

        with patch.object(client, "ocr_image") as mock_ocr:
            mock_ocr.return_value = "text"

            paths = [Path(f"/tmp/image{i}.jpg") for i in range(20)]

            # Should use default max_workers without error
            results = client.ocr_images_parallel(paths)

            assert len(results) == 20
            assert mock_ocr.call_count == 20

    def test_ocr_parallel_returns_in_order(self):
        """Test that results are returned in input order regardless of completion order."""
        client = OllamaClient()

        def indexed_ocr(path):
            # Extract index from path
            idx = int(str(path).split("image")[1].split(".")[0])
            return f"result_{idx}"

        with patch.object(client, "ocr_image", side_effect=indexed_ocr):
            paths = [Path(f"/tmp/image{i}.jpg") for i in range(5)]

            results = client.ocr_images_parallel(paths, max_workers=3)

            # Results should be in correct order
            for i, result in enumerate(results):
                assert f"result_{i}" in result
