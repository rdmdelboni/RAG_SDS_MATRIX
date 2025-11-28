from pathlib import Path

from src.rag.ingestion_service import KnowledgeIngestionService


class _StubDb:
    """Minimal stub to avoid real DB connections."""

    pass


class _StubIngestionCfg:
    def __init__(self, base: Path):
        self.brightdata_api_key = None
        self.brightdata_dataset_id = None
        self.dataset_storage_dir = base / "datasets"
        self.dataset_storage_dir.mkdir(parents=True, exist_ok=True)
        self.snapshot_storage_file = base / "snap.txt"
        self.google_api_key = None
        self.google_cse_id = None
        self.allowed_domains = ("allowed.com", "trusted.org")
        self.craw4ai_command = None
        self.craw4ai_output_dir = base / "craw4ai"
        self.craw4ai_output_dir.mkdir(parents=True, exist_ok=True)


class _StubSettings:
    def __init__(self, base: Path):
        self.ingestion = _StubIngestionCfg(base)


def test_is_domain_allowed_uses_whitelist(monkeypatch, tmp_path: Path):
    """Ensure only whitelisted domains are accepted."""

    monkeypatch.setattr(
        "src.rag.ingestion_service.get_settings", lambda: _StubSettings(tmp_path)
    )
    monkeypatch.setattr("src.rag.ingestion_service.get_db_manager", lambda: _StubDb())
    monkeypatch.setattr("src.rag.ingestion_service.get_vector_store", lambda: None)

    service = KnowledgeIngestionService()

    assert service.is_domain_allowed("https://allowed.com/resource")
    assert service.is_domain_allowed("https://sub.trusted.org/path")
    assert service.is_domain_allowed("trusted.org")
    assert not service.is_domain_allowed("https://blocked.net")
    assert not service.is_domain_allowed("blocked.com")
