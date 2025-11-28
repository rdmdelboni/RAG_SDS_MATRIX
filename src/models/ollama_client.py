"""Unified Ollama client for all LLM operations."""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import httpx
from langchain_ollama import OllamaEmbeddings

from ..config.settings import get_settings
from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ExtractionResult:
    """Result of a field extraction."""

    value: str
    confidence: float
    context: str = ""
    source: str = "llm"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "value": self.value,
            "confidence": self.confidence,
            "context": self.context,
            "source": self.source,
        }


@dataclass
class OllamaClient:
    """Unified client for all Ollama operations.

    Provides interfaces for:
    - Text extraction (qwen2.5:7b-instruct)
    - Chat/RAG queries (llama3.1:8b)
    - Embeddings (qwen3-embedding:4b)
    - OCR (deepseek-ocr)
    """

    base_url: str = field(default_factory=lambda: get_settings().ollama.base_url)
    extraction_model: str = field(
        default_factory=lambda: get_settings().ollama.extraction_model
    )
    chat_model: str = field(default_factory=lambda: get_settings().ollama.chat_model)
    embedding_model: str = field(
        default_factory=lambda: get_settings().ollama.embedding_model
    )
    ocr_model: str = field(default_factory=lambda: get_settings().ollama.ocr_model)
    temperature: float = field(
        default_factory=lambda: get_settings().ollama.temperature
    )
    max_tokens: int = field(default_factory=lambda: get_settings().ollama.max_tokens)
    timeout: int = field(default_factory=lambda: get_settings().ollama.timeout)

    _embeddings: OllamaEmbeddings | None = field(default=None, init=False)
    _embeddings_initialized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        """Initialize embeddings model lazily to avoid blocking."""
        # Don't initialize embeddings here - it's blocking
        # Initialize lazily when first needed
        pass

    def _ensure_embeddings(self) -> None:
        """Ensure embeddings model is initialized (lazy loading)."""
        if not self._embeddings_initialized:
            try:
                self._embeddings = OllamaEmbeddings(
                    base_url=self.base_url,
                    model=self.embedding_model,
                )
                self._embeddings_initialized = True
            except Exception as e:
                logger.error("Failed to initialize embeddings model: %s", e)
                self._embeddings_initialized = True  # Mark as attempted to avoid retrying

    # === Connection Testing ===

    def test_connection(self) -> bool:
        """Test if Ollama is accessible."""
        try:
            with httpx.Client(timeout=5) as client:
                response = client.get(f"{self.base_url}/api/tags")
                return response.status_code == 200
        except Exception as e:
            logger.error("Ollama connection failed: %s", e)
            return False

    def list_models(self) -> list[str]:
        """List available Ollama models."""
        try:
            with httpx.Client(timeout=10) as client:
                response = client.get(f"{self.base_url}/api/tags")
                response.raise_for_status()
                data = response.json()
                return [m["name"] for m in data.get("models", [])]
        except Exception as e:
            logger.error("Failed to list models: %s", e)
            return []

    # === Text Extraction ===

    def extract_field(
        self,
        text: str,
        field_name: str,
        prompt_template: str,
        system_prompt: str | None = None,
    ) -> ExtractionResult:
        """Extract a specific field from text using LLM.

        Args:
            text: Document text to analyze
            field_name: Name of field to extract
            prompt_template: Prompt template with {text} placeholder
            system_prompt: Optional system prompt override

        Returns:
            ExtractionResult with value and confidence
        """
        default_system = (
            "You are an expert at extracting specific information from Safety Data Sheets (SDS). "
            "Always respond in JSON format with keys: 'value', 'confidence' (0.0-1.0), 'context'. "
            "If the information is not found, use value='NOT_FOUND' and confidence=0.0."
        )

        prompt = prompt_template.format(text=text[:4000])  # Limit context size

        try:
            response = self._chat_completion(
                model=self.extraction_model,
                system=system_prompt or default_system,
                user=prompt,
            )

            # Parse JSON response
            parsed = self._parse_json_response(response)
            return ExtractionResult(
                value=str(parsed.get("value", "NOT_FOUND")),
                confidence=float(parsed.get("confidence", 0.0)),
                context=str(parsed.get("context", "")),
                source="llm",
            )

        except Exception as e:
            logger.error("Field extraction failed for %s: %s", field_name, e)
            return ExtractionResult(value="ERROR", confidence=0.0, context=str(e))

    def extract_multiple_fields(
        self,
        text: str,
        fields: list[str],
    ) -> dict[str, ExtractionResult]:
        """Extract multiple fields in a single LLM call.

        Args:
            text: Document text to analyze
            fields: List of field names to extract

        Returns:
            Dictionary mapping field names to extraction results
        """
        fields_str = ", ".join(fields)
        prompt = f"""Extract the following fields from this Safety Data Sheet:
{fields_str}

For each field, provide:
- value: the extracted value (or "NOT_FOUND" if not present)
- confidence: your confidence level (0.0 to 1.0)

Respond in JSON format like:
{{
    "field_name": {{"value": "...", "confidence": 0.9}},
    ...
}}

Document text:
{text[:6000]}
"""

        try:
            response = self._chat_completion(
                model=self.extraction_model,
                system="You are an expert SDS analyzer. Respond only in valid JSON.",
                user=prompt,
            )

            parsed = self._parse_json_response(response)
            results = {}

            for field_name in fields:
                field_data = parsed.get(field_name, {})
                if isinstance(field_data, dict):
                    results[field_name] = ExtractionResult(
                        value=str(field_data.get("value", "NOT_FOUND")),
                        confidence=float(field_data.get("confidence", 0.0)),
                        source="llm",
                    )
                else:
                    results[field] = ExtractionResult(
                        value="NOT_FOUND", confidence=0.0, source="llm"
                    )

            return results

        except Exception as e:
            logger.error("Multi-field extraction failed: %s", e)
            return {
                field: ExtractionResult(value="ERROR", confidence=0.0, context=str(e))
                for field in fields
            }

    # === Chat / RAG ===

    def chat(
        self,
        message: str,
        context: str | None = None,
        system_prompt: str | None = None,
    ) -> str:
        """Send a chat message to the LLM.

        Args:
            message: User message
            context: Optional context (e.g., retrieved documents)
            system_prompt: Optional system prompt

        Returns:
            LLM response text
        """
        default_system = (
            "You are a helpful assistant specialized in chemical safety and SDS analysis. "
            "Provide accurate, concise answers based on the context provided."
        )

        user_message = message
        if context:
            user_message = f"Context:\n{context}\n\nQuestion: {message}"

        try:
            return self._chat_completion(
                model=self.chat_model,
                system=system_prompt or default_system,
                user=user_message,
            )
        except Exception as e:
            logger.error("Chat failed: %s", e)
            return f"Error: {e}"

    # === Embeddings ===

    def embed_text(self, text: str) -> list[float]:
        """Generate embeddings for text.

        Args:
            text: Text to embed

        Returns:
            Embedding vector
        """
        try:
            self._ensure_embeddings()
            if self._embeddings:
                return self._embeddings.embed_query(text)
            return []
        except Exception as e:
            logger.error("Embedding failed: %s", e)
            return []

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple documents.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        try:
            self._ensure_embeddings()
            if self._embeddings:
                return self._embeddings.embed_documents(texts)
            return []
        except Exception as e:
            logger.error("Batch embedding failed: %s", e)
            return []

    def get_embeddings(self) -> OllamaEmbeddings | None:
        """Get the embeddings model for LangChain integration."""
        self._ensure_embeddings()
        return self._embeddings

    # === OCR ===

    def ocr_image(self, image_path: Path | str) -> str:
        """Extract text from an image using OCR model.

        Args:
            image_path: Path to image file

        Returns:
            Extracted text
        """
        image_path = Path(image_path)

        try:
            # Read and encode image
            with open(image_path, "rb") as f:
                image_data = base64.b64encode(f.read()).decode("utf-8")

            # Call Ollama with image
            response = self._chat_completion_with_image(
                model=self.ocr_model,
                prompt="Extract all text from this image. Return only the extracted text.",
                image_base64=image_data,
            )

            return response.strip()

        except Exception as e:
            logger.error("OCR failed for %s: %s", image_path, e)
            return ""

    def ocr_image_bytes(self, image_bytes: bytes) -> str:
        """Extract text from image bytes using OCR model.

        Args:
            image_bytes: Image data as bytes

        Returns:
            Extracted text
        """
        try:
            image_data = base64.b64encode(image_bytes).decode("utf-8")

            response = self._chat_completion_with_image(
                model=self.ocr_model,
                prompt="Extract all text from this image. Return only the extracted text.",
                image_base64=image_data,
            )

            return response.strip()

        except Exception as e:
            logger.error("OCR failed: %s", e)
            return ""

    # === Private Methods ===

    def _chat_completion(
        self,
        model: str,
        system: str,
        user: str,
    ) -> str:
        """Make a chat completion request to Ollama."""
        url = f"{self.base_url}/api/chat"

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "options": {
                "temperature": self.temperature,
                "num_predict": self.max_tokens,
            },
        }

        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            return data.get("message", {}).get("content", "")

    def _chat_completion_with_image(
        self,
        model: str,
        prompt: str,
        image_base64: str,
    ) -> str:
        """Make a chat completion request with an image."""
        url = f"{self.base_url}/api/chat"

        payload = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                    "images": [image_base64],
                },
            ],
            "stream": False,
        }

        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            return data.get("message", {}).get("content", "")

    def _parse_json_response(self, response: str) -> dict[str, Any]:
        """Parse JSON from LLM response, handling code blocks."""
        text = response.strip()

        # Try to extract JSON from code blocks
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()

        # Find JSON object
        start = text.find("{")
        if start == -1:
            return {}

        # Find matching closing brace
        brace_count = 0
        for i, char in enumerate(text[start:], start=start):
            if char == "{":
                brace_count += 1
            elif char == "}":
                brace_count -= 1
                if brace_count == 0:
                    json_str = text[start : i + 1]
                    break
        else:
            return {}

        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            logger.warning("Failed to parse JSON: %s", json_str[:200])
            return {}


@lru_cache(maxsize=1)
def get_ollama_client() -> OllamaClient:
    """Get cached Ollama client instance."""
    return OllamaClient()
