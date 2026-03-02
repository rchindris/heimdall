"""Security and audit hooks for Heimdall.

PreToolUse hooks:
  - Bash allowlist: validates command prefixes and rejects shell metacharacters.
  - MCP input validation: validates package/service names for MCP tools.
PostToolUse hook: audit logging for all tool invocations.
"""

from __future__ import annotations

import json
import os
import re
import shlex
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from claude_agent_sdk import HookMatcher

from .config import AdminConfig

# Shell metacharacters that indicate command chaining, pipes, or subshells.
# Commands containing these are denied even if the first token is on the allowlist.
_SHELL_METACHAR_RE = re.compile(
    r"[;|&`\n]"       # semicolon, pipe, ampersand, backtick, newline
    r"|\$\("          # $( command substitution
    r"|>\s*>"         # >> append redirect
    r"|>\s*[^&]"      # > redirect (but not >&)
    r"|<\("           # <( process substitution
    r"|\|\|"          # || or chain
    r"|&&"            # && and chain
    r"|[{}]"          # brace expansion
)

# Dangerous environment variables that must not be set via env prefix
_DANGEROUS_ENV_VARS = frozenset({
    "LD_PRELOAD", "LD_LIBRARY_PATH", "DYLD_INSERT_LIBRARIES",
    "DYLD_LIBRARY_PATH", "PYTHONPATH", "PERL5LIB", "RUBYLIB",
    "NODE_PATH", "CLASSPATH", "PATH",
})

_DRY_RUN_DENY_TOOLS = frozenset({"Bash", "Write", "Edit"})
_DRY_RUN_ALLOWED_ADMIN_TOOLS = frozenset({
    "mcp__admin__list_packages",
    "mcp__admin__query_package",
    "mcp__admin__service_status",
})


async def bash_allowlist_hook(
    input_data: dict[str, Any],
    tool_use_id: str | None,
    context: Any,
) -> dict[str, Any]:
    """PreToolUse hook: allowlist-based command filtering for Bash.

    Security layers:
    1. Reject commands with shell metacharacters (;, |, &&, $(), etc.)
    2. Reject dangerous environment variable assignments (LD_PRELOAD, PATH, etc.)
    3. Check the primary command token against the allowlist
    4. Deny (not ask) commands not on the allowlist
    """
    if input_data.get("hook_event_name") != "PreToolUse":
        return {}

    if input_data.get("tool_name") != "Bash":
        return {}

    command = input_data.get("tool_input", {}).get("command", "")
    allowed = _config_ref.allowed_command_prefixes if _config_ref else []

    # Layer 1: Reject shell metacharacters
    if _SHELL_METACHAR_RE.search(command):
        return _deny(
            input_data,
            "Command contains shell metacharacters (;, |, &&, $(), >, etc.) "
            "which are not allowed. Use separate commands instead.",
        )

    # Layer 2: Parse command tokens (deny on parse failure)
    try:
        tokens = shlex.split(command)
    except ValueError as e:
        return _deny(input_data, f"Malformed command (shlex parse error: {e})")

    if not tokens:
        return _deny(input_data, "Empty command")

    # Layer 3: Check for dangerous env vars
    first_cmd = None
    has_sudo = False
    for token in tokens:
        if "=" in token and not token.startswith("-"):
            var_name = token.split("=", 1)[0]
            if var_name in _DANGEROUS_ENV_VARS:
                return _deny(
                    input_data,
                    f"Setting dangerous environment variable '{var_name}' is not allowed.",
                )
            continue
        if token == "env":
            continue
        if token == "sudo":
            has_sudo = True
            continue
        first_cmd = token
        break

    if first_cmd is None:
        first_cmd = tokens[0]

    # Layer 4: Check allowlist
    if first_cmd not in allowed:
        return _deny(
            input_data,
            f"Command '{first_cmd}' is not on the allowlist.",
        )

    reason = f"Command '{first_cmd}' is on the allowlist"
    if has_sudo:
        reason += " (running with sudo)"

    return {
        "hookSpecificOutput": {
            "hookEventName": input_data["hook_event_name"],
            "permissionDecision": "allow",
            "permissionDecisionReason": reason,
        }
    }


