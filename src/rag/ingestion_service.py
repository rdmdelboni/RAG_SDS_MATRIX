"""Knowledge ingestion service for populating the RAG knowledge base."""

from __future__ import annotations

import hashlib
import json
import shlex
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse

from langchain_core.documents import Document

from ..config.settings import get_settings
from ..database import get_db_manager
from ..utils.logger import get_logger
from .chunker import TextChunker
from .document_loader import DocumentLoader
from .vector_store import get_vector_store

logger = get_logger(__name__)


@dataclass
class IngestionSummary:
    """Summary of an ingestion operation."""

    source_type: str
    processed: int = 0
    chunks_added: int = 0
    skipped: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_message(self) -> str:
        """Return a human-readable summary."""
        parts = [
            f"Source: {self.source_type}",
            f"Processed: {self.processed}",
            f"Chunks added: {self.chunks_added}",
        ]
        if self.skipped:
            parts.append(f"Skipped: {len(self.skipped)}")
        if self.errors:
            parts.append(f"Errors: {len(self.errors)}")
        return " | ".join(parts)


class BrightDataClient:
    """Minimal Bright Data dataset helper."""

    BASE_URL = "https://api.brightdata.com/datasets/v3"

    def __init__(self, api_key: str, dataset_id: str | None = None) -> None:
        self.api_key = api_key
        self.dataset_id = dataset_id

    @property
    def headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def trigger_snapshot(
        self, keywords: list[dict[str, str]], dataset_id: str | None = None
    ) -> str:
        """Trigger a Bright Data snapshot for the provided keywords."""
        if not dataset_id and not self.dataset_id:
            raise ValueError("Bright Data dataset id is required to trigger a snapshot")

        payload = {
            "dataset_id": dataset_id or self.dataset_id,
            "include_errors": "true",
            "type": "discover_new",
            "discover_by": "keyword",
        }

        import requests

        response = requests.post(
            f"{self.BASE_URL}/trigger",
            params=payload,
            headers=self.headers,
            json=keywords,
            timeout=120,
        )
        response.raise_for_status()

        data = response.json()
        snapshot_id = data.get("snapshot_id")
        if not snapshot_id:
            raise RuntimeError("Bright Data did not return a snapshot_id")
        return snapshot_id

    def snapshot_status(self, snapshot_id: str) -> dict[str, Any]:
        """Return the processing status for a snapshot."""
        import requests

        response = requests.get(
            f"{self.BASE_URL}/progress/{snapshot_id}",
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=60,
        )
        response.raise_for_status()
        return response.json()

    def download_snapshot(self, snapshot_id: str, output_path: Path) -> Path:
        """Download a completed snapshot to the given location."""
        import requests

        response = requests.get(
            f"{self.BASE_URL}/snapshot/{snapshot_id}",
            headers=self.headers,
            timeout=300,
        )
        response.raise_for_status()

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(response.content)
        return output_path


class GoogleSearchClient:
    """Google Custom Search client."""

    API_URL = "https://www.googleapis.com/customsearch/v1"

    def __init__(self, api_key: str, cse_id: str) -> None:
        self.api_key = api_key
        self.cse_id = cse_id

    def search(self, query: str, max_results: int = 5) -> list[dict[str, Any]]:
        """Search Google CSE."""
        if not self.api_key or not self.cse_id:
            raise RuntimeError("Google Search not configured")

        import requests

        params = {
            "key": self.api_key,
            "cx": self.cse_id,
            "q": query,
            "num": max(1, min(max_results, 10)),
        }
        response = requests.get(self.API_URL, params=params, timeout=60)
        response.raise_for_status()
        data = response.json()

        items = data.get("items", [])
        results = []
        for item in items:
            results.append(
                {
                    "title": item.get("title") or "Result",
                    "url": item.get("link"),
                    "content": item.get("snippet") or "",
                }
            )
        return results


