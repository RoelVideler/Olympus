#!/usr/bin/env python3
"""
verify_profiles.py: Verify all 10 Hermes profiles boot and respond.

Usage:
    python scripts/verify_profiles.py

Expected output:
    zeus: OK (response time: X.XXs)
    chronos: OK (response time: X.XXs)
    ...
"""
import subprocess
import time
import sys

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

TEST_PROMPT = "Who are you? Respond in one sentence."


def verify_profile(profile_name: str) -> tuple[bool, str]:
    """Verify a single profile boots and responds."""
    start = time.time()
    try:
        result = subprocess.run(
            ["hermes", "-p", profile_name, "-z", TEST_PROMPT],
            capture_output=True,
            text=True,
            timeout=60,
        )
        elapsed = time.time() - start

        if result.returncode == 0 and result.stdout.strip():
            return True, f"OK ({elapsed:.2f}s)"
        else:
            return False, f"FAILED: {result.stderr.strip()}"
    except subprocess.TimeoutExpired:
        return False, "TIMEOUT (>60s)"
    except FileNotFoundError:
        return False, "hermes command not found"
    except Exception as e:
        return False, f"ERROR: {str(e)}"


def main():
    print("Verifying Olympus profiles...\n")
    all_passed = True

    for profile in PROFILES:
        success, message = verify_profile(profile)
        status = "✓" if success else "✗"
        print(f"  {profile}: {status} {message}")
        if not success:
            all_passed = False

    print()
    if all_passed:
        print("All profiles verified successfully!")
        sys.exit(0)
    else:
        print("Some profiles failed verification.")
        sys.exit(1)


if __name__ == "__main__":
    main()
