from src.matrix.builder import MatrixBuilder


class _DbWithRules:
    def fetch_results(self, limit: int = 500):
        return [
            {
                "id": 1,
                "product_name": "Prod A",
                "cas_number": "123-45-6",
                "hazard_class": "3",
                "incompatibilities": "",
            },
            {
                "id": 2,
                "product_name": "Prod B",
                "cas_number": "789-01-2",
                "hazard_class": "8",
                "incompatibilities": "",
            },
            {
                "id": 3,
                "product_name": "Prod C",
                "cas_number": "50-00-0",
                "hazard_class": "3",
                "incompatibilities": "",
            },
            {
                "id": 4,
                "product_name": "Prod D",
                "cas_number": "64-17-5",
                "hazard_class": "3",
                "incompatibilities": "",
            },
            {
                "id": 5,
                "product_name": "Prod E",
                "cas_number": "99-99-9",
                "hazard_class": "3",
                "incompatibilities": "",
            },
        ]

    def get_incompatibility_rule(self, cas_a, cas_b):
        if {cas_a, cas_b} == {"123-45-6", "789-01-2"}:
            return {"rule": "I", "source": "UNIFAL"}
        return None

    def get_hazard_record(self, cas):
        if cas == "50-00-0":
            return {"hazard_flags": {"dangerous": True}, "env_risk": False}
        if cas == "64-17-5":
            return {"hazard_flags": None, "env_risk": True}
        if cas == "99-99-9":
            return {"hazard_flags": None, "env_risk": False, "idlh": 30}
        return None


def test_matrix_prefers_structured_rules():
    builder = MatrixBuilder()
    builder.db = _DbWithRules()

    matrix = builder.build_incompatibility_matrix()

    assert matrix.loc["Prod A", "Prod B"] == "Incompatible"
    assert matrix.loc["Prod B", "Prod A"] == "Incompatible"
    # Hazard elevation turns compatible pairs into Restricted
    assert matrix.loc["Prod C", "Prod D"] == "Restricted"
    # IDLH threshold elevation (default 50)
    assert matrix.loc["Prod E", "Prod D"] == "Restricted"


def test_matrix_idlh_threshold_configurable(monkeypatch):
    builder = MatrixBuilder()
    # Raise threshold to avoid elevating IDLH=30 pair
    builder.hazard_idlh_threshold = 10
    builder.db = _DbWithRules()

    matrix = builder.build_incompatibility_matrix()

    # Pair without env_risk/dangerous should stay compatible with higher threshold
    assert matrix.loc["Prod E", "Prod A"] == "Compatible"
