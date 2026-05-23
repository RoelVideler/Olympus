"""
Test that Hermes profiles boot and respond to basic prompts.

Note: These tests require Hermes Agent to be installed and configured.
They will be skipped if Hermes is not available.
"""
import subprocess
import pytest

from olympus.constants import PROFILES, ERROR_INDICATORS


def hermes_available() -> bool:
    try:
        result = subprocess.run(["hermes", "--version"], capture_output=True, check=False)
        return result.returncode == 0
    except FileNotFoundError:
        return False


pytestmark = pytest.mark.skipif(
    not hermes_available(), reason="Hermes Agent not installed"
)


@pytest.mark.parametrize("profile", PROFILES)
def test_profile_responds(profile):
    """Test that a profile boots and responds to a basic prompt."""
    try:
        result = subprocess.run(
            ["hermes", "-p", profile, "-z", "Who are you? Respond in one sentence."],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except subprocess.TimeoutExpired:
        pytest.fail(f"Profile {profile} timed out after 60s")

    assert result.returncode == 0, f"Profile {profile} failed: {result.stderr}"
    assert result.stdout.strip(), f"Profile {profile} returned empty response"
    output = result.stdout.strip()
    output_lower = output.lower()
    for indicator in ERROR_INDICATORS:
        assert indicator not in output_lower, f"Profile {profile} output contains error: {indicator}"
