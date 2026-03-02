# Heimdall

Autonomous agentic machine administration.

Heimdall discovers your machine's state, applies configuration recipes written in plain markdown, watches for drift, and fixes what breaks. It orchestrates specialized subagents that handle discovery, configuration, and monitoring.

## How it works

Heimdall runs as a CLI tool or long-lived daemon. It delegates work to three specialized subagents:

- **Discovery agent** scans the machine (OS, packages, services, network, users) and builds a structured profile
- **Recipe applier** reads markdown recipe files and executes the configuration steps
- **Guard agent** compares current state against recipe requirements and reports drift

All shell commands are filtered through an allowlist-based security hook. Custom MCP tools provide cross-distro abstractions for package and service management (apt/dnf/brew/pacman, systemd/launchd). Every tool invocation is logged to an append-only audit trail.

## Recipes

Recipes are markdown files with YAML frontmatter. They describe desired machine state in natural language:

```markdown
---
name: Home Server
description: SSH hardening, Seafile cloud storage, Jellyfin media streaming
tags: [home, server, media, cloud]
os_families: [debian, redhat]
---

## SSH Hardening

Disable root login and password authentication. Only allow key-based auth.

## Firewall

Allow SSH (22), HTTP (80), HTTPS (443), Jellyfin (8096), Seafile (8082, 8000).
Deny everything else.
```

The recipe applier reads these sections, compares them against the current machine profile, plans the steps, and executes them.

Heimdall parses each recipe into a structured specification at runtime (metadata + numbered sections) and validates `os_families` against the current host. When you run `heimdall apply --check`, the orchestrator enforces a read-only toolset so the agent can plan safely without executing any mutations.

## Installation

Requires Python 3.12+ and an Anthropic API key.

```bash
pip install .
export ANTHROPIC_API_KEY=sk-...
```

## Usage

```bash
# Discover machine state and save a profile
heimdall init

# Apply a recipe (use --check for dry run)
heimdall apply recipes/home-server.md
heimdall apply recipes/home-server.md --check

# Quick profile refresh
heimdall scan

# Check for drift from a recipe
heimdall guard recipes/home-server.md

# Run as a daemon with periodic scan and guard
heimdall daemon -r recipes/home-server.md -i 60

# Show current profile and drift status
heimdall status
```

## Configuration

Heimdall reads config from `~/.config/heimdall/config.yaml`. All fields are optional:

```yaml
model: sonnet              # Claude model (sonnet, haiku, opus)
max_budget_usd: 1.0        # Per-command budget limit
daemon_interval_minutes: 60
log_level: INFO
recipes_dir: recipes
profiles_dir: profiles
llm_provider: anthropic     # or openrouter
llm_model_overrides:        # optional per-operation overrides
  apply: sonnet
openrouter_model: openrouter/openai/gpt-4o-mini
openrouter_api_key_env: OPENROUTER_API_KEY
```

When `llm_provider` is set to `openrouter`, Heimdall uses the OpenRouter chat completions API with native tool-calling. Set the `OPENROUTER_API_KEY` environment variable (or your custom `llm_api_key_env`) before running commands. You can override models per-operation via `llm_model_overrides` (keys: `init`, `apply`, `scan`, `guard`, `orchestrator`, `openrouter`, `discovery`, `recipes`, `guard`).

## Security model

- **Allowlist-based Bash filtering**: only known-safe command prefixes are permitted. Shell metacharacters (pipes, semicolons, command substitution) are rejected before parsing.
- **MCP input validation**: package and service names are validated against a strict regex before being passed to shell commands, with `shlex.quote()` as defense-in-depth.
- **Dangerous environment variables blocked**: `LD_PRELOAD`, `PATH`, `DYLD_INSERT_LIBRARIES`, and similar are rejected.
- **Audit logging**: every tool invocation is logged to `~/.local/share/heimdall/audit.log` with timestamps and inputs.
- **Subagent isolation**: subagents cannot spawn other subagents (no `Task` tool in their toolsets).

## Project structure

```
src/heimdall/
  cli.py              # Click CLI (init, apply, scan, guard, daemon, status)
  config.py           # AdminConfig pydantic model
  models.py           # MachineProfile, RecipeSpec, DriftReport
  agent.py            # Core orchestrator using Claude Agent SDK
  hooks.py            # PreToolUse/PostToolUse security and audit hooks
  tools/              # Cross-distro MCP tools (packages, services)
  modules/            # Subagent definitions (discovery, recipes, guard)
  daemon/             # Long-running daemon mode
recipes/              # Markdown recipe files
profiles/             # Machine state snapshots
```

## Development

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

## License

MIT
