"""Configuration for Heimdall."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field

DEFAULT_CONFIG_PATH = Path.home() / ".config" / "heimdall" / "config.yaml"


class AdminConfig(BaseModel):
    """Top-level configuration."""

    recipes_dir: Path = Field(default_factory=lambda: Path("recipes"))
    profiles_dir: Path = Field(default_factory=lambda: Path("profiles"))
    log_level: str = "INFO"
    model: str = "sonnet"
    permission_mode: str = "default"
    max_budget_usd: float = 1.0
    daemon_interval_minutes: int = 60
    llm_provider: str = "anthropic"
    llm_api_key_env: str | None = None
    llm_model_overrides: dict[str, str] = Field(default_factory=dict)
    openrouter_model: str = "openrouter/openai/gpt-4o-mini"
    openrouter_api_key_env: str = "OPENROUTER_API_KEY"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_referer: str | None = None
    openrouter_title: str | None = "Heimdall"
    openrouter_temperature: float = 0.2
    audit_log_path: Path = Field(
        default_factory=lambda: Path.home()
        / ".local"
        / "share"
        / "heimdall"
        / "audit.log"
    )
    allowed_command_prefixes: list[str] = Field(
        default_factory=lambda: [
            # Package managers
            "apt",
            "apt-get",
            "dpkg",
            "dpkg-query",
            "dnf",
            "yum",
            "pacman",
            "brew",
            # Service managers
            "systemctl",
            "launchctl",
            "service",
            # Firewall
            "ufw",
            "firewall-cmd",
            # Network inspection (read-only)
            "ss",
            "ip",
            "ifconfig",
            "netstat",
            "lsof",
            "dig",
            "nslookup",
            "ping",
            # File / system info (read-only)
            "cat",
            "ls",
            "stat",
            "file",
            "wc",
            "df",
            "du",
            "free",
            "lscpu",
            "lsblk",
            "uname",
            "hostname",
            "whoami",
            "id",
            "groups",
            "getent",
            # Process inspection (read-only)
            "ps",
            "pgrep",
            # Filesystem mutation (needed for recipes)
            "mkdir",
            "cp",
            "mv",
            "chmod",
            "chown",
            "ln",
            "touch",
            # Text inspection (read-only)
            "head",
            "tail",
            "grep",
            "sort",
            "uniq",
            "tr",
            "cut",
            # Misc safe (read-only)
            "date",
            "which",
            "command",
            "type",
            "test",
            "[",
        ]
    )


def load_config(path: Path | None = None) -> AdminConfig:
    """Load config from YAML file, falling back to defaults."""
    config_path = path or DEFAULT_CONFIG_PATH
    if config_path.exists():
        with open(config_path) as f:
            data = yaml.safe_load(f) or {}
        return AdminConfig(**data)
    return AdminConfig()
