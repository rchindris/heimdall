"""Data models for Heimdall."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field


# --- Machine Profile ---


class PackageState(BaseModel):
    """Installed package information."""

    name: str
    version: str = ""
    manager: str = ""  # apt, dnf, brew, pacman


class ServiceState(BaseModel):
    """System service state."""

    name: str
    active: bool = False
    enabled: bool = False
    manager: str = ""  # systemd, launchd


class NetworkInterface(BaseModel):
    """Network interface information."""

    name: str
    ipv4: list[str] = Field(default_factory=list)
    ipv6: list[str] = Field(default_factory=list)
    mac: str = ""
    state: str = ""  # up, down


class ListeningPort(BaseModel):
    """Listening network port."""

    port: int
    protocol: str = "tcp"  # tcp, udp
    address: str = "0.0.0.0"
    process: str = ""
    pid: int | None = None


class UserAccount(BaseModel):
    """System user account."""

    username: str
    uid: int
    gid: int
    home: str = ""
    shell: str = ""
    groups: list[str] = Field(default_factory=list)


class MachineProfile(BaseModel):
    """Complete machine state snapshot."""

    hostname: str = ""
    os_name: str = ""
    os_family: str = ""  # debian, redhat, arch, macos
    os_version: str = ""
    kernel: str = ""
    architecture: str = ""
    cpu: str = ""
    memory_gb: float = 0.0
    disk_gb: float = 0.0
    packages: list[PackageState] = Field(default_factory=list)
    services: list[ServiceState] = Field(default_factory=list)
    network_interfaces: list[NetworkInterface] = Field(default_factory=list)
    listening_ports: list[ListeningPort] = Field(default_factory=list)
    users: list[UserAccount] = Field(default_factory=list)
    scanned_at: datetime | None = None

    def to_markdown(self) -> str:
        """Render profile as markdown for agent prompt injection."""
        lines = [
            f"# Machine Profile: {self.hostname}",
            "",
            f"- **OS**: {self.os_name} ({self.os_family})",
            f"- **Version**: {self.os_version}",
            f"- **Kernel**: {self.kernel}",
            f"- **Architecture**: {self.architecture}",
            f"- **CPU**: {self.cpu}",
            f"- **Memory**: {self.memory_gb:.1f} GB",
            f"- **Disk**: {self.disk_gb:.1f} GB",
            "",
        ]

        if self.packages:
            lines.append(f"## Packages ({len(self.packages)} installed)")
            lines.append("")
            for pkg in self.packages[:50]:  # Truncate for prompt size
                lines.append(f"- {pkg.name} {pkg.version}")
            if len(self.packages) > 50:
                lines.append(f"- ... and {len(self.packages) - 50} more")
            lines.append("")

        if self.services:
            lines.append(f"## Services ({len(self.services)})")
            lines.append("")
            for svc in self.services:
                status = "active" if svc.active else "inactive"
                enabled = "enabled" if svc.enabled else "disabled"
                lines.append(f"- {svc.name}: {status}, {enabled}")
            lines.append("")

        if self.listening_ports:
            lines.append(f"## Listening Ports ({len(self.listening_ports)})")
            lines.append("")
            for port in self.listening_ports:
                lines.append(
                    f"- {port.address}:{port.port}/{port.protocol}"
                    f" ({port.process})"
                )
            lines.append("")

        if self.users:
            lines.append(f"## Users ({len(self.users)})")
            lines.append("")
            for user in self.users:
                lines.append(f"- {user.username} (uid={user.uid})")
            lines.append("")

        return "\n".join(lines)


# --- Recipe ---


class RecipeMetadata(BaseModel):
    """YAML frontmatter from a recipe markdown file."""

    name: str = ""
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    requires: list[str] = Field(default_factory=list)  # Other recipe names
    os_families: list[str] = Field(default_factory=list)


class RecipeSpec(BaseModel):
    """Parsed recipe specification."""

    metadata: RecipeMetadata = Field(default_factory=RecipeMetadata)
    source_path: Path | None = None
    raw_content: str = ""
    sections: list[str] = Field(default_factory=list)


# --- Drift Detection ---


class DriftSeverity(str, Enum):
    """Severity level for drift items."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class DriftItem(BaseModel):
    """Single drift finding."""

    category: str = ""  # package, service, config, port, user
    description: str = ""
    expected: str = ""
    actual: str = ""
    severity: DriftSeverity = DriftSeverity.WARNING


class DriftReport(BaseModel):
    """Complete drift detection report."""

    recipe_name: str = ""
    checked_at: datetime | None = None
    items: list[DriftItem] = Field(default_factory=list)
    is_compliant: bool = True

    def to_markdown(self) -> str:
        """Render drift report as markdown."""
        lines = [
            f"# Drift Report: {self.recipe_name}",
            "",
            f"**Status**: {'Compliant' if self.is_compliant else 'DRIFTED'}",
            f"**Checked at**: {self.checked_at}",
            "",
        ]

        if not self.items:
            lines.append("No drift detected.")
        else:
            lines.append(f"## Findings ({len(self.items)})")
            lines.append("")
            for item in self.items:
                lines.append(
                    f"- [{item.severity.value.upper()}] **{item.category}**: "
                    f"{item.description}"
                )
                if item.expected:
                    lines.append(f"  - Expected: {item.expected}")
                if item.actual:
                    lines.append(f"  - Actual: {item.actual}")
            lines.append("")

        return "\n".join(lines)
