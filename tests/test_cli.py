"""Tests for CLI wiring."""

from click.testing import CliRunner

from heimdall.cli import main


class TestCLI:
    def test_help(self):
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "heimdall" in result.output.lower()

    def test_init_help(self):
        runner = CliRunner()
        result = runner.invoke(main, ["init", "--help"])
        assert result.exit_code == 0

    def test_apply_help(self):
        runner = CliRunner()
        result = runner.invoke(main, ["apply", "--help"])
        assert result.exit_code == 0
        assert "--check" in result.output

    def test_scan_help(self):
        runner = CliRunner()
        result = runner.invoke(main, ["scan", "--help"])
        assert result.exit_code == 0

    def test_guard_help(self):
        runner = CliRunner()
        result = runner.invoke(main, ["guard", "--help"])
        assert result.exit_code == 0
        assert "--once" in result.output

    def test_daemon_help(self):
        runner = CliRunner()
        result = runner.invoke(main, ["daemon", "--help"])
        assert result.exit_code == 0
        assert "--interval" in result.output

    def test_status_help(self):
        runner = CliRunner()
        result = runner.invoke(main, ["status", "--help"])
        assert result.exit_code == 0

    def test_commands_listed(self):
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        for cmd in ("init", "apply", "scan", "guard", "daemon", "status"):
            assert cmd in result.output, f"Command '{cmd}' not in help output"
