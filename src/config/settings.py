"""Application settings and configuration management."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Final

from dotenv import load_dotenv

from .mrlp_sources import DEFAULT_MRLP_ALLOWED_DOMAINS

# Load environment variables
load_dotenv()
load_dotenv(
    dotenv_path=Path(__file__).parent.parent.parent / ".env.local", override=True
)

# Base directories
BASE_DIR: Final[Path] = Path(__file__).resolve().parent.parent.parent
DATA_DIR: Final[Path] = Path(os.getenv("DATA_DIR", BASE_DIR / "data"))


@dataclass(frozen=True)
class OllamaConfig:
    """Ollama LLM configuration."""

    base_url: str = field(
        default_factory=lambda: os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    )
    extraction_model: str = field(
        default_factory=lambda: os.getenv(
            "OLLAMA_EXTRACTION_MODEL", "qwen2.5:7b-instruct-q4_K_M"
        )
    )
    chat_model: str = field(
        default_factory=lambda: os.getenv("OLLAMA_CHAT_MODEL", "llama3.1:8b")
    )
    embedding_model: str = field(
        default_factory=lambda: os.getenv(
            "OLLAMA_EMBEDDING_MODEL", "qwen3-embedding:4b"
        )
    )
    ocr_model: str = field(
        default_factory=lambda: os.getenv("OLLAMA_OCR_MODEL", "deepseek-ocr:latest")
    )
    temperature: float = field(
        default_factory=lambda: float(os.getenv("LLM_TEMPERATURE", "0.1"))
    )
    max_tokens: int = field(
        default_factory=lambda: int(os.getenv("LLM_MAX_TOKENS", "2000"))
    )
    timeout: int = field(default_factory=lambda: int(os.getenv("LLM_TIMEOUT", "120")))


@dataclass(frozen=True)
class ProcessingConfig:
    """Document processing configuration."""

    max_workers: int = field(default_factory=lambda: int(os.getenv("MAX_WORKERS", "8")))
    chunk_size: int = field(
        default_factory=lambda: int(os.getenv("CHUNK_SIZE", "1000"))
    )
    chunk_overlap: int = field(
        default_factory=lambda: int(os.getenv("CHUNK_OVERLAP", "200"))
    )
    max_file_size_mb: int = field(
        default_factory=lambda: int(os.getenv("MAX_FILE_SIZE_MB", "50"))
    )
    heuristic_confidence_threshold: float = 0.82  # Skip LLM if heuristics are confident


@dataclass(frozen=True)
class PathsConfig:
    """File system paths configuration."""

    data_dir: Path = field(default_factory=lambda: DATA_DIR)
    chroma_db: Path = field(
        default_factory=lambda: Path(
            os.getenv("CHROMA_DB_PATH", DATA_DIR / "chroma_db")
        )
    )
    duckdb: Path = field(
        default_factory=lambda: Path(
            os.getenv("DUCKDB_PATH", DATA_DIR / "duckdb" / "extractions.db")
        )
    )
    input_dir: Path = field(default_factory=lambda: DATA_DIR / "input")
    output_dir: Path = field(default_factory=lambda: DATA_DIR / "output")
    logs_dir: Path = field(default_factory=lambda: DATA_DIR / "logs")

    def ensure_directories(self) -> None:
        """Create all required directories if they don't exist."""
        for path in [
            self.data_dir,
            self.chroma_db,
            self.duckdb.parent,
            self.input_dir,
            self.output_dir,
            self.logs_dir,
        ]:
            path.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class UIConfig:
    """User interface configuration."""

    language: str = field(default_factory=lambda: os.getenv("UI_LANGUAGE", "pt"))
    theme: str = field(default_factory=lambda: os.getenv("UI_THEME", "dark"))
    window_width: int = 1600
    window_height: int = 900
    min_width: int = 1200
    min_height: int = 700
    # UI scaling
    # Modes: "auto" (default), "compact", "comfortable", "large"
    scale_mode: str = field(
        default_factory=lambda: os.getenv("UI_SCALE_MODE", "auto").lower()
    )
    # Clamp range for auto-scaling; can be overridden via env
    scale_min: float = field(
        default_factory=lambda: float(os.getenv("UI_SCALE_MIN", "0.75"))
    )
    scale_max: float = field(
        default_factory=lambda: float(os.getenv("UI_SCALE_MAX", "1.75"))
    )


@dataclass(frozen=True)
class IngestionConfig:
    """External knowledge ingestion configuration."""

    brightdata_api_key: str | None = field(
        default_factory=lambda: os.getenv("BRIGHTDATA_API_KEY")
    )
    brightdata_dataset_id: str | None = field(
        default_factory=lambda: os.getenv("BRIGHTDATA_DATASET_ID")
    )
    dataset_storage_dir: Path = field(
        default_factory=lambda: Path(
            os.getenv("DATASET_STORAGE_FOLDER", DATA_DIR / "datasets")
        )
    )
    snapshot_storage_file: Path = field(
        default_factory=lambda: Path(
            os.getenv("SNAPSHOT_STORAGE_FILE", DATA_DIR / "brightdata_snapshot.txt")
        )
    )
    google_api_key: str | None = field(
        default_factory=lambda: os.getenv("GOOGLE_API_KEY")
    )
    google_cse_id: str | None = field(
        default_factory=lambda: os.getenv("GOOGLE_CSE_ID")
    )
    allowed_domains: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            domain.strip()
            for domain in os.getenv("MRLP_ALLOWED_DOMAINS", "").split(",")
            if domain.strip()
        )
        or tuple(sorted(DEFAULT_MRLP_ALLOWED_DOMAINS))
    )
    craw4ai_command: str | None = field(
        default_factory=lambda: os.getenv("CRAW4AI_COMMAND")
    )
    craw4ai_output_dir: Path = field(
        default_factory=lambda: Path(
            os.getenv("CRAW4AI_OUTPUT_DIR", DATA_DIR / "craw4ai")
        )
    )

    def ensure_directories(self) -> None:
        """Create ingestion-related directories."""
        self.dataset_storage_dir.mkdir(parents=True, exist_ok=True)
        if self.snapshot_storage_file:
            self.snapshot_storage_file.parent.mkdir(parents=True, exist_ok=True)
        self.craw4ai_output_dir.mkdir(parents=True, exist_ok=True)


@dataclass
class Settings:
    """Main application settings container."""

    ollama: OllamaConfig = field(default_factory=OllamaConfig)
    processing: ProcessingConfig = field(default_factory=ProcessingConfig)
    paths: PathsConfig = field(default_factory=PathsConfig)
    ingestion: IngestionConfig = field(default_factory=IngestionConfig)
    ui: UIConfig = field(default_factory=UIConfig)
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    hazard_idlh_threshold: float = field(
        default_factory=lambda: float(os.getenv("HAZARD_IDLH_THRESHOLD", "50"))
    )

    def __post_init__(self) -> None:
        """Initialize directories after settings are loaded."""
        self.paths.ensure_directories()
        self.ingestion.ensure_directories()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Get cached application settings instance."""
    return Settings()
