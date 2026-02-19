"""Tests for agent definitions."""

from heimdall.modules.discovery import (
    DISCOVERY_MODEL,
    DISCOVERY_SYSTEM_PROMPT,
    DISCOVERY_TOOLS,
)
from heimdall.modules.guard import (
    GUARD_MODEL,
    GUARD_SYSTEM_PROMPT,
    GUARD_TOOLS,
)
from heimdall.modules.recipes import (
    RECIPE_MODEL,
    RECIPE_SYSTEM_PROMPT,
    RECIPE_TOOLS,
)
from heimdall.tools import ALL_ADMIN_TOOL_NAMES


class TestDiscoveryAgent:
    def test_has_system_prompt(self):
        assert len(DISCOVERY_SYSTEM_PROMPT) > 100

    def test_tools_include_bash(self):
        assert "Bash" in DISCOVERY_TOOLS

    def test_tools_include_mcp(self):
        assert "mcp__admin__list_packages" in DISCOVERY_TOOLS
        assert "mcp__admin__service_status" in DISCOVERY_TOOLS

    def test_no_task_tool(self):
        """Subagents must not have the Task tool (no recursive spawning)."""
        assert "Task" not in DISCOVERY_TOOLS

    def test_model(self):
        assert DISCOVERY_MODEL == "haiku"


class TestRecipeAgent:
    def test_has_system_prompt(self):
        assert len(RECIPE_SYSTEM_PROMPT) > 100

    def test_tools_include_edit(self):
        assert "Edit" in RECIPE_TOOLS

    def test_tools_include_all_mcp(self):
        mcp_tools = [t for t in RECIPE_TOOLS if t.startswith("mcp__")]
        assert len(mcp_tools) == len(ALL_ADMIN_TOOL_NAMES)
        assert set(mcp_tools) == set(ALL_ADMIN_TOOL_NAMES)

    def test_no_task_tool(self):
        assert "Task" not in RECIPE_TOOLS

    def test_model(self):
        assert RECIPE_MODEL == "sonnet"


class TestGuardAgent:
    def test_has_system_prompt(self):
        assert len(GUARD_SYSTEM_PROMPT) > 100

    def test_read_only_bias(self):
        """Guard agent should not have Write or Edit tools."""
        assert "Write" not in GUARD_TOOLS
        assert "Edit" not in GUARD_TOOLS

    def test_no_task_tool(self):
        assert "Task" not in GUARD_TOOLS

    def test_model(self):
        assert GUARD_MODEL == "haiku"
