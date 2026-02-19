"""Tests for data models."""

import json
from datetime import datetime, timezone

from heimdall.models import (
    DriftItem,
    DriftReport,
    DriftSeverity,
    ListeningPort,
    MachineProfile,
    NetworkInterface,
    PackageState,
    RecipeMetadata,
    RecipeSpec,
    ServiceState,
    UserAccount,
)


class TestMachineProfile:
    def test_empty_profile(self):
        profile = MachineProfile()
        assert profile.hostname == ""
        assert profile.packages == []
        assert profile.services == []

    def test_roundtrip_json(self):
        profile = MachineProfile(
            hostname="testhost",
            os_name="Ubuntu 24.04",
            os_family="debian",
            kernel="6.8.0",
            architecture="x86_64",
            cpu="AMD Ryzen 5",
            memory_gb=16.0,
            disk_gb=500.0,
            packages=[PackageState(name="nginx", version="1.24", manager="apt")],
            services=[ServiceState(name="nginx", active=True, enabled=True, manager="systemd")],
            network_interfaces=[
                NetworkInterface(name="eth0", ipv4=["192.168.1.10"], mac="aa:bb:cc:dd:ee:ff", state="up")
            ],
            listening_ports=[ListeningPort(port=80, protocol="tcp", process="nginx", pid=1234)],
            users=[UserAccount(username="admin", uid=1000, gid=1000, home="/home/admin", shell="/bin/bash")],
            scanned_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
        data = json.loads(profile.model_dump_json())
        restored = MachineProfile(**data)
        assert restored.hostname == "testhost"
        assert len(restored.packages) == 1
        assert restored.packages[0].name == "nginx"
        assert restored.memory_gb == 16.0

    def test_to_markdown(self):
        profile = MachineProfile(
            hostname="myhost",
            os_name="Debian 12",
            os_family="debian",
            packages=[PackageState(name="vim", version="9.0")],
            services=[ServiceState(name="sshd", active=True, enabled=True)],
        )
        md = profile.to_markdown()
        assert "# Machine Profile: myhost" in md
        assert "vim 9.0" in md
        assert "sshd: active, enabled" in md

    def test_to_markdown_truncates_packages(self):
        packages = [PackageState(name=f"pkg-{i}", version="1.0") for i in range(100)]
        profile = MachineProfile(hostname="host", packages=packages)
        md = profile.to_markdown()
        assert "and 50 more" in md


class TestRecipeSpec:
    def test_empty_spec(self):
        spec = RecipeSpec()
        assert spec.metadata.name == ""
        assert spec.sections == []

    def test_with_metadata(self):
        spec = RecipeSpec(
            metadata=RecipeMetadata(
                name="Test Recipe",
                description="A test",
                tags=["test"],
                os_families=["debian"],
            ),
            raw_content="# Test\nDo stuff.",
            sections=["# Test"],
        )
        assert spec.metadata.name == "Test Recipe"
        assert spec.metadata.os_families == ["debian"]


class TestDriftReport:
    def test_compliant_report(self):
        report = DriftReport(recipe_name="test", is_compliant=True)
        md = report.to_markdown()
        assert "Compliant" in md
        assert "No drift detected" in md

    def test_drifted_report(self):
        report = DriftReport(
            recipe_name="test",
            is_compliant=False,
            checked_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
            items=[
                DriftItem(
                    category="package",
                    description="nginx not installed",
                    expected="installed",
                    actual="missing",
                    severity=DriftSeverity.CRITICAL,
                ),
            ],
        )
        md = report.to_markdown()
        assert "DRIFTED" in md
        assert "nginx not installed" in md
        assert "CRITICAL" in md

    def test_roundtrip_json(self):
        report = DriftReport(
            recipe_name="test",
            is_compliant=False,
            items=[
                DriftItem(category="service", description="sshd not running", severity=DriftSeverity.WARNING),
            ],
        )
        data = json.loads(report.model_dump_json())
        restored = DriftReport(**data)
        assert not restored.is_compliant
        assert restored.items[0].category == "service"
