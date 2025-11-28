"""Chemical compatibility matrix building and export module.

Provides tools for building chemical compatibility matrices from SDS
extractions and exporting results to various formats.
"""

from __future__ import annotations

from .builder import CompatibilityResult, MatrixBuilder, MatrixStats
from .exporter import MatrixExporter

__all__ = [
    "MatrixBuilder",
    "MatrixExporter",
    "MatrixStats",
    "CompatibilityResult",
]
