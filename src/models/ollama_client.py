"""Unified Ollama client for all LLM operations."""

from __future__ import annotations

import base64
import hashlib
import json
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any
import os
import time
import collections

import httpx
from langchain_ollama import OllamaEmbeddings

from ..config.settings import get_settings
from ..utils.logger import get_logger
from .llm_metrics import LLMMetrics
from .few_shot_examples import get_few_shot_examples

logger = get_logger(__name__)


class SimpleLRUCache:
    """Simple LRU cache implementation for extraction results."""

    def __init__(self, max_size: int = 1000):
        """Initialize LRU cache.

        Args:
            max_size: Maximum number of items to cache
        """
        self.max_size = max_size
        self.cache: OrderedDict = OrderedDict()

    def get(self, key: str) -> Any | None:
        """Get item from cache, marking it as recently used."""
        if key in self.cache:
            # Move to end (mark as recently used)
            self.cache.move_to_end(key)
            return self.cache[key]
        return None

    def put(self, key: str, value: Any) -> None:
        """Put item in cache, removing oldest if max_size exceeded."""
        if key in self.cache:
            # Move to end if already exists
            self.cache.move_to_end(key)
        self.cache[key] = value

        # Remove oldest item if cache is full
        if len(self.cache) > self.max_size:
            self.cache.popitem(last=False)

    def clear(self) -> None:
        """Clear all cache entries."""
        self.cache.clear()

    def stats(self) -> dict[str, int]:
        """Get cache statistics."""
        return {"size": len(self.cache), "max_size": self.max_size}


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
    _extraction_cache: SimpleLRUCache = field(
        default_factory=lambda: SimpleLRUCache(max_size=1000), init=False
    )
    _metrics: LLMMetrics = field(default_factory=LLMMetrics, init=False)

    def __post_init__(self) -> None:
        """Initialize embeddings model lazily to avoid blocking."""
        # Don't initialize embeddings here - it's blocking
        # Initialize lazily when first needed
        pass

    def _get_cache_key(self, text: str, field_name: str, model: str) -> str:
        """Generate cache key from text, field name, and model.

        Uses SHA256 hash to keep keys short and avoid issues with special chars.
        """
        content = f"{text[:2000]}:{field_name}:{model}"
        return hashlib.sha256(content.encode()).hexdigest()

    def clear_extraction_cache(self) -> None:
        """Clear the extraction result cache."""
        self._extraction_cache.clear()
        logger.info("Extraction cache cleared")

    def get_cache_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        return self._extraction_cache.stats()

    def get_metrics_stats(self, field_name: str | None = None) -> dict[str, Any]:
        """Get performance metrics statistics.

        Args:
            field_name: Optional field name to filter metrics

        Returns:
            Dictionary with aggregated metrics
        """
        return self._metrics.get_stats(field_name=field_name, model=self.extraction_model)

    def get_metrics_summary(self) -> str:
        """Get formatted metrics summary."""
        return self._metrics.summary()

    def clear_metrics(self) -> None:
        """Clear all collected metrics."""
        self._metrics.clear()
        logger.info("Metrics cleared")

    def extract_field_with_fallback(
        self,
        text: str,
        field_name: str,
        prompt_template: str,
        fallback_result: ExtractionResult | None = None,
        confidence_threshold: float = 0.6,
        system_prompt: str | None = None,
    ) -> ExtractionResult:
        """Extract field with automatic fallback if confidence is low.

        Args:
            text: Document text to analyze
            field_name: Name of field to extract
            prompt_template: Prompt template with {text} placeholder
            fallback_result: Result to use if LLM confidence is too low
            confidence_threshold: Minimum confidence required (0.0-1.0)
            system_prompt: Optional system prompt override

        Returns:
            ExtractionResult with fallback applied if needed
        """
        # Try LLM extraction
        llm_result = self.extract_field(
            text, field_name, prompt_template, system_prompt=system_prompt
        )

        # Check if LLM result meets confidence threshold
        if (
            llm_result.value != "NOT_FOUND"
            and llm_result.value != "ERROR"
            and llm_result.confidence >= confidence_threshold
        ):
            logger.debug(
                "LLM result for %s meets threshold (confidence: %.2f >= %.2f)",
                field_name,
                llm_result.confidence,
                confidence_threshold,
            )
            return llm_result

        # Confidence too low, use fallback if provided
        if fallback_result is not None:
            logger.warning(
                "LLM confidence for %s below threshold (%.2f < %.2f), using fallback: %s",
                field_name,
                llm_result.confidence,
                confidence_threshold,
                fallback_result.value,
            )
            return fallback_result

        # No fallback, return LLM result anyway (with warning if low confidence)
        if llm_result.confidence < confidence_threshold:
            logger.warning(
                "LLM result for %s below confidence threshold (%.2f < %.2f)",
                field_name,
                llm_result.confidence,
                confidence_threshold,
            )

        return llm_result

    def extract_field_with_few_shot(
        self,
        text: str,
        field_name: str,
        prompt_template: str,
        system_prompt: str | None = None,
        use_examples: bool = True,
        example_count: int = 3,
    ) -> ExtractionResult:
        """Extract field using few-shot learning with domain examples.

        Args:
            text: Document text to analyze
            field_name: Name of field to extract
            prompt_template: Prompt template with {text} placeholder
            system_prompt: Optional system prompt override
            use_examples: Whether to add few-shot examples (default True)
            example_count: Number of examples to include

        Returns:
            ExtractionResult with few-shot enhanced extraction
        """
        enhanced_prompt = prompt_template

        if use_examples:
            few_shot = get_few_shot_examples()
            enhanced_prompt = few_shot.enhance_prompt(
                field_name, prompt_template, example_count
            )
            logger.debug(
                "Enhanced prompt for %s with %d few-shot examples", field_name, example_count
            )

        result = self.extract_field(
            text, field_name, enhanced_prompt, system_prompt=system_prompt
        )

        # Mark source as few-shot if it came from LLM
        if result.source == "llm":
            result.source = "llm-few-shot"

        return result

    def extract_field_with_consensus(
        self,
        text: str,
        field_name: str,
        prompt_template: str,
        models: list[str] | None = None,
        consensus_threshold: float = 0.8,
        system_prompt: str | None = None,
    ) -> ExtractionResult:
        """Extract field using multiple models with consensus validation.

        Args:
            text: Document text to analyze
            field_name: Name of field to extract
            prompt_template: Prompt template with {text} placeholder
            models: List of models to use (default: extraction_model only)
            consensus_threshold: Threshold for confidence boost (0.0-1.0)
            system_prompt: Optional system prompt override

        Returns:
            ExtractionResult with consensus-enhanced confidence
        """
        if models is None:
            models = [self.extraction_model]

        if len(models) == 1:
            # Single model, no consensus needed
            return self.extract_field(
                text, field_name, prompt_template, system_prompt=system_prompt
            )

        logger.info(
            "Starting consensus extraction for %s using %d models: %s",
            field_name,
            len(models),
            models,
        )

        results: dict[str, ExtractionResult] = {}

        # Extract with each model
        for model in models:
            # Temporarily override extraction model
            original_model = self.extraction_model
            self.extraction_model = model
            try:
                result = self.extract_field(
                    text, field_name, prompt_template, system_prompt=system_prompt
                )
                results[model] = result
                logger.debug("Extraction with %s: value=%s, confidence=%.2f", model, result.value, result.confidence)
            finally:
                self.extraction_model = original_model

        # Calculate consensus
        successful_results = [r for r in results.values() if r.value != "NOT_FOUND" and r.value != "ERROR"]

        if not successful_results:
            logger.warning("No successful extractions for %s", field_name)
            return ExtractionResult(value="NOT_FOUND", confidence=0.0)

        # Check if models agree on the value (for non-continuous values)
        values = [r.value for r in successful_results]
        unique_values = set(values)

        # If all models agree on same value, boost confidence
        if len(unique_values) == 1 and len(successful_results) > 1:
            agreed_value = values[0]
            avg_confidence = sum(r.confidence for r in successful_results) / len(successful_results)
            consensus_confidence = min(1.0, avg_confidence + 0.15)  # +15% boost for consensus

            logger.info(
                "Consensus achieved for %s: %d/%d models agreed on '%s', confidence: %.2f → %.2f",
                field_name,
                len(successful_results),
                len(models),
                agreed_value,
                avg_confidence,
                consensus_confidence,
            )

            return ExtractionResult(
                value=agreed_value,
                confidence=consensus_confidence,
                context=f"Consensus from {len(successful_results)}/{len(models)} models",
                source="consensus",
            )

        # Models disagree, use highest confidence
        best_result = max(successful_results, key=lambda r: r.confidence)

        logger.warning(
            "No consensus for %s: models disagreed. Using best result (confidence: %.2f) from %d models",
            field_name,
            best_result.confidence,
            len(successful_results),
        )

        return ExtractionResult(
            value=best_result.value,
            confidence=best_result.confidence * 0.95,  # Slight penalty for disagreement
            context=f"Best of {len(successful_results)}/{len(models)} models (disagreement)",
            source="best-effort",
        )

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
        use_cache: bool = True,
    ) -> ExtractionResult:
        """Extract a specific field from text using LLM.

        Args:
            text: Document text to analyze
            field_name: Name of field to extract
            prompt_template: Prompt template with {text} placeholder
            system_prompt: Optional system prompt override
            use_cache: Whether to use cache for this extraction (default True)

        Returns:
            ExtractionResult with value and confidence
        """
        start_time = time.time()
        cache_hit = False

        # Check cache first
        if use_cache:
            cache_key = self._get_cache_key(text, field_name, self.extraction_model)
            cached_result = self._extraction_cache.get(cache_key)
            if cached_result is not None:
                logger.debug(
                    "Cache hit for field %s (key: %s)", field_name, cache_key[:8]
                )
                latency = time.time() - start_time
                cache_hit = True
                # Record cache hit metric
                self._metrics.record(
                    field_name=field_name,
                    model=self.extraction_model,
                    latency=latency,
                    success=True,
                    confidence=cached_result.confidence,
                    cache_hit=True,
                )
                return cached_result

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
            result = ExtractionResult(
                value=str(parsed.get("value", "NOT_FOUND")),
                confidence=float(parsed.get("confidence", 0.0)),
                context=str(parsed.get("context", "")),
                source="llm",
            )

            # Store in cache
            if use_cache:
                cache_key = self._get_cache_key(text, field_name, self.extraction_model)
                self._extraction_cache.put(cache_key, result)

            # Record success metric
            latency = time.time() - start_time
            self._metrics.record(
                field_name=field_name,
                model=self.extraction_model,
                latency=latency,
                success=True,
                confidence=result.confidence,
                cache_hit=cache_hit,
            )

            return result

        except Exception as e:
            logger.error("Field extraction failed for %s: %s", field_name, e)
            latency = time.time() - start_time
            # Record failure metric
            self._metrics.record(
                field_name=field_name,
                model=self.extraction_model,
                latency=latency,
                success=False,
                cache_hit=cache_hit,
            )
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
            results: dict[str, ExtractionResult] = {}

            for field_name in fields:
                field_data = parsed.get(field_name, {})
                if isinstance(field_data, dict):
                    results[field_name] = ExtractionResult(
                        value=str(field_data.get("value", "NOT_FOUND")),
                        confidence=float(field_data.get("confidence", 0.0)),
                        source="llm",
                    )
                else:
                    results[field_name] = ExtractionResult(
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

        except TimeoutError as e:
            logger.debug("OCR timeout (expected for large images): %s. Increase OCR_TIMEOUT_SECONDS if needed.", e)
            return ""
        except Exception as e:
            logger.debug("OCR failed (skipping gracefully): %s", e)
            return ""

    def ocr_images_parallel(
        self,
        image_paths: list[Path | str],
        max_workers: int | None = None,
    ) -> list[str]:
        """Extract text from multiple images in parallel.

        Args:
            image_paths: List of paths to image files
            max_workers: Maximum number of parallel workers (default: CPU count)

        Returns:
            List of extracted texts in same order as input
        """
        if not image_paths:
            return []

        # Determine number of workers (default to CPU count, max 8 for OCR)
        if max_workers is None:
            max_workers = min(os.cpu_count() or 4, 8)

        results: list[str] = [None] * len(image_paths)  # type: ignore

        logger.info("Starting parallel OCR for %d images with %d workers", len(image_paths), max_workers)
        start_time = time.time()

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_index = {
                executor.submit(self.ocr_image, path): i
                for i, path in enumerate(image_paths)
            }

            # Collect results as they complete
            completed = 0
            for future in as_completed(future_to_index):
                idx = future_to_index[future]
                try:
                    results[idx] = future.result()
                    completed += 1
                    logger.debug("OCR completed for image %d/%d", completed, len(image_paths))
                except Exception as e:
                    logger.error("OCR failed for image %d: %s", idx, e)
                    results[idx] = ""

        elapsed = time.time() - start_time
        logger.info(
            "Parallel OCR completed: %d images in %.2fs (avg: %.2fs per image)",
            len(image_paths),
            elapsed,
            elapsed / len(image_paths) if image_paths else 0,
        )

        return results

    def ocr_image_bytes_parallel(
        self,
        image_bytes_list: list[bytes],
        max_workers: int | None = None,
    ) -> list[str]:
        """Extract text from multiple images (as bytes) in parallel.

        Args:
            image_bytes_list: List of image data as bytes
            max_workers: Maximum number of parallel workers (default: CPU count)

        Returns:
            List of extracted texts in same order as input
        """
        if not image_bytes_list:
            return []

        if max_workers is None:
            max_workers = min(os.cpu_count() or 4, 8)

        results: list[str] = [None] * len(image_bytes_list)  # type: ignore

        logger.info("Starting parallel OCR for %d images (bytes) with %d workers", len(image_bytes_list), max_workers)
        start_time = time.time()

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_index = {
                executor.submit(self.ocr_image_bytes, image_bytes): i
                for i, image_bytes in enumerate(image_bytes_list)
            }

            completed = 0
            for future in as_completed(future_to_index):
                idx = future_to_index[future]
                try:
                    results[idx] = future.result()
                    completed += 1
                    logger.debug("OCR (bytes) completed for image %d/%d", completed, len(image_bytes_list))
                except Exception as e:
                    logger.error("OCR (bytes) failed for image %d: %s", idx, e)
                    results[idx] = ""

        elapsed = time.time() - start_time
        logger.info(
            "Parallel OCR (bytes) completed: %d images in %.2fs (avg: %.2fs per image)",
            len(image_bytes_list),
            elapsed,
            elapsed / len(image_bytes_list) if image_bytes_list else 0,
        )

        return results

    # === Private Methods ===

    def _call_with_retry(
        self,
        func,
        *args,
        max_retries: int = 3,
        **kwargs,
    ) -> Any:
        """Execute a function with exponential backoff retry.

        Args:
            func: Callable to execute
            args: Positional arguments for func
            max_retries: Maximum number of retry attempts (default 3)
            kwargs: Keyword arguments for func

        Returns:
            Result from successful function call

        Raises:
            Last exception if all retries fail
        """
        last_exception = None

        for attempt in range(max_retries):
            try:
                return func(*args, **kwargs)
            except (httpx.ConnectError, httpx.TimeoutException, ConnectionError) as e:
                last_exception = e
                if attempt == max_retries - 1:
                    logger.error(
                        "All %d retry attempts failed for %s: %s",
                        max_retries,
                        func.__name__,
                        e,
                    )
                    raise

                wait_time = 2 ** attempt  # 1s, 2s, 4s, etc.
                logger.warning(
                    "Attempt %d/%d failed for %s. Retrying in %ds: %s",
                    attempt + 1,
                    max_retries,
                    func.__name__,
                    wait_time,
                    e,
                )
                time.sleep(wait_time)
            except Exception as e:
                # Don't retry on non-network errors
                logger.error("Non-retryable error in %s: %s", func.__name__, e)
                raise

        # Should not reach here, but just in case
        if last_exception:
            raise last_exception

    def _chat_completion(
        self,
        model: str,
        system: str,
        user: str,
    ) -> str:
        """Make a chat completion request to Ollama."""
        url = f"{self.base_url}/api/chat"
        self._throttle_ollama()

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

        def make_request():
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(url, json=payload)
                response.raise_for_status()
                resp_json = response.json()
                return resp_json.get("message", {}).get("content", "")

        return self._call_with_retry(make_request)

    def _chat_completion_with_image(
        self,
        model: str,
        prompt: str,
        image_base64: str,
    ) -> str:
        """Make a chat completion request with an image."""
        url = f"{self.base_url}/api/chat"
        self._throttle_ollama()

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

        # Use configurable OCR timeout (default 10 minutes)
        from ..config.settings import get_settings
        settings = get_settings()
        ocr_timeout = settings.processing.ocr_timeout_seconds

        def make_request():
            with httpx.Client(timeout=ocr_timeout) as client:
                response = client.post(url, json=payload)
                response.raise_for_status()
                resp_json = response.json()
                return resp_json.get("message", {}).get("content", "")

        return self._call_with_retry(make_request)

    # === Rate Limiting ===
    _ollama_times: collections.deque[float] = field(default_factory=collections.deque)

    def _throttle_ollama(self) -> None:
        """Throttle requests to Ollama to avoid overload."""
        try:
            max_rps = int(os.getenv("OLLAMA_RPS", "20"))
        except Exception:
            max_rps = 20
        now = time.time()
        self._ollama_times.append(now)
        one_sec_ago = now - 1.0
        while self._ollama_times and self._ollama_times[0] < one_sec_ago:
            self._ollama_times.popleft()
        if len(self._ollama_times) >= max_rps:
            sleep_for = max(0.005, self._ollama_times[0] + 1.0 - now)
            time.sleep(sleep_for)

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
