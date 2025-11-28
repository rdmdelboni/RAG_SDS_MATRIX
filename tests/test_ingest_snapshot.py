import json
from pathlib import Path

from src.rag.ingestion_service import KnowledgeIngestionService


class _StubDb:
    def rag_document_exists(self, content_hash: str) -> bool:
        return False

    def register_rag_document(self, **kwargs):
        return 1


class _StubVectorStore:
    def add_documents(self, docs):
        return None


def test_ingest_snapshot_counts_invalid_json(monkeypatch, tmp_path: Path):
    # Patch heavy dependencies with stubs
    monkeypatch.setattr("src.rag.ingestion_service.get_db_manager", lambda: _StubDb())
    monkeypatch.setattr("src.rag.ingestion_service.get_vector_store", lambda: _StubVectorStore())

    service = KnowledgeIngestionService()

    # Avoid running full ingestion pipeline
    def _fake_ingest_text_blob(text: str, metadata: dict, summary):
        summary.processed += 1
        summary.chunks_added += 1

    monkeypatch.setattr(service, "_ingest_text_blob", _fake_ingest_text_blob)

    snapshot = tmp_path / "snapshot.jsonl"
    valid_line = {"content": "Example content"}

    with snapshot.open("w", encoding="utf-8") as f:
        f.write(json.dumps(valid_line) + "\n")
        f.write("not a json line\n")

    summary = service.ingest_snapshot_file(snapshot)

    assert summary.processed == 1
    assert summary.chunks_added == 1
    assert summary.skipped == ["invalid_json"]
