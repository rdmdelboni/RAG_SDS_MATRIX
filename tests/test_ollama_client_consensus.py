"""Tests for cross-model validation and consensus."""

from unittest.mock import patch

import pytest

from src.models.ollama_client import ExtractionResult, OllamaClient


class TestConsensusExtraction:
    """Test suite for consensus-based extraction."""

    def test_consensus_single_model(self):
        """Test that single model returns standard extraction."""
        client = OllamaClient()

        with patch.object(client, "extract_field") as mock_extract:
            mock_extract.return_value = ExtractionResult(
                value="Sulfuric acid",
                confidence=0.9,
            )

            result = client.extract_field_with_consensus(
                text="Test",
                field_name="product_name",
                prompt_template="Extract: {text}",
                models=[client.extraction_model],
            )

            assert result.value == "Sulfuric acid"
            assert result.confidence == 0.9

    def test_consensus_all_models_agree(self):
        """Test consensus when all models agree."""
        client = OllamaClient()

        results_list = [
            ExtractionResult(value="Sulfuric acid", confidence=0.85),
            ExtractionResult(value="Sulfuric acid", confidence=0.90),
            ExtractionResult(value="Sulfuric acid", confidence=0.88),
        ]

        with patch.object(client, "extract_field", side_effect=results_list):
            result = client.extract_field_with_consensus(
                text="Test",
                field_name="product_name",
                prompt_template="Extract: {text}",
                models=["model1", "model2", "model3"],
            )

            # Confidence should be boosted
            assert result.value == "Sulfuric acid"
            assert result.confidence > 0.90  # Should be boosted from avg 0.876
            assert result.source == "consensus"
            assert "Consensus" in result.context

    def test_consensus_models_disagree(self):
        """Test handling when models disagree."""
        client = OllamaClient()

        results_list = [
            ExtractionResult(value="Sulfuric acid", confidence=0.95),
            ExtractionResult(value="Sulfuric Acid", confidence=0.80),
            ExtractionResult(value="Ácido Sulfúrico", confidence=0.75),
        ]

        with patch.object(client, "extract_field", side_effect=results_list):
            result = client.extract_field_with_consensus(
                text="Test",
                field_name="product_name",
                prompt_template="Extract: {text}",
                models=["model1", "model2", "model3"],
            )

            # Should use best result with penalty
            assert result.value == "Sulfuric acid"
            assert result.confidence < 0.95  # Should have penalty
            assert result.source == "best-effort"
            assert "disagreement" in result.context

    def test_consensus_partial_success(self):
        """Test when some models find value and others don't."""
        client = OllamaClient()

        results_list = [
            ExtractionResult(value="Sulfuric acid", confidence=0.85),
            ExtractionResult(value="NOT_FOUND", confidence=0.0),
            ExtractionResult(value="Sulfuric acid", confidence=0.90),
        ]

        with patch.object(client, "extract_field", side_effect=results_list):
            result = client.extract_field_with_consensus(
                text="Test",
                field_name="product_name",
                prompt_template="Extract: {text}",
                models=["model1", "model2", "model3"],
            )

            # Should achieve consensus on successful results
            assert result.value == "Sulfuric acid"
            assert result.confidence > 0.90
            assert "Consensus from 2/3" in result.context

    def test_consensus_all_fail(self):
        """Test when all models fail to extract."""
        client = OllamaClient()

        results_list = [
            ExtractionResult(value="NOT_FOUND", confidence=0.0),
            ExtractionResult(value="NOT_FOUND", confidence=0.0),
            ExtractionResult(value="ERROR", confidence=0.0),
        ]

        with patch.object(client, "extract_field", side_effect=results_list):
            result = client.extract_field_with_consensus(
                text="Test",
                field_name="product_name",
                prompt_template="Extract: {text}",
                models=["model1", "model2", "model3"],
            )

            assert result.value == "NOT_FOUND"
            assert result.confidence == 0.0

    def test_consensus_confidence_cap(self):
        """Test that consensus confidence doesn't exceed 1.0."""
        client = OllamaClient()

        results_list = [
            ExtractionResult(value="Test", confidence=0.99),
            ExtractionResult(value="Test", confidence=0.99),
        ]

        with patch.object(client, "extract_field", side_effect=results_list):
            result = client.extract_field_with_consensus(
                text="Test",
                field_name="field",
                prompt_template="Extract: {text}",
                models=["model1", "model2"],
            )

            # Should not exceed 1.0
            assert result.confidence <= 1.0
            assert result.confidence > 0.99

    def test_consensus_single_result(self):
        """Test consensus with only one successful result."""
        client = OllamaClient()

        results_list = [
            ExtractionResult(value="NOT_FOUND", confidence=0.0),
            ExtractionResult(value="Test Value", confidence=0.85),
            ExtractionResult(value="NOT_FOUND", confidence=0.0),
        ]

        with patch.object(client, "extract_field", side_effect=results_list):
            result = client.extract_field_with_consensus(
                text="Test",
                field_name="field",
                prompt_template="Extract: {text}",
                models=["model1", "model2", "model3"],
            )

            # Should use single result with disagreement penalty (other models didn't agree)
            assert result.value == "Test Value"
            assert result.confidence == pytest.approx(0.85 * 0.95, abs=0.01)

    def test_consensus_case_sensitivity(self):
        """Test that consensus considers case differences."""
        client = OllamaClient()

        results_list = [
            ExtractionResult(value="Sulfuric Acid", confidence=0.85),
            ExtractionResult(value="sulfuric acid", confidence=0.90),
        ]

        with patch.object(client, "extract_field", side_effect=results_list):
            result = client.extract_field_with_consensus(
                text="Test",
                field_name="product_name",
                prompt_template="Extract: {text}",
                models=["model1", "model2"],
            )

            # Case difference means disagreement
            assert result.source == "best-effort"
            assert "disagreement" in result.context

    def test_consensus_logs_extraction_details(self, caplog):
        """Test that consensus logs extraction details."""
        client = OllamaClient()

        results_list = [
            ExtractionResult(value="Test", confidence=0.85),
            ExtractionResult(value="Test", confidence=0.90),
        ]

        with patch.object(client, "extract_field", side_effect=results_list):
            result = client.extract_field_with_consensus(
                text="Test",
                field_name="field",
                prompt_template="Extract: {text}",
                models=["model1", "model2"],
            )

            # Should log consensus achievement
            assert "Consensus achieved" in caplog.text or result.source == "consensus"
