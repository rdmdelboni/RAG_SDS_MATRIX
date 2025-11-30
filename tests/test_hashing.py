from src.rag.ingestion_service import KnowledgeIngestionService


def test_hash_text_consistency(tmp_path):
    service = KnowledgeIngestionService()
    text = "Safety Data Sheet Example Content"
    h1 = service._hash_text(text)
    h2 = service._hash_text(text)
    assert h1 == h2
    assert len(h1) == 64  # sha256 hex length


def test_hash_file_consistency(tmp_path):
    service = KnowledgeIngestionService()
    file_path = tmp_path / "sample.txt"
    file_path.write_text("ABC123", encoding="utf-8")
    h1 = service._hash_file(file_path)
    h2 = service._hash_file(file_path)
    assert h1 == h2
    assert len(h1) == 64


def test_hash_file_distinct(tmp_path):
    service = KnowledgeIngestionService()
    f1 = tmp_path / "a.txt"
    f2 = tmp_path / "b.txt"
    f1.write_text("ONE", encoding="utf-8")
    f2.write_text("TWO", encoding="utf-8")
    assert service._hash_file(f1) != service._hash_file(f2)
