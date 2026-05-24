"""Domain routing skill — maps query domains to specialist profiles via polling.

Uses lightweight model calls to specialist profiles (hermes -p <profile> -z "<prompt>")
to determine which specialist should handle a given query.
"""

from __future__ import annotations

import json
import subprocess
from typing import Any

ROUTING_SCHEMA = {
    "name": "routing",
    "description": "Route a query to specialist profiles via polling and return routing decisions.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The user query to route.",
            },
            "all_profiles": {
                "type": "boolean",
                "description": "If true, poll all specialist profiles. If false, use domain matching only.",
                "default": False,
            },
        },
        "required": ["query"],
    },
}

DOMAIN_MAP = {
    "scheduling": "chronos",
    "calendar": "chronos",
    "planning": "chronos",
    "time": "chronos",
    "health": "iaso",
    "fitness": "iaso",
    "nutrition": "iaso",
    "exercise": "iaso",
    "sleep": "iaso",
    "relationships": "philia",
    "social": "philia",
    "friend": "philia",
    "family": "philia",
    "dating": "philia",
    "investments": "plutus",
    "stocks": "plutus",
    "money": "plutus",
    "portfolio": "plutus",
    "crypto": "plutus",
    "home": "hephaestus",
    "maintenance": "hephaestus",
    "repair": "hephaestus",
    "appliance": "hephaestus",
    "business": "metis",
    "strategy": "metis",
    "startup": "metis",
    "marketing": "metis",
    "creative": "apollo",
    "writing": "apollo",
    "art": "apollo",
    "music": "apollo",
    "design": "apollo",
    "finance": "midas",
    "budget": "midas",
    "budgeting": "midas",
    "expenses": "midas",
    "saving": "midas",
    "spending": "midas",
}

SPECIALIST_PROFILES = [
    "chronos",
    "iaso",
    "philia",
    "plutus",
    "hephaestus",
    "metis",
    "apollo",
    "midas",
]

ROUTING_PROMPT = (
    "You are a domain classifier. Given this user query, determine which single domain "
    "it belongs to from: scheduling, health, relationships, investments, home, business, "
    "creative, finance. Respond with ONLY the domain name in lowercase, or 'unknown' if "
    "none match.\n\nQuery: {query}"
)

SPECIALIST_PROMPT = (
    "You are a specialist AI assistant. Given this user query, briefly assess whether "
    "it falls within your domain expertise. If yes, provide a short insight (2-3 sentences). "
    "If no, respond with exactly: NO_MATCH\n\nQuery: {query}"
)


def _detect_domain(query: str) -> str:
    """Detect the domain of a query using keyword matching."""
    query_lower = query.lower()
    for keyword, domain in DOMAIN_MAP.items():
        if keyword in query_lower:
            return domain
    return "unknown"


def _call_profile(profile: str, prompt: str, timeout: int = 10) -> str | None:
    """Make a lightweight model call to a specialist profile via Hermes CLI."""
    try:
        result = subprocess.run(
            ["hermes", "-p", profile, "-z", prompt],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return None
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None


def handle_routing(args: dict, **kw) -> dict[str, Any]:
    """Handle a routing request.

    Args:
        args: Dict with 'query' and optional 'all_profiles' boolean.

    Returns:
        Dict with domain, matched_profile, and optional specialist responses.
    """
    query = args.get("query", "")
    all_profiles = args.get("all_profiles", False)

    domain = _detect_domain(query)
    matched_profile = DOMAIN_MAP.get(domain) if domain != "unknown" else None

    result: dict[str, Any] = {
        "domain": domain,
        "matched_profile": matched_profile,
        "specialist_responses": {},
    }

    if matched_profile and not all_profiles:
        response = _call_profile(matched_profile, SPECIALIST_PROMPT.format(query=query))
        if response and response != "NO_MATCH":
            result["specialist_responses"][matched_profile] = response

    if all_profiles:
        for profile in SPECIALIST_PROFILES:
            response = _call_profile(profile, SPECIALIST_PROMPT.format(query=query))
            if response and response != "NO_MATCH":
                result["specialist_responses"][profile] = response

    return result
