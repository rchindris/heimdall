"""Cross-distro package management MCP tools."""

from __future__ import annotations

import functools
import shlex
import shutil

from claude_agent_sdk import tool

from ._common import run_cmd, validate_name

_MANAGER_COMMANDS = {
    "apt": "apt-get",
    "dnf": "dnf",
    "pacman": "pacman",
    "brew": "brew",
}


@functools.cache
def _detect_manager() -> str:
    """Detect the available package manager (cached for session lifetime)."""
    for name, cmd in _MANAGER_COMMANDS.items():
        if shutil.which(cmd):
            return name
    return "unknown"


@tool(
    "install_package",
    "Install a system package using the detected package manager",
    {"name": str},
)
async def install_package(args: dict) -> dict:
    name = args["name"]
    try:
        validate_name(name, "package")
    except ValueError as e:
        return {"content": [{"type": "text", "text": f"Error: {e}"}]}

    mgr = _detect_manager()
    cmd = _build_install_cmd(mgr, name)
    if not cmd:
        text = f"Error: no supported package manager found (detected: {mgr})"
    else:
        text = await run_cmd(cmd)
    return {"content": [{"type": "text", "text": text}]}


@tool(
    "remove_package",
    "Remove a system package using the detected package manager",
    {"name": str},
)
async def remove_package(args: dict) -> dict:
    name = args["name"]
    try:
        validate_name(name, "package")
    except ValueError as e:
        return {"content": [{"type": "text", "text": f"Error: {e}"}]}

    mgr = _detect_manager()
    cmd = _build_remove_cmd(mgr, name)
    if not cmd:
        text = f"Error: no supported package manager found (detected: {mgr})"
    else:
        text = await run_cmd(cmd)
    return {"content": [{"type": "text", "text": text}]}


@tool(
    "list_packages",
    "List all installed packages with their versions",
    {},
)
async def list_packages(args: dict) -> dict:
    mgr = _detect_manager()
    cmds = {
        "apt": "dpkg-query -W -f='${Package}\\t${Version}\\n'",
        "dnf": "dnf list installed",
        "pacman": "pacman -Q",
        "brew": "brew list --versions",
    }
    cmd = cmds.get(mgr)
    if not cmd:
        text = f"Error: no supported package manager found (detected: {mgr})"
    else:
        text = await run_cmd(cmd)
    return {"content": [{"type": "text", "text": text}]}


@tool(
    "query_package",
    "Query information about a specific package",
    {"name": str},
)
async def query_package(args: dict) -> dict:
    name = args["name"]
    try:
        validate_name(name, "package")
    except ValueError as e:
        return {"content": [{"type": "text", "text": f"Error: {e}"}]}

    mgr = _detect_manager()
    safe = shlex.quote(name)
    cmds = {
        "apt": f"apt-cache show {safe}",
        "dnf": f"dnf info {safe}",
        "pacman": f"pacman -Qi {safe}",
        "brew": f"brew info {safe}",
    }
    cmd = cmds.get(mgr)
    if not cmd:
        text = f"Error: no supported package manager found (detected: {mgr})"
    else:
        text = await run_cmd(cmd)
    return {"content": [{"type": "text", "text": text}]}


def _build_install_cmd(mgr: str, name: str) -> str | None:
    safe = shlex.quote(name)
    cmds = {
        "apt": f"apt-get install -y {safe}",
        "dnf": f"dnf install -y {safe}",
        "pacman": f"pacman -S --noconfirm {safe}",
        "brew": f"brew install {safe}",
    }
    return cmds.get(mgr)


def _build_remove_cmd(mgr: str, name: str) -> str | None:
    safe = shlex.quote(name)
    cmds = {
        "apt": f"apt-get remove -y {safe}",
        "dnf": f"dnf remove -y {safe}",
        "pacman": f"pacman -R --noconfirm {safe}",
        "brew": f"brew uninstall {safe}",
    }
    return cmds.get(mgr)


ALL_PACKAGE_TOOLS = [install_package, remove_package, list_packages, query_package]
