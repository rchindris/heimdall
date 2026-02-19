"""Core orchestrator — builds agent options and runs commands."""

from __future__ import annotations

import json
from pathlib import Path

from claude_agent_sdk import (
    AgentDefinition,
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    query,
)

from .config import AdminConfig
from .hooks import build_hook_matchers, set_config
from .models import DriftReport, MachineProfile
from .modules.discovery import DISCOVERY_MODEL, DISCOVERY_SYSTEM_PROMPT, DISCOVERY_TOOLS
from .modules.guard import GUARD_MODEL, GUARD_SYSTEM_PROMPT, GUARD_TOOLS
from .modules.recipes import RECIPE_MODEL, RECIPE_SYSTEM_PROMPT, RECIPE_TOOLS
from .tools import ALL_ADMIN_TOOL_NAMES, create_admin_tools_server

# SDK built-in tools used by the orchestrator
ORCHESTRATOR_TOOLS = [
    "Bash",
    "Read",
    "Write",
    "Edit",
    "Glob",
    "Grep",
    "Task",
]


def _build_agents() -> dict[str, AgentDefinition]:
    """Build subagent definitions."""
    return {
        "discovery": AgentDefinition(
            description=(
                "Machine discovery agent that scans OS, hardware, packages, "
                "services, network, and users to build a complete machine profile."
            ),
            prompt=DISCOVERY_SYSTEM_PROMPT,
            tools=DISCOVERY_TOOLS,
            model=DISCOVERY_MODEL,
        ),
        "recipe-applier": AgentDefinition(
            description=(
                "Recipe applier agent that reads markdown recipes describing "
                "desired machine configuration and applies them step by step."
            ),
            prompt=RECIPE_SYSTEM_PROMPT,
            tools=RECIPE_TOOLS,
            model=RECIPE_MODEL,
        ),
        "guard": AgentDefinition(
            description=(
                "Drift detection agent that compares current machine state "
                "against recipe requirements and reports deviations."
            ),
            prompt=GUARD_SYSTEM_PROMPT,
            tools=GUARD_TOOLS,
            model=GUARD_MODEL,
        ),
    }


def build_options(
    config: AdminConfig,
    system_prompt: str = "",
) -> ClaudeAgentOptions:
    """Build ClaudeAgentOptions with all tools, hooks, and subagents configured."""
    set_config(config)

    admin_server = create_admin_tools_server()

    return ClaudeAgentOptions(
        system_prompt=system_prompt or None,
        model=config.model,
        permission_mode=config.permission_mode,
        max_budget_usd=config.max_budget_usd,
        allowed_tools=ORCHESTRATOR_TOOLS + ALL_ADMIN_TOOL_NAMES,
        mcp_servers={"admin": admin_server},
        agents=_build_agents(),
        hooks=build_hook_matchers(),
        cwd=str(Path.cwd()),
    )


def _load_profile(config: AdminConfig) -> MachineProfile | None:
    """Load the current machine profile if it exists."""
    profile_path = config.profiles_dir / "current.json"
    if profile_path.exists():
        data = json.loads(profile_path.read_text())
        return MachineProfile(**data)
    return None


async def run_init(config: AdminConfig) -> None:
    """Discover machine state and save profile."""
    profile = _load_profile(config)
    context = ""
    if profile:
        context = f"\n\nCurrent known profile:\n{profile.to_markdown()}"

    prompt = (
        "Discover this machine's complete state and save the profile to "
        f"{config.profiles_dir}/current.json. "
        "Use the discovery subagent to perform the scan."
        f"{context}"
    )

    options = build_options(config, system_prompt=(
        "You are Heimdall, an autonomous machine administration agent. "
        "Your task is to discover and inventory this machine's state."
    ))

    async for message in query(prompt=prompt, options=options):
        _print_message(message)


async def run_apply(config: AdminConfig, recipe_path: str, check: bool = False) -> None:
    """Apply a recipe to the machine."""
    profile = _load_profile(config)
    profile_context = f"\n\nCurrent machine profile:\n{profile.to_markdown()}" if profile else ""

    mode = "DRY RUN (--check)" if check else "APPLY"
    prompt = (
        f"[{mode}] Apply the recipe at '{recipe_path}' to this machine. "
        "Use the recipe-applier subagent to read and execute the recipe."
        f"{profile_context}"
    )
    if check:
        prompt += "\n\nThis is a dry run. Do NOT execute any changes, only report what would be done."

    options = build_options(config, system_prompt=(
        "You are Heimdall, an autonomous machine administration agent. "
        "Your task is to apply configuration recipes to this machine."
    ))

    async for message in query(prompt=prompt, options=options):
        _print_message(message)


async def run_scan(config: AdminConfig) -> None:
    """Quick profile update."""
    prompt = (
        "Perform a quick scan to update the machine profile at "
        f"{config.profiles_dir}/current.json. "
        "Use the discovery subagent for a focused update."
    )

    options = build_options(config, system_prompt=(
        "You are Heimdall, an autonomous machine administration agent. "
        "Perform a quick machine state update."
    ))

    async for message in query(prompt=prompt, options=options):
        _print_message(message)


async def run_guard(
    config: AdminConfig,
    recipe_path: str,
) -> None:
    """Check for drift from a recipe."""
    profile = _load_profile(config)
    profile_context = f"\n\nCurrent machine profile:\n{profile.to_markdown()}" if profile else ""

    prompt = (
        f"Check for drift from the recipe at '{recipe_path}'. "
        "Use the guard subagent to compare current state against recipe requirements. "
        f"Write the drift report to {config.profiles_dir}/drift-report.json."
        f"{profile_context}"
    )

    options = build_options(config, system_prompt=(
        "You are Heimdall, an autonomous machine administration agent. "
        "Your task is to detect configuration drift."
    ))

    async for message in query(prompt=prompt, options=options):
        _print_message(message)


def run_status(config: AdminConfig) -> None:
    """Show current profile and drift status."""
    profile = _load_profile(config)
    if not profile:
        print("No machine profile found. Run 'heimdall init' first.")
        return

    print(profile.to_markdown())

    drift_path = config.profiles_dir / "drift-report.json"
    if drift_path.exists():
        data = json.loads(drift_path.read_text())
        report = DriftReport(**data)
        print("\n" + report.to_markdown())
    else:
        print("\nNo drift report found. Run 'heimdall guard' to check for drift.")


def _print_message(message: object) -> None:
    """Print SDK messages in a human-readable format."""
    if isinstance(message, AssistantMessage):
        for block in message.content:
            if hasattr(block, "text"):
                print(block.text)
            elif hasattr(block, "name"):
                print(f"  [tool] {block.name}")
    elif isinstance(message, ResultMessage):
        print(f"\n--- {message.subtype} ---")
