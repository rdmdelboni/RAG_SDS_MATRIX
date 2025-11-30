from pathlib import Path

import pytest

from src.sds.processor import SDSProcessor


class _StubDb:
    def __init__(self):
        self.stored = []
        self.updated = []

    def register_document(self, filename, file_path, file_size, file_type, num_pages=None):
        return 1

    def store_extraction(
        self,
        document_id,
        field_name,
        value,
        confidence,
        context="",
        validation_status="pending",
        validation_message=None,
        source="heuristic",
    ):
        self.stored.append(
            {
                "document_id": document_id,
                "field_name": field_name,
                "value": value,
                "confidence": confidence,
                "context": context,
                "validation_status": validation_status,
                "validation_message": validation_message,
                "source": source,
            }
        )

    def update_document_status(
        self,
        doc_id,
        status,
        processing_time=None,
        error_message=None,
        is_dangerous=None,
        completeness=None,
        avg_confidence=None,
    ):
        self.updated.append(
            {
                "doc_id": doc_id,
                "status": status,
                "processing_time": processing_time,
                "error_message": error_message,
                "is_dangerous": is_dangerous,
                "completeness": completeness,
                "avg_confidence": avg_confidence,
            }
        )


class _StubExtractor:
    def extract_document(self, file_path: Path):
        return {"text": "Sample SDS text", "sections": {}}


class _StubHeuristics:
    def extract_all_fields(self, text, sections=None):
        return {
            "hazard_class": {"value": "3", "confidence": 0.9, "context": "", "source": "heuristic"},
        }


class _StubLLM:
    def refine_heuristic(self, field_name, heur_result, text):
        return heur_result

    def extract_multiple_fields(self, fields, text):
        return {}


class _StubValidator:
    def calculate_completeness(self, extractions, required_fields=None):
        return 1.0

    def get_overall_confidence(self, extractions):
        return 1.0

    def is_dangerous(self, hazard_class):
        return True


class _StubRag:
    def __init__(self, stats):
        self.stats = stats

    def get_knowledge_base_stats(self):
        return self.stats


def _patched_validate(field_name, result):
    result["validation_status"] = "valid"
    result["validation_message"] = None
    return result


def test_rag_enrichment_skipped_on_stats_error(monkeypatch, tmp_path: Path):
    test_file = tmp_path / "sds.txt"
    test_file.write_text("dummy", encoding="utf-8")

    processor = SDSProcessor()

    # Patch dependencies with lightweight stubs
    processor.db = _StubDb()
    processor.extractor = _StubExtractor()
    processor.heuristics = _StubHeuristics()
    processor.llm = _StubLLM()
    processor.validator = _StubValidator()
    processor.rag = _StubRag(stats={"error": "vector store unavailable"})

    enrich_called = {"flag": False}

    def _fake_enrich(doc_id, extractions, text):
        enrich_called["flag"] = True
        return extractions

    processor._enrich_with_rag = _fake_enrich

    # Patch validation to avoid relying on full FieldValidator
    monkeypatch.setattr("src.sds.processor.validate_extraction_result", _patched_validate)

    result = processor.process(test_file, use_rag=True)

    assert result.status == "success"
    assert enrich_called["flag"] is False
    # RAG error should still allow processing to complete
    assert processor.db.updated[-1]["status"] == "success"


def test_rag_enrichment_runs_when_docs_available(monkeypatch, tmp_path: Path):
    test_file = tmp_path / "sds.txt"
    test_file.write_text("dummy", encoding="utf-8")

    processor = SDSProcessor()

    processor.db = _StubDb()
    processor.extractor = _StubExtractor()
    processor.heuristics = _StubHeuristics()
    processor.llm = _StubLLM()
    processor.validator = _StubValidator()
    processor.rag = _StubRag(stats={"document_count": 3})

    enrich_called = {"flag": False}

    def _fake_enrich(doc_id, extractions, text):
        enrich_called["flag"] = True
        return extractions

    processor._enrich_with_rag = _fake_enrich
    monkeypatch.setattr("src.sds.processor.validate_extraction_result", _patched_validate)

    processor.process(test_file, use_rag=True)

    assert enrich_called["flag"] is True


