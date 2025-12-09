"""Tests for LLM metrics tracking and monitoring."""

from src.models.llm_metrics import LLMMetrics, ExtractionMetrics


class TestExtractionMetrics:
    """Test suite for ExtractionMetrics dataclass."""

    def test_extraction_metrics_creation(self):
        """Test creating extraction metrics."""
        metric = ExtractionMetrics(
            field_name="product_name",
            model="qwen2.5",
            latency_seconds=0.5,
            success=True,
            confidence=0.95,
            cache_hit=False,
        )

        assert metric.field_name == "product_name"
        assert metric.model == "qwen2.5"
        assert metric.latency_seconds == 0.5
        assert metric.success is True
        assert metric.confidence == 0.95
        assert metric.cache_hit is False

    def test_extraction_metrics_to_dict(self):
        """Test converting metrics to dictionary."""
        metric = ExtractionMetrics(
            field_name="cas_number",
            model="llama3.1",
            latency_seconds=1.2,
            success=True,
            confidence=0.85,
        )

        metric_dict = metric.to_dict()

        assert metric_dict["field_name"] == "cas_number"
        assert metric_dict["model"] == "llama3.1"
        assert metric_dict["latency_seconds"] == 1.2
        assert metric_dict["success"] is True
        assert metric_dict["confidence"] == 0.85
        assert "timestamp" in metric_dict


class TestLLMMetrics:
    """Test suite for LLMMetrics aggregation."""

    def test_metrics_recording(self):
        """Test recording metrics."""
        metrics = LLMMetrics()

        metrics.record(
            field_name="product_name",
            model="qwen2.5",
            latency=0.5,
            success=True,
            confidence=0.9,
        )

        assert len(metrics) == 1

    def test_metrics_stats_empty(self):
        """Test stats for empty metrics."""
        metrics = LLMMetrics()

        stats = metrics.get_stats()

        assert stats["total_calls"] == 0
        assert stats["success_rate"] == 0.0

    def test_metrics_stats_single_call(self):
        """Test stats for single call."""
        metrics = LLMMetrics()

        metrics.record(
            field_name="product_name",
            model="qwen2.5",
            latency=0.5,
            success=True,
            confidence=0.9,
        )

        stats = metrics.get_stats()

        assert stats["total_calls"] == 1
        assert stats["successful_calls"] == 1
        assert stats["failed_calls"] == 0
        assert stats["success_rate"] == 1.0
        assert stats["latency"]["avg"] == 0.5
        assert stats["confidence"]["avg"] == 0.9

    def test_metrics_stats_multiple_calls(self):
        """Test stats for multiple calls."""
        metrics = LLMMetrics()

        # Successful calls
        metrics.record("field1", "model1", latency=0.5, success=True, confidence=0.9)
        metrics.record("field1", "model1", latency=0.6, success=True, confidence=0.85)
        # Failed call
        metrics.record("field1", "model1", latency=0.3, success=False)

        stats = metrics.get_stats()

        assert stats["total_calls"] == 3
        assert stats["successful_calls"] == 2
        assert stats["failed_calls"] == 1
        assert stats["success_rate"] == pytest.approx(0.667, abs=0.01)

    def test_metrics_cache_hit_rate(self):
        """Test cache hit rate calculation."""
        metrics = LLMMetrics()

        metrics.record("field1", "model1", latency=0.5, success=True, cache_hit=True)
        metrics.record("field1", "model1", latency=0.6, success=True, cache_hit=True)
        metrics.record("field1", "model1", latency=0.8, success=True, cache_hit=False)

        stats = metrics.get_stats()

        assert stats["cache_hit_rate"] == pytest.approx(0.667, abs=0.01)
        assert stats["cache_hits"] == 2

    def test_metrics_field_filtering(self):
        """Test filtering metrics by field."""
        metrics = LLMMetrics()

        metrics.record("field1", "model1", latency=0.5, success=True)
        metrics.record("field2", "model1", latency=0.6, success=True)
        metrics.record("field1", "model1", latency=0.7, success=False)

        field1_stats = metrics.get_stats(field_name="field1")

        assert field1_stats["total_calls"] == 2
        assert field1_stats["successful_calls"] == 1

    def test_metrics_model_filtering(self):
        """Test filtering metrics by model."""
        metrics = LLMMetrics()

        metrics.record("field1", "model1", latency=0.5, success=True)
        metrics.record("field1", "model2", latency=0.6, success=True)

        model1_stats = metrics.get_stats(model="model1")

        assert model1_stats["total_calls"] == 1

    def test_metrics_field_stats(self):
        """Test per-field statistics."""
        metrics = LLMMetrics()

        metrics.record("field1", "model1", latency=0.5, success=True, confidence=0.9)
        metrics.record("field2", "model1", latency=0.6, success=True, confidence=0.8)

        field_stats = metrics.get_field_stats()

        assert "field1" in field_stats
        assert "field2" in field_stats
        assert field_stats["field1"]["total_calls"] == 1
        assert field_stats["field2"]["total_calls"] == 1

    def test_metrics_model_stats(self):
        """Test per-model statistics."""
        metrics = LLMMetrics()

        metrics.record("field1", "model1", latency=0.5, success=True)
        metrics.record("field2", "model1", latency=0.6, success=True)
        metrics.record("field3", "model2", latency=0.7, success=True)

        model_stats = metrics.get_model_stats()

        assert "model1" in model_stats
        assert "model2" in model_stats
        assert model_stats["model1"]["total_calls"] == 2
        assert model_stats["model2"]["total_calls"] == 1

    def test_metrics_clear(self):
        """Test clearing metrics."""
        metrics = LLMMetrics()

        metrics.record("field1", "model1", latency=0.5, success=True)
        assert len(metrics) == 1

        metrics.clear()
        assert len(metrics) == 0

    def test_metrics_summary(self):
        """Test metrics summary formatting."""
        metrics = LLMMetrics()

        metrics.record("field1", "model1", latency=0.5, success=True, confidence=0.9)
        summary = metrics.summary()

        assert "LLM Metrics Summary" in summary
        assert "Total calls: 1" in summary
        assert "Success rate:" in summary

    def test_metrics_raw_export(self):
        """Test exporting raw metrics."""
        metrics = LLMMetrics()

        metrics.record("field1", "model1", latency=0.5, success=True, confidence=0.9)
        raw = metrics.get_raw_metrics()

        assert len(raw) == 1
        assert raw[0]["field_name"] == "field1"
        assert raw[0]["latency_seconds"] == 0.5

    def test_metrics_max_history(self):
        """Test that metrics history respects max size."""
        metrics = LLMMetrics(max_history=100)

        # Add more than max
        for i in range(150):
            metrics.record(f"field{i}", "model1", latency=0.5, success=True)

        # Should only keep last 100
        assert len(metrics) == 100


# Add pytest import for approx
import pytest
