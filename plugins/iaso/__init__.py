"""Iaso health sync plugin.

Registers the withings_sync tool for fetching, storing, and querying
health data from Withings devices.
"""

from __future__ import annotations

from .skills.withings_sync import WITHINGS_SYNC_SCHEMA, handle_withings_sync


def register(ctx) -> None:
    """Register Iaso tools. Called once by the plugin loader."""

    ctx.register_tool(
        name="withings_sync",
        toolset="iaso",
        schema=WITHINGS_SYNC_SCHEMA,
        handler=handle_withings_sync,
        description="Sync and query health data from Withings devices.",
    )
