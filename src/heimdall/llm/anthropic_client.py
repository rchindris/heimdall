"""Anthropic-backed LLM client using claude_agent_sdk."""

from __future__ import annotations

from pathlib import Path
from typing import AsyncIterator

from claude_agent_sdk import (
    AgentDefinition,
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    query,
)

from heimdall.config import AdminConfig
from heimdall.hooks import build_hook_matchers
from heimdall.modules.discovery import (
    DISCOVERY_MODEL,
    DISCOVERY_SYSTEM_PROMPT,
    DISCOVERY_TOOLS,
)
from heimdall.modules.guard import GUARD_MODEL, GUARD_SYSTEM_PROMPT, GUARD_TOOLS
from heimdall.modules.recipes import RECIPE_MODEL, RECIPE_SYSTEM_PROMPT, RECIPE_TOOLS
from heimdall.tools import ALL_ADMIN_TOOL_NAMES, create_admin_tools_server

from .base import LLMClient, LLMRunRequest


ORCHESTRATOR_TOOLS = [
    "Bash",
    "Read",
    "Write",
    "Edit",
    "Glob",
    "Grep",
    "Task",
]


class AnthropicLLMClient(LLMClient):
    """Thin wrapper around claude_agent_sdk to satisfy the LLMClient protocol."""

    def __init__(self, config: AdminConfig) -> None:
        self.config = config

    async def run(self, request: LLMRunRequest) -> None:
        options = self._build_options(
            system_prompt=request.system_prompt,
            model_override=self._model_for_operation(request.operation),
        )
        async for message in query(prompt=request.prompt, options=options):
            self._print_message(message)

    # --- helpers -----------------------------------------------------------------

    def _model_for_operation(self, operation: str) -> str:
        overrides = self.config.llm_model_overrides or {}
        return (
            overrides.get(operation)
            or overrides.get("orchestrator")
            or self.config.model
        )

    def _agent_model(self, key: str, default: str) -> str:
        overrides = self.config.llm_model_overrides or {}
        return overrides.get(key, default)

    def _build_agents(self) -> dict[str, AgentDefinition]:
        return {
            "discovery": AgentDefinition(
                description=(
                    "Machine discovery agent that scans OS, hardware, packages, "
                    "services, network, and users to build a complete machine profile."
                ),
                prompt=DISCOVERY_SYSTEM_PROMPT,
                tools=DISCOVERY_TOOLS,
                model=self._agent_model("discovery", DISCOVERY_MODEL),
            ),
            "recipe-applier": AgentDefinition(
                description=(
                    "Recipe applier agent that reads markdown recipes describing "
                    "desired machine configuration and applies them step by step."
                ),
                prompt=RECIPE_SYSTEM_PROMPT,
                tools=RECIPE_TOOLS,
                model=self._agent_model("recipes", RECIPE_MODEL),
            ),
            "guard": AgentDefinition(
                description=(
                    "Drift detection agent that compares current machine state "
                    "against recipe requirements and reports deviations."
                ),
                prompt=GUARD_SYSTEM_PROMPT,
                tools=GUARD_TOOLS,
                model=self._agent_model("guard", GUARD_MODEL),
            ),
        }

    def _build_options(
        self,
        system_prompt: str | None,
        model_override: str | None,
    ) -> ClaudeAgentOptions:
        admin_server = create_admin_tools_server()

        return ClaudeAgentOptions(
            system_prompt=system_prompt or None,
            model=model_override or self.config.model,
            permission_mode=self.config.permission_mode,
            max_budget_usd=self.config.max_budget_usd,
            allowed_tools=ORCHESTRATOR_TOOLS + ALL_ADMIN_TOOL_NAMES,
            mcp_servers={"admin": admin_server},
            agents=self._build_agents(),
            hooks=build_hook_matchers(),
            cwd=str(Path.cwd()),
        )

    def _print_message(self, message: object) -> None:
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if hasattr(block, "text"):
                    print(block.text)
                elif hasattr(block, "name"):
                    print(f"  [tool] {block.name}")
        elif isinstance(message, ResultMessage):
            print(f"\n--- {message.subtype} ---")
