"""Anthropic-backed LLM client using direct HTTP API."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import anthropic

from heimdall.config import AdminConfig

from .base import LLMClient, LLMRunRequest

DEFAULT_MODEL = "claude-sonnet-4-20250514"

ORCHESTRATOR_TOOLS = [
    {
        "name": "Bash",
        "description": "Execute a shell command.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The shell command to execute.",
                }
            },
            "required": ["command"],
        },
    },
    {
        "name": "Read",
        "description": "Read a file from the filesystem.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the file to read."},
                "limit": {"type": "integer", "description": "Max characters to read."},
            },
            "required": ["path"],
        },
    },
    {
        "name": "Write",
        "description": "Write content to a file.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to write to."},
                "content": {"type": "string", "description": "Content to write."},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "Glob",
        "description": "Find files matching a glob pattern.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Glob pattern to match."},
            },
            "required": ["pattern"],
        },
    },
    {
        "name": "Grep",
        "description": "Search for a pattern in a file.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Pattern to search for."},
                "path": {"type": "string", "description": "File path to search in."},
            },
            "required": ["pattern", "path"],
        },
    },
]


def _resolve_api_key(env_name: str | None) -> str | None:
    if env_name:
        return os.environ.get(env_name)
    return os.environ.get("ANTHROPIC_API_KEY")


class AnthropicLLMClient(LLMClient):
    """Anthropic API client with tool calling support."""

    def __init__(self, config: AdminConfig) -> None:
        self.config = config
        api_key = _resolve_api_key(config.llm_api_key_env)
        if not api_key:
            raise RuntimeError(
                "Missing Anthropic API key. Set ANTHROPIC_API_KEY environment variable."
            )
        self.client = anthropic.AsyncAnthropic(api_key=api_key)

    async def run(self, request: LLMRunRequest) -> None:
        model = self._model_for_operation(request.operation)

        messages = []
        if request.system_prompt:
            messages.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": request.system_prompt + "\n\n" + request.prompt,
                        }
                    ],
                }
            )
        else:
            messages.append(
                {"role": "user", "content": [{"type": "text", "text": request.prompt}]}
            )

        max_iterations = 10
        for _ in range(max_iterations):
            response = await self.client.messages.create(
                model=model,
                max_tokens=4096,
                messages=messages,
                tools=ORCHESTRATOR_TOOLS,
            )

            # Collect text content to print
            text_blocks = []
            tool_use_blocks = []

            for block in response.content:
                if block.type == "text":
                    text_blocks.append(block.text)
                elif block.type == "tool_use":
                    tool_use_blocks.append(block)

            # Print text content
            for text in text_blocks:
                print(text)

            # If no tool calls, we're done
            if not tool_use_blocks:
                break

            # Process tool calls
            for block in tool_use_blocks:
                tool_name = block.name
                tool_input = block.input

                print(f"\n[tool:{tool_name}] ", end="", flush=True)

                result = await self._execute_tool(tool_name, tool_input)
                print(result[:200] + ("..." if len(result) > 200 else ""))

                # Add assistant message with tool use
                messages.append(
                    {
                        "role": "assistant",
                        "content": response.content,
                    }
                )

                # Add tool result
                messages.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": result,
                            }
                        ],
                    }
                )

    async def _execute_tool(self, name: str, args: dict) -> str:
        """Execute a tool and return the result."""
        if name == "Bash":
            command = args.get("command", "")
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                return f"Error: command timed out after 60 seconds"

            output = stdout.decode() + stderr.decode()
            return output or f"Command exited with code {proc.returncode}"

        elif name == "Read":
            return self._run_read(args)
        elif name == "Write":
            return await self._run_write(args)
        elif name == "Glob":
            return self._run_glob(args)
        elif name == "Grep":
            return self._run_grep(args)
        else:
            return f"Tool {name} is not supported."

    def _run_read(self, args: dict) -> str:
        from .openrouter_client import _validate_path

        path = args.get("path", "")
        if not path:
            return "Error: path is required"

        file_path, error = _validate_path(path)
        if error:
            return error
        if not file_path:
            return f"Error: path '{path}' is not allowed"
        if not file_path.exists():
            return f"Error: {path} not found"
        if not file_path.is_file():
            return f"Error: {path} is not a file"

        data = file_path.read_text(errors="ignore")
        limit = args.get("limit", 4000)
        return data[:limit]

    async def _run_write(self, args: dict) -> str:
        from .openrouter_client import _validate_path

        path = args.get("path", "")
        content = args.get("content", "")
        if not path:
            return "Error: path is required"

        file_path, error = _validate_path(path)
        if error:
            return error
        if not file_path:
            return f"Error: path '{path}' is not allowed"

        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content)
        return f"Wrote {len(content)} bytes to {path}"

    def _run_glob(self, args: dict) -> str:
        import glob
        from .openrouter_client import _validate_path

        pattern = args.get("pattern", "")
        if not pattern:
            return "Error: pattern is required"

        if ".." in pattern:
            return "Error: '..' not allowed in glob pattern"

        matches = glob.glob(pattern, recursive=True)
        validated = []
        for m in matches:
            file_path, error = _validate_path(m)
            if file_path:
                validated.append(m)
        return "\n".join(sorted(validated)) or "(no matches)"

    def _run_grep(self, args: dict) -> str:
        from .openrouter_client import _validate_path

        pattern = args.get("pattern", "")
        path = args.get("path", "")
        if not pattern or not path:
            return "Error: pattern and path are required"

        file_path, error = _validate_path(path)
        if error:
            return error
        if not file_path:
            return f"Error: path '{path}' is not allowed"
        if not file_path.exists():
            return f"Error: {path} not found"
        if not file_path.is_file():
            return f"Error: {path} is not a file"

        matches = []
        for line_no, line in enumerate(
            file_path.read_text(errors="ignore").splitlines(), start=1
        ):
            if pattern in line:
                matches.append(f"{line_no}: {line}")
        return "\n".join(matches) or "(no matches)"

    def _model_for_operation(self, operation: str) -> str:
        overrides = self.config.llm_model_overrides or {}
        return overrides.get(operation) or overrides.get("anthropic") or DEFAULT_MODEL
