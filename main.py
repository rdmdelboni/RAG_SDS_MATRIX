#!/usr/bin/env python3
"""RAG SDS Matrix - Main entry point.

A RAG-enhanced Safety Data Sheet processor that extracts chemical safety
information and generates compatibility matrices.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add src to path for development
sys.path.insert(0, str(Path(__file__).parent / "src"))


def check_dependencies() -> bool:
    """Check if all required dependencies are available."""
    missing = []

    try:
        from PySide6 import QtWidgets  # type: ignore
    except ImportError:
        missing.append("PySide6")

    try:
        import chromadb
    except ImportError:
        missing.append("chromadb")

    try:
        import duckdb
    except ImportError:
        missing.append("duckdb")

    try:
        import pdfplumber
    except ImportError:
        missing.append("pdfplumber")

    try:
        import langchain
    except ImportError:
        missing.append("langchain")

    if missing:
        print("Missing dependencies:")
        for dep in missing:
            print(f"  - {dep}")
        print("\nInstall with: pip install -r requirements.txt")
        return False

    return True


def check_ollama() -> bool:
    """Check if Ollama is running and accessible."""
    from src.models import get_ollama_client

    client = get_ollama_client()
    if not client.test_connection():
        print("\nWarning: Could not connect to Ollama")
        print("Make sure Ollama is running: ollama serve")
        print("The application will start but LLM features will be limited.\n")
        return False

    # List available models
    models = client.list_models()
    if models:
        print(f"Ollama connected. Available models: {', '.join(models[:5])}")
    return True


def main() -> int:
    """Application main entry point."""
    print("=" * 60)
    print("  RAG SDS Matrix - Safety Data Sheet Processor")
    print("=" * 60)
    print()

    # Check dependencies
    if not check_dependencies():
        return 1

    # Check Ollama (non-fatal if not available)
    check_ollama()

    # Import and run the application
    try:
        from src.ui.app import run_app

        run_app()
        return 0
    except ImportError as e:
        print(f"\nError importing UI module: {e}")
        print("Running in CLI mode...")

        # Fallback to CLI mode
        from src.config import get_settings
        from src.database import get_db_manager

        settings = get_settings()
        db = get_db_manager()
        stats = db.get_statistics()

        print(f"\nDatabase: {settings.paths.duckdb}")
        print(f"Documents: {stats['total_documents']}")
        print(f"Processed: {stats['processed']}")
        print(f"RAG Documents: {stats['rag_documents']}")

        return 0


if __name__ == "__main__":
    sys.exit(main())
