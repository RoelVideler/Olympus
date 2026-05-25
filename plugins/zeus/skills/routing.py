"""Domain routing skill — maps query domains to specialist profiles via polling.

Uses lightweight model calls to specialist profiles (hermes -p <profile> -z "<prompt>")
to determine which specialist should handle a given query.
"""

from __future__ import annotations

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

KEYWORD_TO_DOMAIN = {
    "scheduling": "scheduling",
    "schedule": "scheduling",
    "calendar": "scheduling",
    "planning": "scheduling",
    "time": "scheduling",
    "test": "scheduling",
    "health": "health",
    "fitness": "health",
    "nutrition": "health",
    "exercise": "health",
    "sleep": "health",
    "relationships": "relationships",
    "social": "relationships",
    "friend": "relationships",
    "family": "relationships",
    "dating": "relationships",
    "investments": "investments",
    "stocks": "investments",
    "money": "investments",
    "portfolio": "investments",
    "crypto": "investments",
    "home": "home",
    "maintenance": "home",
    "repair": "home",
    "appliance": "home",
    "business": "business",
    "strategy": "business",
    "startup": "business",
    "marketing": "business",
    "creative": "creative",
    "writing": "creative",
    "art": "creative",
    "music": "creative",
    "design": "creative",
    "finance": "finance",
    "budget": "finance",
    "budgeting": "finance",
    "expenses": "finance",
    "saving": "finance",
    "spending": "finance",
}

DOMAIN_MAP = {
    "scheduling": "chronos",
    "health": "iaso",
    "relationships": "philia",
    "investments": "plutus",
    "home": "hephaestus",
    "business": "metis",
    "creative": "apollo",
    "finance": "midas",
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
    "You are a specialist AI assistant. The user asked this query, and Zeus (the generalist) "
    "provided this initial answer:\n\n"
    "Query: {query}\n"
    "Zeus's answer: {zeus_answer}\n\n"
    "Review Zeus's answer from your domain expertise. If it's correct and complete, confirm "
    "that it's accurate. If it needs correction, missing important detail, or could benefit "
    "from your domain-specific knowledge, provide your refined answer. Be thorough but concise — "
    "give as much detail as the situation requires.\n\n"
    "If this query is NOT within your domain expertise, say so briefly and move on."
)


def _detect_domain(query: str) -> str:
    """Detect the domain of a query using keyword matching."""
    query_lower = query.lower()
    for keyword, domain in KEYWORD_TO_DOMAIN.items():
        if keyword in query_lower:
            return domain
    return "unknown"


_NO_MATCH_INDICATORS = [
    "not within my domain",
    "not my area",
    "not in my expertise",
    "don't handle that",
    "outside my domain",
    "not something i can",
    "not my specialty",
]


def _is_no_match(response: str) -> bool:
    """Check if a specialist response indicates the query is outside their domain."""
    if not response:
        return True
    response_lower = response.lower()
    return any(indicator in response_lower for indicator in _NO_MATCH_INDICATORS)


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
        args: Dict with 'query', optional 'zeus_answer', and optional 'all_profiles' boolean.

    Returns:
        Dict with domain, matched_profile, and specialist responses.
    """
    query = args.get("query", "")
    zeus_answer = args.get("zeus_answer", "")
    all_profiles = args.get("all_profiles", False)

    domain = _detect_domain(query)
    matched_profile = DOMAIN_MAP.get(domain) if domain != "unknown" else None

    result: dict[str, Any] = {
        "domain": domain,
        "matched_profile": matched_profile,
        "specialist_responses": {},
    }

    if matched_profile and not all_profiles:
        prompt = SPECIALIST_PROMPT.format(query=query, zeus_answer=zeus_answer)
        response = _call_profile(matched_profile, prompt)
        if response and not _is_no_match(response):
            result["specialist_responses"][matched_profile] = response

    if all_profiles:
        for profile in SPECIALIST_PROFILES:
            prompt = SPECIALIST_PROMPT.format(query=query, zeus_answer=zeus_answer)
            response = _call_profile(profile, prompt)
            if response and not _is_no_match(response):
                result["specialist_responses"][profile] = response

    return result
