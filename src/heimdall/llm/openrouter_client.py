"""OpenRouter-backed LLM client with basic tool-calling support."""

from __future__ import annotations

import asyncio
import glob
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict

import httpx

from heimdall.config import AdminConfig
from heimdall.hooks import (
    audit_log_hook,
    bash_allowlist_hook,
    dry_run_guard_hook,
    mcp_input_validation_hook,
)
import heimdall.tools.package_manager as pkg_mgr
import heimdall.tools.service_manager as svc_mgr

from .base import LLMClient, LLMRunRequest


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]


class ToolExecutor:
    """Executes tool calls locally while honoring Heimdall hooks."""

    def __init__(self, config: AdminConfig) -> None:
        self.config = config
        self.mcp_handlers = {
            "mcp__admin__install_package",
            "mcp__admin__remove_package",
            "mcp__admin__list_packages",
            "mcp__admin__query_package",
            "mcp__admin__enable_service",
            "mcp__admin__disable_service",
            "mcp__admin__start_service",
            "mcp__admin__stop_service",
            "mcp__admin__service_status",
        }

    async def run(self, name: str, args: dict[str, Any]) -> str:
        pre_ctx = {"hook_event_name": "PreToolUse", "tool_name": name, "tool_input": args}
        hook = await dry_run_guard_hook(pre_ctx, None, {})
        if _is_denied(hook):
            return _denial_reason(hook)

        if name == "Bash":
            return await self._run_bash(args)
        if name == "Read":
            return self._run_read(args)
        if name == "Write":
            return await self._run_write(args)
        if name == "Glob":
            return self._run_glob(args)
        if name == "Grep":
            return self._run_grep(args)
        if name in self.mcp_handlers:
            return await self._run_mcp_tool(name, args)
        return f"Tool {name} is not supported by the OpenRouter provider."

    async def _run_bash(self, args: dict[str, Any]) -> str:
        command = args.get("command", "").strip()
        if not command:
            return "Error: command cannot be empty"

        hook = await bash_allowlist_hook(
            {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": command}},
            None,
            {},
        )
        if _is_denied(hook):
            return _denial_reason(hook)

        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        output = stdout.decode() + stderr.decode()
        await audit_log_hook(
            {"hook_event_name": "PostToolUse", "tool_name": "Bash", "tool_input": {"command": command}},
            None,
            {},
        )
        return output or f"Command exited with code {proc.returncode}"

    def _run_read(self, args: dict[str, Any]) -> str:
        path = args.get("path")
        if not path:
            return "Error: path is required"
        file_path = Path(path)
        if not file_path.exists():
            return f"Error: {path} not found"
        data = file_path.read_text(errors="ignore")
        limit = int(args.get("limit", 4000))
        return data[:limit]

    async def _run_write(self, args: dict[str, Any]) -> str:
        path = args.get("path")
        content = args.get("content", "")
        if not path:
            return "Error: path is required"
        file_path = Path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content)
        await audit_log_hook(
            {"hook_event_name": "PostToolUse", "tool_name": "Write", "tool_input": {"path": path}},
            None,
            {},
        )
        return f"Wrote {len(content)} bytes to {path}"

    def _run_glob(self, args: dict[str, Any]) -> str:
        pattern = args.get("pattern", "")
        if not pattern:
            return "Error: pattern is required"
        matches = sorted(glob.glob(pattern, recursive=True))
        return "\n".join(matches) or "(no matches)"

    def _run_grep(self, args: dict[str, Any]) -> str:
        pattern = args.get("pattern", "")
        path = args.get("path", "")
        if not pattern or not path:
            return "Error: pattern and path are required"
        file_path = Path(path)
        if not file_path.exists():
            return f"Error: {path} not found"
        matches = []
        for line_no, line in enumerate(file_path.read_text(errors="ignore").splitlines(), start=1):
            if pattern in line:
                matches.append(f"{line_no}: {line}")
        return "\n".join(matches) or "(no matches)"

    async def _run_mcp_tool(self, name: str, args: dict[str, Any]) -> str:
        hook = await mcp_input_validation_hook(
            {"hook_event_name": "PreToolUse", "tool_name": name, "tool_input": args},
            None,
            {},
        )
        if _is_denied(hook):
            return _denial_reason(hook)
        
        # Map tool name to handler function
        handlers = {
            "mcp__admin__install_package": pkg_mgr.install_package,
            "mcp__admin__remove_package": pkg_mgr.remove_package,
            "mcp__admin__list_packages": pkg_mgr.list_packages,
            "mcp__admin__query_package": pkg_mgr.query_package,
            "mcp__admin__enable_service": svc_mgr.enable_service,
            "mcp__admin__disable_service": svc_mgr.disable_service,
            "mcp__admin__start_service": svc_mgr.start_service,
            "mcp__admin__stop_service": svc_mgr.stop_service,
            "mcp__admin__service_status": svc_mgr.service_status,
        }
        
        handler = handlers.get(name)
        if not handler:
            return f"Unknown MCP tool: {name}"
        
        # The @tool decorator wraps the function, call the underlying __call__
        if hasattr(handler, "__call__"):
            result = await handler(args)
        else:
            return f"Tool {name} is not callable"
            
        text_blocks = [block.get("text", "") for block in result.get("content", []) if block.get("type") == "text"]
        await audit_log_hook(
            {"hook_event_name": "PostToolUse", "tool_name": name, "tool_input": args},
            None,
            {},
        )
        return "\n".join(text_blocks) or "(no output)"