async def mcp_input_validation_hook(
    input_data: dict[str, Any],
    tool_use_id: str | None,
    context: Any,
) -> dict[str, Any]:
    """PreToolUse hook: validate MCP tool inputs for safety."""
    if input_data.get("hook_event_name") != "PreToolUse":
        return {}

    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})

    # Only validate MCP admin tools that take a 'name' parameter
    if not tool_name.startswith("mcp__admin__"):
        return {}

    name = tool_input.get("name", "")
    if not name:
        # Tools like list_packages don't require a name
        return {}

    # Validate name against injection
    safe_re = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._+\-]*$")
    if not safe_re.match(name) or len(name) > 256:
        return _deny(
            input_data,
            f"Invalid name parameter: {name!r}. "
            "Only alphanumeric, dots, hyphens, underscores, and plus signs allowed.",
        )

    return {}


async def audit_log_hook(
    input_data: dict[str, Any],
    tool_use_id: str | None,
    context: Any,
) -> dict[str, Any]:
    """PostToolUse hook: log every tool invocation to the audit log."""
    if input_data.get("hook_event_name") != "PostToolUse":
        return {}

    log_path = _config_ref.audit_log_path if _config_ref else _default_audit_path()
    log_path.parent.mkdir(parents=True, exist_ok=True)

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "tool_name": input_data.get("tool_name", ""),
        "tool_use_id": tool_use_id,
        "input": _summarize_input(input_data.get("tool_input", {})),
    }

    fd = os.open(str(log_path), os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    try:
        os.write(fd, (json.dumps(entry) + "\n").encode())
    finally:
        os.close(fd)

    return {}


# --- Module-level config reference (set by agent.py before use) ---

_config_ref: AdminConfig | None = None


def set_config(config: AdminConfig) -> None:
    """Set the config reference used by hooks."""
    global _config_ref
    _config_ref = config


def build_hook_matchers() -> dict[str, list[HookMatcher]]:
    """Build the hooks dict for ClaudeAgentOptions."""
    return {
        "PreToolUse": [
            HookMatcher(hooks=[dry_run_guard_hook]),
            HookMatcher(matcher="Bash", hooks=[bash_allowlist_hook]),
            HookMatcher(matcher="^mcp__admin__", hooks=[mcp_input_validation_hook]),
        ],
        "PostToolUse": [
            HookMatcher(hooks=[audit_log_hook]),
        ],
    }


# --- Helpers ---


def _deny(input_data: dict[str, Any], reason: str) -> dict[str, Any]:
    """Build a deny response."""
    return {
        "hookSpecificOutput": {
            "hookEventName": input_data["hook_event_name"],
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }


def _summarize_input(tool_input: dict[str, Any], max_len: int = 2000) -> str:
    """Create a summary of tool input for the audit log.

    Uses a generous limit to preserve forensic evidence.
    """
    text = json.dumps(tool_input)
    if len(text) > max_len:
        return text[:max_len] + "..."
    return text


def _default_audit_path() -> Path:
    return Path.home() / ".local" / "share" / "heimdall" / "audit.log"


_dry_run_mode: bool = False


async def dry_run_guard_hook(
    input_data: dict[str, Any],
    tool_use_id: str | None,
    context: Any,
) -> dict[str, Any]:
    """PreToolUse hook: block mutating tools while in dry-run mode."""

    if input_data.get("hook_event_name") != "PreToolUse" or not _dry_run_mode:
        return {}

    tool_name = input_data.get("tool_name", "")

    if tool_name in _DRY_RUN_DENY_TOOLS:
        return _deny(
            input_data,
            "Dry-run mode blocks tool usage. Provide a plan instead of executing changes.",
        )

    if tool_name.startswith("mcp__admin__") and tool_name not in _DRY_RUN_ALLOWED_ADMIN_TOOLS:
        return _deny(
            input_data,
            "Dry-run mode blocks administrative actions that mutate the system.",
        )

    return {}


def set_dry_run_mode(enabled: bool) -> None:
    """Enable or disable dry-run enforcement for tool usage."""

    global _dry_run_mode
    _dry_run_mode = enabled
