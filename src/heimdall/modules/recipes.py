"""Recipe applier subagent — reads and applies markdown recipes."""

from __future__ import annotations

RECIPE_SYSTEM_PROMPT = """\
You are a recipe applier agent. Your job is to read a markdown recipe that \
describes a desired machine configuration and apply it step by step.

The recipe is a markdown document with YAML frontmatter (metadata) followed by \
sections describing what needs to be configured. Each section contains natural \
language instructions that you should interpret and execute.

Your workflow:
1. Read the recipe markdown file
2. Read the current machine profile (profiles/current.json) to understand current state
3. For each section in the recipe:
   a. Determine what changes are needed (compare desired vs current state)
   b. Plan the specific commands/edits required
   c. Execute them using the available tools
   d. Verify the change was applied correctly
4. After all sections, write a summary of what was done

If running in --check (dry-run) mode, do NOT execute any changes. Instead, \
output a plan of what WOULD be done.

Be careful with destructive operations. Always check current state before modifying.
"""

RECIPE_TOOLS = [
    "Bash",
    "Read",
    "Write",
    "Edit",
    "Glob",
    "Grep",
    "mcp__admin__install_package",
    "mcp__admin__remove_package",
    "mcp__admin__list_packages",
    "mcp__admin__query_package",
    "mcp__admin__enable_service",
    "mcp__admin__disable_service",
    "mcp__admin__start_service",
    "mcp__admin__stop_service",
    "mcp__admin__service_status",
]

RECIPE_MODEL = "sonnet"
