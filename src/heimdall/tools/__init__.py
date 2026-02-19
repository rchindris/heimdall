"""Custom MCP tools for Heimdall.

Creates an in-process SDK MCP server with package and service management tools.
The SDK references these as mcp__admin__<tool_name>.
"""

from __future__ import annotations

from claude_agent_sdk import create_sdk_mcp_server

from .package_manager import ALL_PACKAGE_TOOLS
from .service_manager import ALL_SERVICE_TOOLS


def create_admin_tools_server() -> dict:
    """Create the admin MCP server config for ClaudeAgentOptions.mcp_servers."""
    return create_sdk_mcp_server(
        name="admin",
        version="0.1.0",
        tools=ALL_PACKAGE_TOOLS + ALL_SERVICE_TOOLS,
    )


# Derive MCP tool names programmatically from the registered tools.
# The SDK exposes them as mcp__<server>__<tool_name>.
_ALL_TOOLS = ALL_PACKAGE_TOOLS + ALL_SERVICE_TOOLS
ALL_ADMIN_TOOL_NAMES = [f"mcp__admin__{t.name}" for t in _ALL_TOOLS]
