"""Recipe parsing and validation utilities."""

from __future__ import annotations

import platform
from pathlib import Path

import frontmatter

from .models import RecipeMetadata, RecipeSpec


def load_recipe_spec(path: Path) -> RecipeSpec:
    """Parse a markdown recipe with YAML frontmatter into a RecipeSpec."""

    post = frontmatter.load(str(path))
    metadata = RecipeMetadata(**(post.metadata or {}))
    sections = _split_into_sections(post.content or "")
    return RecipeSpec(
        metadata=metadata,
        source_path=path,
        raw_content=(post.content or "").strip(),
        sections=sections,
    )


def summarize_sections(spec: RecipeSpec, max_sections: int = 12) -> str:
    """Return a short numbered outline of the recipe sections."""

    lines: list[str] = []
    for idx, section in enumerate(spec.sections[:max_sections], start=1):
        title = _derive_section_title(section)
        lines.append(f"{idx}. {title}")
    if len(spec.sections) > max_sections:
        lines.append(f"... plus {len(spec.sections) - max_sections} more sections")
    return "\n".join(lines) if lines else "(no sections found)"


def ensure_recipe_supported(spec: RecipeSpec) -> None:
    """Raise ValueError if the current machine is not supported by the recipe."""

    if not spec.metadata.os_families:
        return

    current = detect_os_family()
    if current and current not in spec.metadata.os_families:
        raise ValueError(
            "Recipe is not applicable to this machine: "
            f"requires {spec.metadata.os_families}, detected {current}."
        )


def detect_os_family() -> str:
    """Best-effort detection of the current OS family."""

    system = platform.system().lower()
    if system == "darwin":
        return "macos"
    if system != "linux":
        return system

    os_release = _read_os_release()
    tokens = _tokenize_os_release(os_release)
    if any(tok in tokens for tok in ("debian", "ubuntu")):
        return "debian"
    if any(tok in tokens for tok in ("rhel", "redhat", "fedora", "centos", "rocky")):
        return "redhat"
    if "arch" in tokens:
        return "arch"
    return "linux"


def _read_os_release() -> dict[str, str]:
    data: dict[str, str] = {}
    try:
        with open("/etc/os-release", "r", encoding="utf-8") as fh:
            for line in fh:
                if "=" not in line:
                    continue
                key, value = line.strip().split("=", 1)
                data[key.upper()] = value.strip().strip('"')
    except FileNotFoundError:
        pass
    return data


def _tokenize_os_release(data: dict[str, str]) -> set[str]:
    tokens: set[str] = set()
    for key in ("ID", "ID_LIKE"):
        raw = data.get(key, "")
        for token in raw.replace("/", " ").replace(",", " ").split():
            tokens.add(token.lower())
    return tokens


def _split_into_sections(content: str) -> list[str]:
    sections: list[list[str]] = []
    current: list[str] = []
    for line in content.splitlines():
        if line.startswith("## ") and current:
            sections.append(current)
            current = [line]
        else:
            current.append(line)
    if current:
        sections.append(current)
    return ["\n".join(block).strip() for block in sections if any(s.strip() for s in block)]


def _derive_section_title(section: str) -> str:
    for line in section.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        stripped = stripped.lstrip("# ").strip()
        return stripped or "Untitled Section"
    return "Untitled Section"
