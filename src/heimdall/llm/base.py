"""Base definitions for LLM providers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol


LLMOperation = Literal["init", "apply", "scan", "guard"]


@dataclass(slots=True)
class LLMRunRequest:
    """Standardized request passed to an LLM provider."""

    operation: LLMOperation
    prompt: str
    system_prompt: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class LLMClient(Protocol):
    """Interface all provider implementations must follow."""

    async def run(self, request: LLMRunRequest) -> None:  # pragma: no cover - protocol
        """Execute the request and stream output directly to stdout."""
        raise NotImplementedError
