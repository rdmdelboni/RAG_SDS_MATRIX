import json
from pathlib import Path

from src.rag.ingestion_service import KnowledgeIngestionService


class _StubDb:
    def __init__(self):
        self.hazards = []
        self.snapshots = set()

    def register_hazard_record(
        self,
        cas,
        hazard_flags=None,
        idlh=None,
        pel=None,
        rel=None,
        env_risk=None,
        source=None,
        metadata=None,
        content_hash=None,
    ):
        self.hazards.append(
            {
                "cas": cas,
                "hazard_flags": hazard_flags,
                "idlh": idlh,
                "pel": pel,
                "rel": rel,
                "env_risk": env_risk,
                "source": source,
                "metadata": metadata,
                "content_hash": content_hash,
            }
        )

    def snapshot_exists(self, content_hash: str) -> bool:
        return content_hash in self.snapshots

    def register_snapshot(self, source_type: str, file_path, content_hash: str) -> None:
        self.snapshots.add(content_hash)


def test_ingest_structured_hazards(monkeypatch, tmp_path: Path):
    db = _StubDb()
    monkeypatch.setattr("src.rag.ingestion_service.get_db_manager", lambda: db)
    monkeypatch.setattr("src.rag.ingestion_service.get_vector_store", lambda: None)

    service = KnowledgeIngestionService()

    file_path = tmp_path / "hazards.jsonl"
    entries = [
        {"cas": "50-00-0", "hazard_flags": {"dangerous": True}, "idlh": 20, "source": "NIOSH"},
        {"cas": "64-17-5", "env_risk": True, "source": "CETESB"},
        "invalid",
        {"hazard_flags": {"dangerous": False}},
        {"cas": "50-00-0", "hazard_flags": {"dangerous": True}, "idlh": 20, "source": "NIOSH"},  # duplicate
    ]

    with file_path.open("w", encoding="utf-8") as f:
        f.write(json.dumps(entries[0]) + "\n")
        f.write(json.dumps(entries[1]) + "\n")
        f.write(entries[2] + "\n")
        f.write(json.dumps(entries[3]) + "\n")
        f.write(json.dumps(entries[4]) + "\n")

    summary = service.ingest_structured_hazards(file_path)

    assert summary.processed == 2
    assert "invalid_json" in summary.skipped
    assert "missing_cas" in summary.skipped
    assert "duplicate_hash" in summary.skipped
    assert len(db.hazards) == 2
