import pandas as pd

from src.matrix.builder import MatrixBuilder


class _FakeDb:
    """Minimal fake database for matrix tests."""

    def fetch_results(self, limit: int = 500):
        return [
            {
                "id": 1,
                "product_name": "Acido Forte",
                "hazard_class": "3",
                "incompatibilities": "Base Forte",
            },
            {
                "id": 2,
                "product_name": "Base Forte",
                "hazard_class": "8",
                "incompatibilities": "Acido Forte",
            },
        ]


def test_build_incompatibility_matrix_uses_id_key(monkeypatch):
    builder = MatrixBuilder()
    builder.db = _FakeDb()

    matrix = builder.build_incompatibility_matrix()

    assert isinstance(matrix, pd.DataFrame)
    assert matrix.loc["Acido Forte", "Acido Forte"] == "Self"
    assert matrix.loc["Acido Forte", "Base Forte"] == "Incompatible"
    assert matrix.loc["Base Forte", "Acido Forte"] == "Incompatible"