class OpenRouterLLMClient(LLMClient):
    """OpenRouter implementation supporting function/tool calls via chat completions."""

    def __init__(self, config: AdminConfig) -> None:
        self.config = config
        self.tool_executor = ToolExecutor(config)

    async def run(self, request: LLMRunRequest) -> None:
        api_key = _resolve_api_key(
            self.config.llm_api_key_env
            or self.config.openrouter_api_key_env
            or "OPENROUTER_API_KEY"
        )
        if not api_key:
            raise RuntimeError(
                "Missing OpenRouter API key. Set the OPENROUTER_API_KEY environment variable "
                "or configure llm_api_key_env."
            )

        headers = {
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": self.config.openrouter_referer or "https://github.com/anthropics/heimdall",
            "X-Title": self.config.openrouter_title or "Heimdall",
        }

        messages: list[dict[str, Any]] = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.append({"role": "user", "content": request.prompt})

        model = self._model_for_operation(request.operation)
        base_url = self.config.openrouter_base_url.rstrip("/")
        tool_defs = self._tool_definitions()

        async with httpx.AsyncClient(base_url=base_url, timeout=60) as client:
            while True:
                payload = {
                    "model": model,
                    "messages": messages,
                    "tools": tool_defs,
                    "tool_choice": "auto",
                    "temperature": self.config.openrouter_temperature,
                }
                try:
                    response = await client.post("/chat/completions", json=payload, headers=headers)
                    response.raise_for_status()
                    data = response.json()
                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 401:
                        raise RuntimeError(
                            "OpenRouter authentication failed. Check your OPENROUTER_API_KEY environment variable."
                        ) from e
                    elif e.response.status_code == 429:
                        raise RuntimeError(
                            "OpenRouter rate limit exceeded. Try again later or upgrade your plan."
                        ) from e
                    elif e.response.status_code >= 500:
                        raise RuntimeError(
                            f"OpenRouter server error: {e.response.text[:500]}"
                        ) from e
                    else:
                        raise RuntimeError(
                            f"OpenRouter API error ({e.response.status_code}): {e.response.text[:500]}"
                        ) from e
                choice = data["choices"][0]
                message = choice["message"]

                tool_calls = message.get("tool_calls") or []
                if tool_calls:
                    messages.append(message)
                    for call in tool_calls:
                        tool_name = call["function"]["name"]
                        args_json = call["function"].get("arguments") or "{}"
                        try:
                            tool_args = json.loads(args_json)
                        except json.JSONDecodeError:
                            tool_args = {}
                        result = await self.tool_executor.run(tool_name, tool_args)
                        print(f"  [tool:{tool_name}] {result[:2000]}")
                        messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": call.get("id") or tool_name,
                                "name": tool_name,
                                "content": result,
                            }
                        )
                    continue

                content = message.get("content")
                if isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "output_text":
                            print(block.get("text", ""))
                        elif isinstance(block, dict):
                            print(block.get("text", ""))
                elif isinstance(content, str):
                    print(content)
                break

    # --- helpers -----------------------------------------------------------------

    def _model_for_operation(self, operation: str) -> str:
        overrides = self.config.llm_model_overrides or {}
        return (
            overrides.get(operation)
            or overrides.get("openrouter")
            or self.config.openrouter_model
        )

    def _tool_definitions(self) -> list[dict[str, Any]]:
        return [
            _tool("Bash", "Execute an allowlisted shell command.", {"command": _string_schema()}),
            _tool("Read", "Read a text file (first 4000 chars).", {"path": _string_schema(), "limit": {"type": "integer"}}),
            _tool("Write", "Overwrite a text file with provided content.", {"path": _string_schema(), "content": _string_schema()}),
            _tool("Glob", "Find files matching a glob pattern.", {"pattern": _string_schema()}),
            _tool("Grep", "Search for a literal pattern within a file.", {"path": _string_schema(), "pattern": _string_schema()}),
            *_mcp_tool_specs(),
        ]


def _tool(name: str, description: str, properties: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": list(properties.keys()),
            },
        },
    }


def _mcp_tool_specs() -> list[dict[str, Any]]:
    tools: list[tuple[str, str, bool]] = [
        ("mcp__admin__install_package", "Install a package using the native package manager.", True),
        ("mcp__admin__remove_package", "Remove a package.", True),
        ("mcp__admin__list_packages", "List installed packages.", False),
        ("mcp__admin__query_package", "Show detailed information about a package.", True),
        ("mcp__admin__enable_service", "Enable a system service.", True),
        ("mcp__admin__disable_service", "Disable a system service.", True),
        ("mcp__admin__start_service", "Start a system service.", True),
        ("mcp__admin__stop_service", "Stop a system service.", True),
        ("mcp__admin__service_status", "Check status of a system service.", True),
    ]
    specs: list[dict[str, Any]] = []
    for name, desc, requires_name in tools:
        params: dict[str, Any] = {
            "type": "object",
            "properties": {"name": _string_schema()},
            "required": ["name"],
        }
        if not requires_name:
            params["required"] = []
        specs.append(
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": desc,
                    "parameters": params,
                },
            }
        )
    return specs


def _string_schema() -> dict[str, str]:
    return {"type": "string"}


def _is_denied(result: dict[str, Any] | None) -> bool:
    if not result:
        return False
    decision = result.get("hookSpecificOutput", {}).get("permissionDecision")
    return decision == "deny"


def _denial_reason(result: dict[str, Any] | None) -> str:
    if not result:
        return "Denied"
    return result.get("hookSpecificOutput", {}).get("permissionDecisionReason", "Denied")


def _resolve_api_key(env_name: str | None) -> str | None:
    if env_name:
        return os.environ.get(env_name)
    return None