def test_missing_fields_trigger_llm_calls(monkeypatch, tmp_path: Path):
    test_file = tmp_path / "sds.txt"
    test_file.write_text("dummy", encoding="utf-8")

    processor = SDSProcessor()
    processor.db = _StubDb()
    processor.extractor = _StubExtractor()

    class _HeuristicsNoFields:
        def extract_all_fields(self, text, sections=None):
            # Return empty to force missing required fields
            return {}

    class _LLMTrackCalls:
        def __init__(self):
            self.refine_called = []
            self.multi_called = False

        def refine_heuristic(self, field_name, heur_result, text):
            self.refine_called.append(field_name)
            return heur_result

        def extract_multiple_fields(self, fields, text):
            self.multi_called = True
            # Return dummy values for required fields
            return {name: {"value": f"VAL_{name}", "confidence": 0.5, "context": "", "source": "llm"} for name in fields}

    tracker = _LLMTrackCalls()
    processor.heuristics = _HeuristicsNoFields()
    processor.llm = tracker
    processor.validator = _StubValidator()
    processor.rag = _StubRag(stats={"document_count": 0})

    monkeypatch.setattr("src.sds.processor.validate_extraction_result", _patched_validate)

    result = processor.process(test_file, use_rag=False)

    assert tracker.multi_called is True
    # Required fields should be filled by LLM fallback
    assert result.extractions


def test_refine_heuristic_invoked_on_low_confidence(monkeypatch, tmp_path: Path):
    test_file = tmp_path / "sds.txt"
    test_file.write_text("dummy", encoding="utf-8")

    processor = SDSProcessor()
    processor.db = _StubDb()
    processor.extractor = _StubExtractor()

    class _HeuristicsLowConf:
        def extract_all_fields(self, text, sections=None):
            return {
                "product_name": {"value": "Acido Forte", "confidence": 0.5, "context": "", "source": "heuristic"},
            }

    class _LLMTracker:
        def __init__(self):
            self.refined = False

        def refine_heuristic(self, field_name, heur_result, text):
            self.refined = True
            return heur_result

        def extract_multiple_fields(self, fields, text):
            return {}

    tracker = _LLMTracker()
    processor.heuristics = _HeuristicsLowConf()
    processor.llm = tracker
    processor.validator = _StubValidator()
    processor.rag = _StubRag(stats={"document_count": 0})

    monkeypatch.setattr("src.sds.processor.validate_extraction_result", _patched_validate)

    processor.process(test_file, use_rag=False)

    assert tracker.refined is True


def test_processor_output_feeds_matrix(monkeypatch, tmp_path: Path):
    """Smoke test chaining processor output into MatrixBuilder with stubs."""
    test_file = tmp_path / "sds.txt"
    test_file.write_text("dummy", encoding="utf-8")

    processor = SDSProcessor()
    processor.db = _StubDb()
    processor.extractor = _StubExtractor()

    class _HeuristicsSimple:
        def extract_all_fields(self, text, sections=None):
            return {
                "product_name": {"value": "Produto A", "confidence": 0.9, "context": "", "source": "heuristic"},
                "hazard_class": {"value": "3", "confidence": 0.9, "context": "", "source": "heuristic"},
                "incompatibilities": {"value": "Produto B", "confidence": 0.9, "context": "", "source": "heuristic"},
            }

    processor.heuristics = _HeuristicsSimple()
    processor.llm = _StubLLM()
    processor.validator = _StubValidator()
    processor.rag = _StubRag(stats={"document_count": 0})

    monkeypatch.setattr("src.sds.processor.validate_extraction_result", _patched_validate)

    result = processor.process(test_file, use_rag=False)

    # Build a fake DB record list from stored extractions
    records = []
    for stored in processor.db.stored:
        records.append(
            {
                "id": 1,
                "product_name": stored["value"] if stored["field_name"] == "product_name" else "Produto A",
                "hazard_class": "3",
                "incompatibilities": "Produto B",
            }
        )

    class _DbForMatrix:
        def fetch_results(self, limit: int = 500):
            return records

    from src.matrix.builder import MatrixBuilder

    builder = MatrixBuilder()
    builder.db = _DbForMatrix()

    matrix = builder.build_incompatibility_matrix()

    assert not matrix.empty
    assert matrix.loc["Produto A", "Produto A"] == "Self"