class Craw4AIClient:
    """Helper for invoking Craw4AI CLI jobs."""

    def __init__(self, command_template: str | None, output_dir: Path) -> None:
        self.command_template = command_template
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def run_job(self, seeds: list[str], mode: str = "url") -> Path:
        """Execute a Craw4AI job and return the output file path."""
        if not self.command_template:
            raise RuntimeError("CRAW4AI_COMMAND not configured")

        with tempfile.NamedTemporaryFile(
            "w", delete=False, encoding="utf-8"
        ) as temp_input:
            for seed in seeds:
                temp_input.write(seed.strip() + "\n")
            input_path = Path(temp_input.name)

        timestamp = int(time.time())
        output_path = self.output_dir / f"craw4ai_{timestamp}.json"
        command = self.command_template.format(
            input_file=str(input_path),
            output_file=str(output_path),
            mode=mode,
        )

        try:
            subprocess.run(
                shlex.split(command),
                check=True,
                capture_output=True,
                text=True,
            )
        finally:
            input_path.unlink(missing_ok=True)

        if not output_path.exists():
            raise RuntimeError("Craw4AI did not produce an output file")

        return output_path


class KnowledgeIngestionService:
    """Central service for feeding knowledge into the vector store."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.db = get_db_manager()
        self.doc_loader = DocumentLoader()
        self.chunker = TextChunker()
        self.vector_store = get_vector_store()
        ingestion_cfg = self.settings.ingestion
        self.allowed_domains = {d.lower() for d in ingestion_cfg.allowed_domains}
        self.brightdata_client = (
            BrightDataClient(
                api_key=ingestion_cfg.brightdata_api_key,
                dataset_id=ingestion_cfg.brightdata_dataset_id,
            )
            if ingestion_cfg.brightdata_api_key
            else None
        )
        self.search_client = (
            GoogleSearchClient(
                api_key=ingestion_cfg.google_api_key,
                cse_id=ingestion_cfg.google_cse_id,
            )
            if ingestion_cfg.google_api_key and ingestion_cfg.google_cse_id
            else None
        )
        self.craw4ai_client = Craw4AIClient(
            command_template=ingestion_cfg.craw4ai_command,
            output_dir=ingestion_cfg.craw4ai_output_dir,
        )

    # === Public ingestion methods ===

    def ingest_local_files(self, file_paths: Iterable[Path]) -> IngestionSummary:
        """Ingest local files into the knowledge base."""
        summary = IngestionSummary(source_type="file")
        for path in map(Path, file_paths):
            try:
                if not path.exists():
                    summary.errors.append(f"{path} not found")
                    continue
                content_hash = self._hash_file(path)
                if self.db.rag_document_exists(content_hash):
                    summary.skipped.append(path.name)
                    continue

                documents = self.doc_loader.load_file(path)
                chunks = self.chunker.chunk_documents(documents)
                if not chunks:
                    summary.skipped.append(path.name)
                    continue

                self.vector_store.add_documents(chunks)
                self.db.register_rag_document(
                    source_type="file",
                    source_path=str(path),
                    title=path.stem,
                    chunk_count=len(chunks),
                    content_hash=content_hash,
                    metadata={"pages": len(documents)},
                )
                summary.processed += 1
                summary.chunks_added += len(chunks)
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.exception("Failed to ingest %s", path)
                summary.errors.append(f"{path.name}: {exc}")
        return summary

    def ingest_url(self, url: str) -> IngestionSummary:
        """Fetch a URL, chunk its text, and ingest it."""
        summary = IngestionSummary(source_type="url")
        if not self.is_domain_allowed(url):
            msg = f"Domain not allowed by whitelist: {url}"
            logger.warning(msg)
            summary.errors.append(msg)
            return summary
        try:
            import requests

            response = requests.get(url, timeout=60)
            response.raise_for_status()
            text = response.text
            metadata = {
                "source": url,
                "title": url.split("/")[-1] or url,
                "type": "url",
            }
            self._ingest_text_blob(text, metadata=metadata, summary=summary)
        except Exception as exc:
            logger.error("URL ingestion failed for %s: %s", url, exc)
            summary.errors.append(str(exc))
        return summary

    def ingest_snapshot_file(self, snapshot_path: Path) -> IngestionSummary:
        """Ingest a Bright Data snapshot (JSON lines)."""
        summary = IngestionSummary(source_type="brightdata")
        try:
            lines = snapshot_path.read_text(encoding="utf-8").splitlines()
        except Exception as exc:
            summary.errors.append(str(exc))
            return summary

        invalid_count = 0
        total = len(lines)
        for idx, line in enumerate(lines, 1):
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
                text = payload.get("raw_text") or payload.get("content")
                if not text:
                    continue
                source_url = payload.get("url") or payload.get("source")
                if source_url and not self.is_domain_allowed(source_url):
                    logger.debug(
                        "Skipping snapshot line (not whitelisted): %s", source_url
                    )
                    summary.skipped.append(f"not_whitelisted:{source_url}")
                    continue
                metadata = {
                    "source": payload.get("url") or payload.get("source"),
                    "title": payload.get("title") or "BrightData Article",
                    "type": "crawler",
                }
                self._ingest_text_blob(text, metadata=metadata, summary=summary)
            except json.JSONDecodeError:
                invalid_count += 1
                logger.warning(
                    "Invalid JSON line in snapshot %s:%d: %s",
                    snapshot_path.name,
                    idx,
                    line[:80],
                )
                summary.skipped.append("invalid_json")
        if invalid_count:
            logger.warning(
                "Snapshot %s had %d invalid JSON lines out of %d",
                snapshot_path.name,
                invalid_count,
                total,
            )
        return summary

    def ingest_structured_incompatibilities(self, jsonl_path: Path) -> IngestionSummary:
        """Ingest structured incompatibility rules (JSONL with cas_a, cas_b, rule)."""
        summary = IngestionSummary(source_type="structured_incompatibilities")
        seen_hashes: set[str] = set()
        file_hash = self._hash_file(jsonl_path)

        # Dedupe whole file
        if self.db.snapshot_exists(file_hash):
            summary.skipped.append("snapshot_exists")
            return summary
        self.db.register_snapshot("incompatibilities", jsonl_path, file_hash)

        try:
            lines = jsonl_path.read_text(encoding="utf-8").splitlines()
        except Exception as exc:
            summary.errors.append(str(exc))
            return summary

        for line in lines:
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                summary.skipped.append("invalid_json")
                continue

            cas_a = payload.get("cas_a")
            cas_b = payload.get("cas_b")
            rule = payload.get("rule")
            if not (cas_a and cas_b and rule):
                summary.skipped.append("missing_fields")
                continue

            justification = payload.get("justification")
            source = payload.get("source", "structured")
            group_a = payload.get("group_a")
            group_b = payload.get("group_b")
            metadata = payload.get("metadata")
            content_hash = payload.get("content_hash") or self._hash_text(line)

            # Dedupe by hash to avoid double-processing
            if content_hash in seen_hashes:
                summary.skipped.append("duplicate_hash")
                continue
            seen_hashes.add(content_hash)

            try:
                self.db.register_incompatibility_rule(
                    cas_a=cas_a,
                    cas_b=cas_b,
                    rule=rule,
                    source=source,
                    justification=justification,
                    group_a=group_a,
                    group_b=group_b,
                    metadata=metadata,
                    content_hash=content_hash,
                )
                summary.processed += 1
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.exception("Failed to store incompatibility rule")
                summary.errors.append(str(exc))

        return summary

    def ingest_structured_hazards(self, jsonl_path: Path) -> IngestionSummary:
        """Ingest structured hazard flags (JSONL with cas, hazard flags, tox/env data)."""
        summary = IngestionSummary(source_type="structured_hazards")
        seen_hashes: set[str] = set()
        file_hash = self._hash_file(jsonl_path)

        if self.db.snapshot_exists(file_hash):
            summary.skipped.append("snapshot_exists")
            return summary
        self.db.register_snapshot("hazards", jsonl_path, file_hash)

        try:
            lines = jsonl_path.read_text(encoding="utf-8").splitlines()
        except Exception as exc:
            summary.errors.append(str(exc))
            return summary

        for line in lines:
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                summary.skipped.append("invalid_json")
                continue

            cas = payload.get("cas")
            if not cas:
                summary.skipped.append("missing_cas")
                continue

            hazard_flags = payload.get("hazard_flags")
            idlh = payload.get("idlh")
            pel = payload.get("pel")
            rel = payload.get("rel")
            env_risk = payload.get("env_risk")
            source = payload.get("source", "structured")
            metadata = payload.get("metadata")
            content_hash = payload.get("content_hash") or self._hash_text(line)

            if content_hash in seen_hashes:
                summary.skipped.append("duplicate_hash")
                continue
            seen_hashes.add(content_hash)

            try:
                self.db.register_hazard_record(
                    cas=cas,
                    hazard_flags=hazard_flags,
                    idlh=idlh,
                    pel=pel,
                    rel=rel,
                    env_risk=env_risk,
                    source=source,
                    metadata=metadata,
                    content_hash=content_hash,
                )
                summary.processed += 1
            except Exception as exc:  # pragma: no cover
                logger.exception("Failed to store hazard record")
                summary.errors.append(str(exc))

        return summary

    def ingest_web_search(self, query: str, max_results: int = 5) -> IngestionSummary:
        """Use Google CSE to retrieve snippets and ingest them."""
        summary = IngestionSummary(source_type="google_search")
        if not self.search_client:
            summary.errors.append("Google Search not configured")
            return summary

        try:
            results = self.search_client.search(query, max_results=max_results)
        except Exception as exc:
            logger.error("Google search failed: %s", exc)
            summary.errors.append(str(exc))
            return summary

        for result in results:
            text = result.get("content", "")
            if not text.strip():
                continue
            url = result.get("url")
            if url and not self.is_domain_allowed(url):
                summary.skipped.append(f"not_whitelisted:{url}")
                continue
            metadata = {
                "source": result.get("url"),
                "title": result.get("title"),
                "type": "google_search",
                "query": query,
            }
            self._ingest_text_blob(text, metadata=metadata, summary=summary)

        return summary

    def ingest_simple_urls(self, urls: list[str]) -> IngestionSummary:
        """Fetch URLs with a lightweight scraper (requests + trafilatura/bs4)."""
        summary = IngestionSummary(source_type="simple_http")
        try:
            import requests
        except ImportError:
            summary.errors.append("requests not installed")
            return summary

        for url in urls:
            if not url.strip():
                continue
            if not self.is_domain_allowed(url):
                summary.skipped.append(f"not_whitelisted:{url}")
                continue
            try:
                response = requests.get(url, timeout=30)
                response.raise_for_status()
                text = self._extract_readable_text(response.text)
                if not text.strip():
                    summary.skipped.append(url)
                    continue
                metadata = {"source": url, "title": url, "type": "simple_http"}
                self._ingest_text_blob(text, metadata=metadata, summary=summary)
            except Exception as exc:
                logger.warning("Simple fetch failed for %s: %s", url, exc)
                summary.errors.append(f"{url}: {exc}")

        return summary

    def run_and_ingest_craw4ai_job(
        self, seeds: list[str], mode: str = "url"
    ) -> IngestionSummary:
        """Run Craw4AI with provided seeds and ingest the resulting JSON."""
        if not self.craw4ai_client or not self.settings.ingestion.craw4ai_command:
            raise RuntimeError("Craw4AI not configured (set CRAW4AI_COMMAND in .env)")

        if mode == "url":
            blocked = [seed for seed in seeds if not self.is_domain_allowed(seed)]
            if blocked:
                raise ValueError(f"Craw4AI seeds not whitelisted: {', '.join(blocked)}")

        output_path = self.craw4ai_client.run_job(seeds, mode=mode)
        return self.ingest_snapshot_file(output_path)

    # === Helpers ===

    def is_domain_allowed(self, url: str) -> bool:
        """Check if URL belongs to an allowed MRLP domain."""
        if not url:
            return False

        parsed = urlparse(url if "://" in url else f"https://{url}")
        hostname = (parsed.hostname or "").lower()
        if not hostname:
            return False

        return any(
            hostname == allowed or hostname.endswith(f".{allowed}")
            for allowed in self.allowed_domains
        )

    def _ingest_text_blob(
        self,
        text: str,
        metadata: dict[str, Any],
        summary: IngestionSummary,
    ) -> None:
        """Chunk and ingest a single text blob."""
        content_hash = self._hash_text(text)
        if self.db.rag_document_exists(content_hash):
            summary.skipped.append(metadata.get("title", "unknown"))
            return

        document = Document(page_content=text, metadata=metadata)
        chunks = self.chunker.chunk_documents([document])
        if not chunks:
            summary.skipped.append(metadata.get("title", "empty"))
            return

        self.vector_store.add_documents(chunks)
        self.db.register_rag_document(
            source_type=metadata.get("type", "text"),
            source_path=metadata.get("source"),
            source_url=metadata.get("source"),
            title=metadata.get("title"),
            chunk_count=len(chunks),
            content_hash=content_hash,
            metadata=metadata,
        )

        summary.processed += 1
        summary.chunks_added += len(chunks)

    @staticmethod
    def _hash_file(path: Path) -> str:
        """Calculate a hash for file deduplication."""
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(8192), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _hash_text(text: str) -> str:
        """Hash raw text content."""
        digest = hashlib.sha256()
        digest.update(text.encode("utf-8", errors="ignore"))
        return digest.hexdigest()

    @staticmethod
    def _extract_readable_text(html: str) -> str:
        """Attempt to extract readable text from HTML using best available parser."""
        try:
            import trafilatura

            extracted = trafilatura.extract(html)
            if extracted:
                return extracted
        except Exception:
            pass

        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(html, "html.parser")
            for script in soup(["script", "style"]):
                script.decompose()
            return soup.get_text(separator="\n", strip=True)
        except Exception:
            return html

    # === Bright Data helpers ===

    def trigger_brightdata_keywords(
        self,
        keywords: list[tuple[str, int]],
    ) -> str:
        """Trigger a Bright Data crawl for the provided keywords."""
        if not self.brightdata_client:
            raise RuntimeError("Bright Data API not configured")

        payload = []
        for keyword, pages in keywords:
            payload.append(
                {
                    "keyword": keyword,
                    "pages_load": str(max(1, pages)),
                }
            )

        snapshot_id = self.brightdata_client.trigger_snapshot(payload)
        self._write_snapshot_id(snapshot_id)
        logger.info("Bright Data snapshot triggered: %s", snapshot_id)
        return snapshot_id

    def get_last_snapshot_id(self) -> str | None:
        """Return the last stored snapshot id."""
        snapshot_file = self.settings.ingestion.snapshot_storage_file
        if snapshot_file.exists():
            content = snapshot_file.read_text(encoding="utf-8").strip()
            if content:
                return content
        return None

    def check_brightdata_status(self, snapshot_id: str | None = None) -> dict[str, Any]:
        """Check the status of a Bright Data snapshot."""
        if not self.brightdata_client:
            raise RuntimeError("Bright Data API not configured")

        snapshot_id = snapshot_id or self.get_last_snapshot_id()
        if not snapshot_id:
            raise RuntimeError("Snapshot ID not provided")

        status = self.brightdata_client.snapshot_status(snapshot_id)
        return status

    def download_brightdata_snapshot(
        self,
        snapshot_id: str | None = None,
    ) -> Path:
        """Download a Bright Data snapshot to the dataset directory."""
        if not self.brightdata_client:
            raise RuntimeError("Bright Data API not configured")

        snapshot_id = snapshot_id or self.get_last_snapshot_id()
        if not snapshot_id:
            raise RuntimeError("Snapshot ID not provided")

        dataset_dir = self.settings.ingestion.dataset_storage_dir
        dataset_dir.mkdir(parents=True, exist_ok=True)
        output_path = dataset_dir / f"{snapshot_id}.jsonl"

        self.brightdata_client.download_snapshot(snapshot_id, output_path)
        self._write_snapshot_id(snapshot_id)
        logger.info("Downloaded snapshot %s to %s", snapshot_id, output_path)
        return output_path

    def download_and_ingest_snapshot(
        self,
        snapshot_id: str | None = None,
    ) -> IngestionSummary:
        """Download snapshot and ingest its contents."""
        file_path = self.download_brightdata_snapshot(snapshot_id)
        summary = self.ingest_snapshot_file(file_path)
        return summary

    def _write_snapshot_id(self, snapshot_id: str) -> None:
        """Persist the last snapshot id for later reference."""
        snapshot_file = self.settings.ingestion.snapshot_storage_file
        snapshot_file.parent.mkdir(parents=True, exist_ok=True)
        snapshot_file.write_text(snapshot_id, encoding="utf-8")
