"""Hephaestus home management plugin.

Registers the home_maintenance tool for tracking maintenance schedules,
logging device history, and sharing maintenance facts.
"""

from __future__ import annotations

from .skills.home_maintenance import HOME_MAINTENANCE_SCHEMA, handle_home_maintenance


def register(ctx) -> None:
    """Register Hephaestus tools. Called once by the plugin loader."""

    ctx.register_tool(
        name="home_maintenance",
        toolset="hephaestus",
        schema=HOME_MAINTENANCE_SCHEMA,
        handler=handle_home_maintenance,
        description="Track home maintenance events, schedules, and reminders.",
    )
