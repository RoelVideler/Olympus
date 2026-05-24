"""Share knowledge plugin — cross-agent knowledge sharing for Olympus.

Registers the share_knowledge tool into the share_knowledge toolset.
Agents can write, query, and delete shared facts via the Olympus SQLite database.

Scope enforcement: Each profile's allowed scopes are loaded from scopes.json.
The calling profile is identified via Hermes' get_active_profile_name().
"""

from __future__ import annotations

import json
from pathlib import Path

from .tools import (
    SHARE_KNOWLEDGE_SCHEMA,
    _handle_share_knowledge,
    load_scope_config,
)

# Scope configuration file location
_PLUGIN_DIR = Path(__file__).resolve().parent
_SCOPES_FILE = _PLUGIN_DIR / "scopes.json"


def _default_scopes() -> dict[str, dict[str, list[str]]]:
    """Default scope configuration for all Olympus profiles."""
    return {
        "zeus": {"read": ["personal", "business", "global"], "write": ["personal", "business", "global"]},
        "chronos": {"read": ["personal", "global"], "write": ["personal", "global"]},
        "iaso": {"read": ["personal", "global"], "write": ["personal"]},
        "hermes-agent": {"read": ["personal", "global"], "write": ["personal", "global"]},
        "philia": {"read": ["personal", "global"], "write": ["personal"]},
        "plutus": {"read": ["personal", "global"], "write": ["personal"]},
        "hephaestus": {"read": ["personal", "global"], "write": ["personal"]},
        "metis": {"read": ["business", "global"], "write": ["business", "global"]},
        "apollo": {"read": ["business", "global"], "write": ["business"]},
        "midas": {"read": ["business", "global"], "write": ["business"]},
    }


def _ensure_scopes_file() -> None:
    """Create scopes.json if it doesn't exist."""
    if not _SCOPES_FILE.exists():
        with open(_SCOPES_FILE, "w") as f:
            json.dump(_default_scopes(), f, indent=2)


def register(ctx) -> None:
    """Register the share_knowledge tool. Called once by the plugin loader."""
    _ensure_scopes_file()

    # Load scope config and pass it to the handler via closure
    scope_config = load_scope_config(str(_SCOPES_FILE))

    def scoped_handler(args: dict, **kw) -> str:
        return _handle_share_knowledge(args, scope_config=scope_config, **kw)

    ctx.register_tool(
        name="share_knowledge",
        toolset="share_knowledge",
        schema=SHARE_KNOWLEDGE_SCHEMA,
        handler=scoped_handler,
        description="Write, query, or delete cross-agent knowledge facts.",
    )
