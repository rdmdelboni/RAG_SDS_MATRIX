from pathlib import Path

from src.database.db_manager import DatabaseManager


def test_find_hazardous_combinations_from_extracted_inventory(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("RAG_SDS_MATRIX_DB_MODE", "memory")

    db = DatabaseManager(db_path=tmp_path / "test.duckdb")

    f = tmp_path / "a.pdf"
    f.write_bytes(b"%PDF-1.4 dummy")
    doc_id = db.register_document("a.pdf", f, f.stat().st_size, ".pdf", num_pages=1)

    db.replace_document_ingredients(
        doc_id,
        [
            {"cas_number": "67-64-1", "chemical_name": "Acetone", "confidence": 0.9, "source": "heuristic"},
            {"cas_number": "64-17-5", "chemical_name": "Ethanol", "confidence": 0.9, "source": "heuristic"},
        ],
    )

    db.register_incompatibility_rule(
        "64-17-5",
        "67-64-1",
        rule="I",
        source="TEST",
        justification="Example incompatibility",
    )

    combos = db.find_hazardous_combinations()

    assert any(c["cas_a"] == "64-17-5" and c["cas_b"] == "67-64-1" and c["rule"] == "I" for c in combos)

