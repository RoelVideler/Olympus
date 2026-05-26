"""Chronos scheduling plugin.

Registers the calendar_query tool for Google Calendar read-only access.
"""

from __future__ import annotations

from .skills.calendar_query import CALENDAR_QUERY_SCHEMA, handle_calendar_query


def register(ctx) -> None:
    """Register Chronos tools. Called once by the plugin loader."""

    ctx.register_tool(
        name="calendar_query",
        toolset="chronos",
        schema=CALENDAR_QUERY_SCHEMA,
        handler=handle_calendar_query,
        description="Query Google Calendar for events, calendars, and availability. Read-only.",
    )
