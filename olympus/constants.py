"""Shared constants for Olympus profile verification."""

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

ERROR_INDICATORS = [
    "Profile does not exist",
    "error:",
    "failed:",
    "Traceback",
    "Exception",
]
