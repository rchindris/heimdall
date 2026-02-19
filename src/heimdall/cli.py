"""CLI interface for Heimdall."""

from __future__ import annotations

import asyncio
from pathlib import Path

import click

from .config import AdminConfig, load_config


@click.group()
@click.option(
    "--config",
    "config_path",
    type=click.Path(exists=False, path_type=Path),
    default=None,
    help="Path to config YAML file.",
)
@click.pass_context
def main(ctx: click.Context, config_path: Path | None) -> None:
    """Heimdall — autonomous agentic machine administration."""
    ctx.ensure_object(dict)
    ctx.obj["config"] = load_config(config_path)


@main.command()
@click.pass_context
def init(ctx: click.Context) -> None:
    """Discover machine state and save profile."""
    from .agent import run_init

    config: AdminConfig = ctx.obj["config"]
    asyncio.run(run_init(config))


@main.command()
@click.argument("recipe", type=click.Path(exists=True, path_type=Path))
@click.option("--check", is_flag=True, help="Dry run — show what would be done.")
@click.pass_context
def apply(ctx: click.Context, recipe: Path, check: bool) -> None:
    """Apply a recipe to this machine."""
    from .agent import run_apply

    config: AdminConfig = ctx.obj["config"]
    asyncio.run(run_apply(config, str(recipe), check=check))


@main.command()
@click.pass_context
def scan(ctx: click.Context) -> None:
    """Quick profile update."""
    from .agent import run_scan

    config: AdminConfig = ctx.obj["config"]
    asyncio.run(run_scan(config))


@main.command()
@click.argument("recipe", type=click.Path(exists=True, path_type=Path), required=False)
@click.option("-r", "--recipe-path", type=click.Path(exists=True, path_type=Path), help="Recipe file.")
@click.option("--once", is_flag=True, help="Run once and exit.")
@click.pass_context
def guard(ctx: click.Context, recipe: Path | None, recipe_path: Path | None, once: bool) -> None:
    """Check for drift from a recipe."""
    from .agent import run_guard

    config: AdminConfig = ctx.obj["config"]
    path = recipe or recipe_path
    if not path:
        raise click.UsageError("Provide a recipe path as argument or via -r/--recipe-path.")
    asyncio.run(run_guard(config, str(path)))


@main.command()
@click.option("-i", "--interval", type=int, default=None, help="Interval in minutes.")
@click.option("-r", "--recipe", type=click.Path(exists=True, path_type=Path), required=True, help="Recipe file.")
@click.pass_context
def daemon(ctx: click.Context, interval: int | None, recipe: Path) -> None:
    """Run in daemon mode with periodic scan and guard."""
    from .daemon.server import AdminDaemon

    config: AdminConfig = ctx.obj["config"]
    if interval is not None:
        config = config.model_copy(update={"daemon_interval_minutes": interval})

    d = AdminDaemon(config=config, recipe_path=str(recipe))
    asyncio.run(d.run())


@main.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """Show current profile and drift status."""
    from .agent import run_status

    config: AdminConfig = ctx.obj["config"]
    run_status(config)
