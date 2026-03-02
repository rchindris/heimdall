"""LLM provider factory."""

from __future__ import annotations

from heimdall.config import AdminConfig

from .anthropic_client import AnthropicLLMClient
from .base import LLMClient
from .openrouter_client import OpenRouterLLMClient


def create_llm_client(config: AdminConfig) -> LLMClient:
    """Return the appropriate LLM client based on config."""

    provider = (config.llm_provider or "anthropic").lower()
    if provider == "anthropic":
        return AnthropicLLMClient(config)
    if provider == "openrouter":
        return OpenRouterLLMClient(config)
    raise ValueError(f"Unsupported LLM provider: {config.llm_provider}")
