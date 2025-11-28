import json
from pathlib import Path

from src.rag.ingestion_service import KnowledgeIngestionService


class _StubDb:
    def __init__(self):
        self.rules = []
        self.snapshots = set()

    def register_incompatibility_rule(
        self,
        cas_a,
        cas_b,
        rule,
        source,
        justification=None,
        group_a=None,
        group_b=None,
        metadata=None,
        content_hash=None,
    ):
        self.rules.append(
            {
                "cas_a": cas_a,
                "cas_b": cas_b,
                "rule": rule,
                "source": source,
                "justification": justification,
                "group_a": group_a,
                "group_b": group_b,
                "metadata": metadata,
                "content_hash": content_hash,
            }
        )
    def snapshot_exists(self, content_hash: str) -> bool:
        return content_hash in self.snapshots

    def register_snapshot(self, source_type: str, file_path, content_hash: str) -> None:
        self.snapshots.add(content_hash)


def test_ingest_structured_incompatibilities(monkeypatch, tmp_path: Path):
    db = _StubDb()
    monkeypatch.setattr("src.rag.ingestion_service.get_db_manager", lambda: db)
    monkeypatch.setattr("src.rag.ingestion_service.get_vector_store", lambda: None)

    service = KnowledgeIngestionService()

    file_path = tmp_path / "rules.jsonl"
    entries = [
        {"cas_a": "123-45-6", "cas_b": "789-01-2", "rule": "I", "source": "UNIFAL"},
        {"cas_a": "111-11-1", "cas_b": "222-22-2", "rule": "R", "source": "CAMEO", "justification": "Test"},
        "invalid json",
        {"cas_a": "missing", "rule": "I"},
        {"cas_a": "123-45-6", "cas_b": "789-01-2", "rule": "I", "source": "UNIFAL"},  # duplicate hash
    ]

    with file_path.open("w", encoding="utf-8") as f:
        f.write(json.dumps(entries[0]) + "\n")
        f.write(json.dumps(entries[1]) + "\n")
        f.write(entries[2] + "\n")
        f.write(json.dumps(entries[3]) + "\n")
        f.write(json.dumps(entries[4]) + "\n")

    summary = service.ingest_structured_incompatibilities(file_path)

    assert summary.processed == 2
    assert "invalid_json" in summary.skipped
    assert "missing_fields" in summary.skipped
    assert "duplicate_hash" in summary.skipped
    assert len(db.rules) == 2
