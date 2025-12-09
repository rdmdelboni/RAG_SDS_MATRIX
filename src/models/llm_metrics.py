"""LLM metrics tracking and monitoring."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any
import statistics

from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ExtractionMetrics:
    """Metrics for a single extraction operation."""

    field_name: str
    model: str
    latency_seconds: float
    success: bool
    confidence: float = 0.0
    cache_hit: bool = False
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "field_name": self.field_name,
            "model": self.model,
            "latency_seconds": self.latency_seconds,
            "success": self.success,
            "confidence": self.confidence,
            "cache_hit": self.cache_hit,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class LLMMetrics:
    """Track and aggregate LLM performance metrics."""

    max_history: int = 10000  # Maximum metrics to keep in memory

    _metrics: list[ExtractionMetrics] = field(default_factory=list, init=False)
    _start_time: datetime = field(default_factory=datetime.now, init=False)

    def record(
        self,
        field_name: str,
        model: str,
        latency: float,
        success: bool,
        confidence: float = 0.0,
        cache_hit: bool = False,
    ) -> None:
        """Record a single extraction metric.

        Args:
            field_name: Name of extracted field
            model: LLM model used
            latency: Time taken in seconds
            success: Whether extraction succeeded
            confidence: Confidence score (0.0-1.0)
            cache_hit: Whether result came from cache
        """
        metric = ExtractionMetrics(
            field_name=field_name,
            model=model,
            latency_seconds=latency,
            success=success,
            confidence=confidence,
            cache_hit=cache_hit,
        )
        self._metrics.append(metric)

        # Trim history if too large
        if len(self._metrics) > self.max_history:
            self._metrics = self._metrics[-self.max_history :]

        logger.debug(
            "Recorded metric: %s (%.2fs, success=%s, confidence=%.2f, cache_hit=%s)",
            field_name,
            latency,
            success,
            confidence,
            cache_hit,
        )

    def get_stats(self, field_name: str | None = None, model: str | None = None) -> dict[str, Any]:
        """Get aggregated statistics.

        Args:
            field_name: Filter by field name (optional)
            model: Filter by model (optional)

        Returns:
            Dictionary with aggregated metrics
        """
        # Filter metrics
        filtered = self._metrics
        if field_name:
            filtered = [m for m in filtered if m.field_name == field_name]
        if model:
            filtered = [m for m in filtered if m.model == model]

        if not filtered:
            return {
                "total_calls": 0,
                "success_rate": 0.0,
                "avg_latency": 0.0,
                "avg_confidence": 0.0,
                "cache_hit_rate": 0.0,
            }

        # Calculate statistics
        total_calls = len(filtered)
        successful = sum(1 for m in filtered if m.success)
        success_rate = successful / total_calls if total_calls > 0 else 0.0

        latencies = [m.latency_seconds for m in filtered]
        avg_latency = statistics.mean(latencies) if latencies else 0.0
        median_latency = statistics.median(latencies) if latencies else 0.0
        min_latency = min(latencies) if latencies else 0.0
        max_latency = max(latencies) if latencies else 0.0

        confidences = [m.confidence for m in filtered if m.success]
        avg_confidence = statistics.mean(confidences) if confidences else 0.0
        median_confidence = statistics.median(confidences) if confidences else 0.0

        cache_hits = sum(1 for m in filtered if m.cache_hit)
        cache_hit_rate = cache_hits / total_calls if total_calls > 0 else 0.0

        return {
            "total_calls": total_calls,
            "successful_calls": successful,
            "failed_calls": total_calls - successful,
            "success_rate": round(success_rate, 4),
            "latency": {
                "avg": round(avg_latency, 3),
                "median": round(median_latency, 3),
                "min": round(min_latency, 3),
                "max": round(max_latency, 3),
            },
            "confidence": {
                "avg": round(avg_confidence, 3),
                "median": round(median_confidence, 3),
            },
            "cache_hit_rate": round(cache_hit_rate, 4),
            "cache_hits": cache_hits,
        }

    def get_field_stats(self) -> dict[str, Any]:
        """Get statistics per field."""
        if not self._metrics:
            return {}

        fields = set(m.field_name for m in self._metrics)
        return {field: self.get_stats(field_name=field) for field in fields}

    def get_model_stats(self) -> dict[str, Any]:
        """Get statistics per model."""
        if not self._metrics:
            return {}

        models = set(m.model for m in self._metrics)
        return {model: self.get_stats(model=model) for model in models}

    def clear(self) -> None:
        """Clear all metrics."""
        self._metrics.clear()
        self._start_time = datetime.now()
        logger.info("Metrics cleared")

    def get_raw_metrics(self) -> list[dict[str, Any]]:
        """Get raw metrics as dictionaries."""
        return [m.to_dict() for m in self._metrics]

    def summary(self) -> str:
        """Get formatted summary of metrics."""
        if not self._metrics:
            return "No metrics recorded"

        uptime = datetime.now() - self._start_time
        stats = self.get_stats()

        summary_lines = [
            "=== LLM Metrics Summary ===",
            f"Uptime: {uptime}",
            f"Total calls: {stats['total_calls']}",
            f"Success rate: {stats['success_rate']*100:.1f}%",
            f"Avg latency: {stats['latency']['avg']:.2f}s",
            f"Median latency: {stats['latency']['median']:.2f}s",
            f"Avg confidence: {stats['confidence']['avg']:.2f}",
            f"Cache hit rate: {stats['cache_hit_rate']*100:.1f}%",
        ]

        return "\n".join(summary_lines)

    def __len__(self) -> int:
        """Get number of recorded metrics."""
        return len(self._metrics)
