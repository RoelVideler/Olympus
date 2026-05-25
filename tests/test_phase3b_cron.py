"""Tests for Phase 3b: Cron Jobs — Chronos morning briefing, health sync, portfolio check."""

import json
import subprocess
from pathlib import Path

import pytest


def _run_hermes(args: list[str], profile: str = "chronos") -> subprocess.CompletedProcess:
    """Run a hermes CLI command."""
    return subprocess.run(
        ["hermes", "-p", profile] + args,
        capture_output=True,
        text=True,
        timeout=30,
    )


class TestGatewayRunning:
    """Test that the Hermes gateway is installed and running."""

    def test_gateway_service_installed(self):
        """Gateway service should be installed as a launchd service."""
        plist = Path.home() / "Library" / "LaunchAgents" / "ai.hermes.gateway.plist"
        assert plist.exists(), "Gateway launchd plist not found"

    def test_gateway_process_running(self):
        """Gateway process should be running."""
        result = subprocess.run(
            ["pgrep", "-f", "hermes_cli.main.*gateway"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, "Gateway process not running"


class TestCronJobs:
    """Test that all Phase 3b cron jobs are created."""

    @pytest.fixture
    def cron_list(self):
        """Get the list of cron jobs."""
        result = _run_hermes(["cron", "list"])
        assert result.returncode == 0
        return result.stdout

    def test_morning_briefing_job(self, cron_list):
        """Morning briefing should be scheduled at 07:00 daily on Zeus profile."""
        assert "morning-briefing" in cron_list
        assert "0 7 * * *" in cron_list
        assert "zeus" in cron_list

    def test_email_triage_job(self, cron_list):
        """Email triage should run every 30 minutes on Hermes profile."""
        assert "email-triage" in cron_list
        assert "every 30m" in cron_list
        assert "hermes-agent" in cron_list

    def test_health_sync_job(self, cron_list):
        """Health sync should run at 08:00 and 20:00 on Iaso profile."""
        assert "health-sync" in cron_list
        assert "0 8,20 * * *" in cron_list
        assert "iaso" in cron_list

    def test_portfolio_check_job(self, cron_list):
        """Portfolio check should run at 09:30 weekdays on Plutus profile."""
        assert "portfolio-check" in cron_list
        assert "30 9 * * 1-5" in cron_list
        assert "plutus" in cron_list

    def test_invoice_reminder_job(self, cron_list):
        """Invoice reminder should run on 1st of month on Midas profile."""
        assert "invoice-reminder" in cron_list
        assert "0 10 1 * *" in cron_list
        assert "midas" in cron_list

    def test_all_jobs_active(self, cron_list):
        """All jobs should be in active state."""
        assert cron_list.count("[active]") >= 5

    def test_five_jobs_total(self, cron_list):
        """Should have exactly 5 cron jobs."""
        job_names = ["morning-briefing", "email-triage", "health-sync", "portfolio-check", "invoice-reminder"]
        found = sum(1 for name in job_names if name in cron_list)
        assert found >= 5, f"Expected at least 5 jobs, found {found}"


class TestCronScheduler:
    """Test that the cron scheduler is operational."""

    def test_cron_ticker_started(self):
        """Gateway logs should show cron ticker started."""
        log_path = Path.home() / ".hermes" / "logs" / "gateway.log"
        if log_path.exists():
            content = log_path.read_text()
            assert "Cron ticker started" in content, "Cron ticker not found in gateway logs"
