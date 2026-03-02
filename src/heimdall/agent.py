"""Core orchestrator — builds agent options and runs commands."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .config import AdminConfig
from .hooks import set_config, set_dry_run_mode
from .llm import LLMRunRequest, create_llm_client
from .models import DriftReport, MachineProfile, RecipeSpec
from .recipe_parser import ensure_recipe_supported, load_recipe_spec, summarize_sections


def _ensure_runtime_dirs(config: AdminConfig) -> None:
    config.recipes_dir.mkdir(parents=True, exist_ok=True)
    config.profiles_dir.mkdir(parents=True, exist_ok=True)


def _load_recipe(recipe_path: str, validate_os: bool = False) -> RecipeSpec:
    path = Path(recipe_path)
    spec = load_recipe_spec(path)
    if validate_os:
        ensure_recipe_supported(spec)
    return spec


def _recipe_prompt_context(spec: RecipeSpec) -> str:
    metadata = spec.metadata
    name = metadata.name or (spec.source_path.name if spec.source_path else "(unknown)")
    tags = ", ".join(metadata.tags) if metadata.tags else "none"
    os_targets = ", ".join(metadata.os_families) if metadata.os_families else "any"
    summary = summarize_sections(spec)
    return (
        f"Recipe: {name}\n"
        f"Description: {metadata.description or 'n/a'}\n"
        f"Tags: {tags}\n"
        f"Supported OS families: {os_targets}\n"
        f"Sections:\n{summary}\n"
        f"Source path: {spec.source_path}"
    )


def _stamp_drift_report(config: AdminConfig, spec: RecipeSpec) -> None:
    drift_path = config.profiles_dir / "drift-report.json"
    if not drift_path.exists():
        return
    data = json.loads(drift_path.read_text())
    report = DriftReport(**data)
    report.recipe_name = report.recipe_name or spec.metadata.name or (
        spec.source_path.name if spec.source_path else ""
    )
    report.checked_at = datetime.now(timezone.utc)
    drift_path.write_text(report.model_dump_json(indent=2))


def _load_profile(config: AdminConfig) -> MachineProfile | None:
    """Load the current machine profile if it exists."""
    profile_path = config.profiles_dir / "current.json"
    if profile_path.exists():
        data = json.loads(profile_path.read_text())
        return MachineProfile(**data)
    return None


async def run_init(config: AdminConfig) -> None:
    """Discover machine state and save profile."""
    _ensure_runtime_dirs(config)
    set_config(config)
    set_dry_run_mode(False)
    client = create_llm_client(config)
    profile = _load_profile(config)
    context = ""
    if profile:
        context = f"\n\nCurrent known profile:\n{profile.to_markdown()}"

    prompt = (
        "Discover this machine's complete state and save the profile to "
        f"{config.profiles_dir}/current.json. "
        "Use the discovery subagent to perform the scan."
        f"{context}"
    )

    await client.run(
        LLMRunRequest(
            operation="init",
            prompt=prompt,
            system_prompt=(
                "You are Heimdall, an autonomous machine administration agent. "
                "Your task is to discover and inventory this machine's state."
            ),
        )
    )


async def run_apply(config: AdminConfig, recipe_path: str, check: bool = False) -> None:
    """Apply a recipe to the machine."""
    _ensure_runtime_dirs(config)
    set_config(config)
    spec = _load_recipe(recipe_path, validate_os=True)
    profile = _load_profile(config)
    profile_context = f"\n\nCurrent machine profile:\n{profile.to_markdown()}" if profile else ""

    mode = "DRY RUN (--check)" if check else "APPLY"
    recipe_context = _recipe_prompt_context(spec)
    recipe_identity = spec.metadata.name or Path(recipe_path).name
    prompt = (
        f"[{mode}] Apply the recipe '{recipe_identity}' located at '{recipe_path}' to this machine.\n"
        f"{recipe_context}\n\n"
        "Use the recipe-applier subagent to interpret each section, compare it with the current "
        "machine profile, plan concrete steps, and execute them in order."
        f"{profile_context}"
    )
    if check:
        prompt += (
            "\n\nThis is a dry run. Provide a detailed plan of actions for every section, "
            "but do NOT execute any commands that mutate the system."
        )

    set_dry_run_mode(check)
    client = create_llm_client(config)
    try:
        await client.run(
            LLMRunRequest(
                operation="apply",
                prompt=prompt,
                system_prompt=(
                    "You are Heimdall, an autonomous machine administration agent. "
                    "Your task is to apply configuration recipes to this machine."
                ),
                metadata={"recipe": recipe_identity, "check": check},
            )
        )
    finally:
        set_dry_run_mode(False)


async def run_scan(config: AdminConfig) -> None:
    """Quick profile update."""
    _ensure_runtime_dirs(config)
    set_config(config)
    set_dry_run_mode(False)
    client = create_llm_client(config)
    prompt = (
        "Perform a quick scan to update the machine profile at "
        f"{config.profiles_dir}/current.json. "
        "Use the discovery subagent for a focused update."
    )

    await client.run(
        LLMRunRequest(
            operation="scan",
            prompt=prompt,
            system_prompt=(
                "You are Heimdall, an autonomous machine administration agent. "
                "Perform a quick machine state update."
            ),
        )
    )


async def run_guard(
    config: AdminConfig,
    recipe_path: str,
) -> None:
    """Check for drift from a recipe."""
    _ensure_runtime_dirs(config)
    set_config(config)
    set_dry_run_mode(False)
    spec = _load_recipe(recipe_path)
    profile = _load_profile(config)
    profile_context = f"\n\nCurrent machine profile:\n{profile.to_markdown()}" if profile else ""
    recipe_context = _recipe_prompt_context(spec)
    recipe_identity = spec.metadata.name or Path(recipe_path).name

    prompt = (
        f"Check for drift from the recipe '{recipe_identity}' located at '{recipe_path}'.\n"
        f"{recipe_context}\n\n"
        "Use the guard subagent to compare current state against every requirement in the recipe. "
        f"Write the drift report to {config.profiles_dir}/drift-report.json with an accurate summary."
        f"{profile_context}"
    )

    client = create_llm_client(config)
    await client.run(
        LLMRunRequest(
            operation="guard",
            prompt=prompt,
            system_prompt=(
                "You are Heimdall, an autonomous machine administration agent. "
                "Your task is to detect configuration drift."
            ),
            metadata={"recipe": recipe_identity},
        )
    )

    _stamp_drift_report(config, spec)


def run_status(config: AdminConfig) -> None:
    """Show current profile and drift status."""
    _ensure_runtime_dirs(config)
    profile = _load_profile(config)
    if not profile:
        print("No machine profile found. Run 'heimdall init' first.")
        return

    print(profile.to_markdown())

    drift_path = config.profiles_dir / "drift-report.json"
    if drift_path.exists():
        data = json.loads(drift_path.read_text())
        report = DriftReport(**data)
        print("\n" + report.to_markdown())
    else:
        print("\nNo drift report found. Run 'heimdall guard' to check for drift.")
