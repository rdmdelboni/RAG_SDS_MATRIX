"""LLM Factory - Flexible provider selection for RAG operations.

This module provides a factory pattern for creating LLM instances.
Currently configured to use your existing Ollama solution exclusively.
Custom HTTP endpoints are also supported for future extensibility.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol

from ..utils.logger import get_logger
from .ollama_client import get_ollama_client

logger = get_logger(__name__)


class LLMProvider(str, Enum):
    """Supported LLM providers."""

    OLLAMA = "ollama"
    CUSTOM = "custom"


class LLMInterface(Protocol):
    """Protocol for LLM implementations."""

    def chat(
        self,
        message: str,
        context: str | None = None,
        system_prompt: str | None = None,
    ) -> str:
        """Send chat message."""
        ...

    def extract_field(
        self,
        text: str,
        field_name: str,
        prompt_template: str,
        system_prompt: str | None = None,
    ) -> Any:
        """Extract field from text."""
        ...

    def embed_text(self, text: str) -> list[float]:
        """Generate embeddings."""
        ...


@dataclass
class LLMFactory:
    """Factory for creating LLM instances based on provider configuration."""

    @staticmethod
    def create_llm(
        provider: LLMProvider | str | None = None,
        **kwargs: Any,
    ) -> LLMInterface:
        """Create LLM instance based on provider.

        Args:
            provider: LLM provider (defaults to Ollama)
            **kwargs: Provider-specific configuration

        Returns:
            LLM client instance

        Raises:
            ValueError: If provider is not supported
        """
        # Default to Ollama (your existing solution)
        if provider is None:
            provider = LLMProvider.OLLAMA

        # Convert string to enum
        if isinstance(provider, str):
            try:
                provider = LLMProvider(provider.lower())
            except ValueError:
                raise ValueError(
                    f"Unsupported provider: {provider}. "
                    f"Supported: {[p.value for p in LLMProvider]}"
                )

        logger.info("Creating LLM with provider: %s", provider.value)

        if provider == LLMProvider.OLLAMA:
            return get_ollama_client()

        elif provider == LLMProvider.CUSTOM:
            return LLMFactory._create_custom(**kwargs)

        else:
            raise ValueError(f"Provider {provider} not implemented")

    @staticmethod
    def _create_custom(**kwargs: Any) -> Any:
        """Create custom LLM wrapper.

        Args:
            **kwargs: Custom LLM configuration (endpoint, api_key, headers)

        Returns:
            Custom LLM wrapper

        Raises:
            ValueError: If endpoint not provided
        """
        endpoint = kwargs.get("endpoint") or os.getenv("CUSTOM_LLM_ENDPOINT")
        if not endpoint:
            raise ValueError("Custom LLM requires endpoint")

        api_key = kwargs.get("api_key") or os.getenv("CUSTOM_LLM_API_KEY")
        headers = kwargs.get("headers", {})

        import httpx

        class CustomLLMWrapper:
            """Wrapper for custom LLM endpoints."""

            def __init__(self):
                self.endpoint = endpoint
                self.api_key = api_key
                self.headers = headers

            def chat(
                self,
                message: str,
                context: str | None = None,
                system_prompt: str | None = None,
            ) -> str:
                headers = self.headers.copy()
                if self.api_key:
                    headers["Authorization"] = f"Bearer {self.api_key}"
                headers["Content-Type"] = "application/json"

                payload = {
                    "prompt": message,
                    "system": system_prompt,
                    "context": context,
                }

                with httpx.Client(timeout=120) as client:
                    response = client.post(
                        self.endpoint,
                        json=payload,
                        headers=headers,
                    )
                    response.raise_for_status()
                    return response.json().get("response", "")

            def extract_field(
                self,
                text: str,
                field_name: str,
                prompt_template: str,
                system_prompt: str | None = None,
            ) -> Any:
                prompt = prompt_template.format(text=text[:4000])
                return self.chat(prompt, system_prompt=system_prompt)

            def embed_text(self, text: str) -> list[float]:
                # Custom embeddings would need separate endpoint
                logger.warning("Custom embeddings not implemented")
                return []

        logger.info("Created custom LLM with endpoint: %s", endpoint)
        return CustomLLMWrapper()

    @staticmethod
    def get_default_provider() -> str:
        """Get default LLM provider from environment.

        Returns:
            Provider name (defaults to 'ollama')
        """
        return os.getenv("LLM_PROVIDER", "ollama").lower()


# Convenience function for backward compatibility
def get_llm(provider: LLMProvider | str | None = None, **kwargs: Any) -> LLMInterface:
    """Get LLM instance with specified or default provider.

    Args:
        provider: LLM provider (defaults to Ollama)
        **kwargs: Provider-specific configuration

    Returns:
        LLM client instance

    Example:
        >>> # Use default (Ollama - your existing solution)
        >>> llm = get_llm()
        >>>
        >>> # Use custom endpoint
        >>> llm = get_llm("custom", endpoint="https://your-llm.com/api")
        >>>
        >>> # From environment
        >>> os.environ["LLM_PROVIDER"] = "ollama"
        >>> llm = get_llm()
    """
    if provider is None:
        provider = LLMFactory.get_default_provider()

    return LLMFactory.create_llm(provider, **kwargs)
