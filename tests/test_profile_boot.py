"""
Test that Hermes profiles boot and respond to basic prompts.

Note: These tests require Hermes Agent to be installed and configured.
They will be skipped if Hermes is not available.
"""
import subprocess
import pytest

PROFILES = [
    "zeus",
    "chronos",
    "iaso",
    "hermes-agent",
    "philia",
    "plutus",
    "hephaestus",
    "metis",
    "apollo",
    "midas",
]


def hermes_available() -> bool:
    try:
        subprocess.run(["hermes", "--version"], capture_output=True, check=True)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


pytestmark = pytest.mark.skipif(
    not hermes_available(), reason="Hermes Agent not installed"
)


@pytest.mark.parametrize("profile", PROFILES)
def test_profile_responds(profile):
    """Test that a profile boots and responds to a basic prompt."""
    result = subprocess.run(
        ["hermes", "-p", profile, "-z", "Who are you? Respond in one sentence."],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, f"Profile {profile} failed: {result.stderr}"
    assert result.stdout.strip(), f"Profile {profile} returned empty response"
