"""Cross-distro service management MCP tools."""

from __future__ import annotations

import functools
import shlex
import shutil

from claude_agent_sdk import tool

from ._common import run_cmd, validate_name


@functools.cache
def _detect_service_manager() -> str:
    """Detect the available service manager (cached for session lifetime)."""
    if shutil.which("systemctl"):
        return "systemd"
    if shutil.which("launchctl"):
        return "launchd"
    if shutil.which("service"):
        return "sysvinit"
    return "unknown"


@tool(
    "enable_service",
    "Enable a system service to start on boot",
    {"name": str},
)
async def enable_service(args: dict) -> dict:
    name = args["name"]
    try:
        validate_name(name, "service")
    except ValueError as e:
        return {"content": [{"type": "text", "text": f"Error: {e}"}]}
    cmd = _build_cmd(_detect_service_manager(), "enable", name)
    if not cmd:
        text = f"Error: cannot enable services with {_detect_service_manager()}"
    else:
        text = await run_cmd(cmd)
    return {"content": [{"type": "text", "text": text}]}


@tool(
    "disable_service",
    "Disable a system service from starting on boot",
    {"name": str},
)
async def disable_service(args: dict) -> dict:
    name = args["name"]
    try:
        validate_name(name, "service")
    except ValueError as e:
        return {"content": [{"type": "text", "text": f"Error: {e}"}]}
    cmd = _build_cmd(_detect_service_manager(), "disable", name)
    if not cmd:
        text = f"Error: cannot disable services with {_detect_service_manager()}"
    else:
        text = await run_cmd(cmd)
    return {"content": [{"type": "text", "text": text}]}


@tool(
    "start_service",
    "Start a system service",
    {"name": str},
)
async def start_service(args: dict) -> dict:
    name = args["name"]
    try:
        validate_name(name, "service")
    except ValueError as e:
        return {"content": [{"type": "text", "text": f"Error: {e}"}]}
    cmd = _build_cmd(_detect_service_manager(), "start", name)
    if not cmd:
        text = f"Error: cannot start services with {_detect_service_manager()}"
    else:
        text = await run_cmd(cmd)
    return {"content": [{"type": "text", "text": text}]}


@tool(
    "stop_service",
    "Stop a system service",
    {"name": str},
)
async def stop_service(args: dict) -> dict:
    name = args["name"]
    try:
        validate_name(name, "service")
    except ValueError as e:
        return {"content": [{"type": "text", "text": f"Error: {e}"}]}
    cmd = _build_cmd(_detect_service_manager(), "stop", name)
    if not cmd:
        text = f"Error: cannot stop services with {_detect_service_manager()}"
    else:
        text = await run_cmd(cmd)
    return {"content": [{"type": "text", "text": text}]}


@tool(
    "service_status",
    "Check the status of a system service",
    {"name": str},
)
async def service_status(args: dict) -> dict:
    name = args["name"]
    try:
        validate_name(name, "service")
    except ValueError as e:
        return {"content": [{"type": "text", "text": f"Error: {e}"}]}
    cmd = _build_cmd(_detect_service_manager(), "status", name)
    if not cmd:
        text = f"Error: cannot query services with {_detect_service_manager()}"
    else:
        text = await run_cmd(cmd)
    return {"content": [{"type": "text", "text": text}]}


def _build_cmd(mgr: str, action: str, name: str) -> str | None:
    """Build a service management command with safe quoting."""
    safe = shlex.quote(name)
    if mgr == "systemd":
        return f"systemctl {action} {safe}"
    elif mgr == "launchd":
        # Modern macOS: use bootstrap/bootout for start/stop, enable/disable for boot
        launchd_actions = {
            "start": f"launchctl bootstrap system /Library/LaunchDaemons/{safe}.plist",
            "stop": f"launchctl bootout system /Library/LaunchDaemons/{safe}.plist",
            "enable": f"launchctl enable system/{safe}",
            "disable": f"launchctl disable system/{safe}",
            "status": f"launchctl list | grep -F {safe}",
        }
        return launchd_actions.get(action)
    elif mgr == "sysvinit":
        sysvinit_actions = {
            "start": f"service {safe} start",
            "stop": f"service {safe} stop",
            "status": f"service {safe} status",
            "enable": f"update-rc.d {safe} defaults",
            "disable": f"update-rc.d {safe} remove",
        }
        return sysvinit_actions.get(action)
    return None


ALL_SERVICE_TOOLS = [
    enable_service,
    disable_service,
    start_service,
    stop_service,
    service_status,
]
