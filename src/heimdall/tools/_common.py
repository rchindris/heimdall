"""Shared utilities for MCP tools."""

from __future__ import annotations

import asyncio
import re
import shlex

# Strict validation: only alphanumeric, dots, hyphens, underscores, plus signs.
# This covers all valid package and service names across apt/dnf/pacman/brew/systemd/launchd.
_SAFE_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._+\-]*$")


def validate_name(name: str, kind: str = "package") -> str:
    """Validate a package or service name against shell injection.

    Raises ValueError if the name contains unsafe characters.
    """
    if not name:
        raise ValueError(f"Empty {kind} name")
    if len(name) > 256:
        raise ValueError(f"{kind.title()} name too long (max 256 chars)")
    if not _SAFE_NAME_RE.match(name):
        raise ValueError(
            f"Invalid {kind} name: {name!r}. "
            f"Only alphanumeric characters, dots, hyphens, underscores, "
            f"and plus signs are allowed."
        )
    return name


async def run_cmd(cmd: str, timeout: int = 60) -> str:
    """Run a shell command and return its output."""
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        return f"Error: command timed out after {timeout} seconds"

    output = stdout.decode() + stderr.decode()
    if proc.returncode != 0:
        return f"Error (exit {proc.returncode}):\n{output}"
    return output
