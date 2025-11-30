from src.rag.ingestion_service import KnowledgeIngestionService


def test_allowed_domain_positive():
    service = KnowledgeIngestionService()
    # Use a domain from default allowed list (should include 'osha.gov' based on examples)
    assert service.is_domain_allowed("https://www.osha.gov/some/page") is True


def test_allowed_domain_negative():
    service = KnowledgeIngestionService()
    assert service.is_domain_allowed("https://not-in-whitelist.example.com") is False
