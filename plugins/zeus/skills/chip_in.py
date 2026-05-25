"""Chip-in coordination skill — polls specialist profiles for relevance scores and insights.

After Zeus responds to a user message, this skill polls all 8 specialist profiles in parallel.
Each profile evaluates relevance and returns (score, insight) or "no match".
Zeus streams relevant chip-ins (score > threshold) to the user.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import json
import subprocess
from typing import Any

CHIP_IN_SCHEMA = {
    "name": "chip_in",
    "description": "Poll all specialist profiles in parallel for chip-in relevance scores and insights.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The user query to evaluate for chip-in relevance.",
            },
            "zeus_answer": {
                "type": "string",
                "description": "Zeus's initial answer to the query, for specialists to review and refine.",
                "default": "",
            },
            "threshold": {
                "type": "number",
                "description": "Minimum relevance score (0-1) to include a chip-in. Default 0.5.",
                "default": 0.5,
            },
            "timeout": {
                "type": "integer",
                "description": "Max seconds to wait for each profile. Default 15.",
                "default": 15,
            },
        },
        "required": ["query"],
    },
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

CHIP_IN_PROMPT = (
    "You are evaluating whether a user query is relevant to your domain. "
    "Zeus has already provided this initial answer:\n\n"
    "Query: {query}\n"
    "Zeus's answer: {zeus_answer}\n\n"
    "Respond in this exact JSON format:\n"
    '{{"score": <0.0-1.0>, "insight": "<your review or null>"}}\n\n'
    "Rules:\n"
    "- If the query is NOT relevant to your domain, set score to 0.0 and insight to null.\n"
    "- If Zeus's answer is correct but you have nothing to add, set score to 0.3 and insight to null.\n"
    "- If Zeus's answer needs correction or you have valuable domain-specific detail, set score 0.5-1.0 and provide your insight.\n"
    "- Be thorough but concise — give as much detail as the situation requires.\n"
    "- Respond with ONLY valid JSON, no other text.\n\n"
    "Query: {query}"
)


async def _call_profile_async(profile: str, prompt: str, timeout: int = 15) -> dict[str, Any]:
    """Async wrapper around subprocess call to a specialist profile."""
    loop = asyncio.get_event_loop()
    try:
        result = await asyncio.wait_for(
            loop.run_in_executor(
                None,
                lambda: subprocess.run(
                    ["hermes", "-p", profile, "-z", prompt],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                ),
            ),
            timeout=timeout + 2,
        )
        if result.returncode == 0:
            output = result.stdout.strip()
            try:
                parsed = json.loads(output)
                return {
                    "profile": profile,
                    "score": parsed.get("score", 0.0),
                    "insight": parsed.get("insight"),
                }
            except (json.JSONDecodeError, AttributeError):
                return {"profile": profile, "score": 0.0, "insight": None}
        return {"profile": profile, "score": 0.0, "insight": None}
    except (asyncio.TimeoutError, subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return {"profile": profile, "score": 0.0, "insight": None}


def handle_chip_in(args: dict, **kw) -> dict[str, Any]:
    """Handle a chip-in polling request.

    Polls all specialist profiles in parallel and returns those above the threshold.

    Args:
        args: Dict with 'query', optional 'zeus_answer', optional 'threshold' (default 0.5),
              optional 'timeout' (default 15).

    Returns:
        Dict with chip_ins list (sorted by score descending) and metadata.
    """
    query = args.get("query", "")
    zeus_answer = args.get("zeus_answer", "")
    threshold = args.get("threshold", 0.5)
    timeout = args.get("timeout", 15)

    prompt = CHIP_IN_PROMPT.format(query=query, zeus_answer=zeus_answer)

    async def _run() -> list[dict[str, Any]]:
        tasks = [
            _call_profile_async(profile, prompt, timeout)
            for profile in SPECIALIST_PROFILES
        ]
        return await asyncio.gather(*tasks)

    # Detect if we're already in an async context (e.g., called from Hermes'
    # event loop). asyncio.run() raises RuntimeError in that case.
    try:
        asyncio.get_running_loop()
        # In async context — run the coroutine in a new thread to avoid
        # "event loop already running" error from run_until_complete().
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(asyncio.run, _run())
            results = future.result(timeout=timeout + 5)
    except RuntimeError:
        # No running loop — safe to use asyncio.run()
        results = asyncio.run(_run())

    chip_ins = [
        r for r in results
        if r["score"] >= threshold and r["insight"] is not None
    ]
    chip_ins.sort(key=lambda x: x["score"], reverse=True)

    return {
        "query": query,
        "threshold": threshold,
        "chip_ins": chip_ins,
        "total_polled": len(SPECIALIST_PROFILES),
        "relevant_count": len(chip_ins),
    }
