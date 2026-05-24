"""Zeus orchestrator plugin — routing and chip-in coordination for Olympus.

Registers the routing and chip_in tools into the zeus toolset.
Zeus uses these skills to poll specialist profiles and coordinate chip-in responses.
"""

from __future__ import annotations

from .skills.routing import ROUTING_SCHEMA, handle_routing
from .skills.chip_in import CHIP_IN_SCHEMA, handle_chip_in


def register(ctx) -> None:
    """Register Zeus orchestrator tools. Called once by the plugin loader."""

    ctx.register_tool(
        name="routing",
        toolset="zeus",
        schema=ROUTING_SCHEMA,
        handler=handle_routing,
        description="Route a query to specialist profiles via polling and return routing decisions.",
    )

    ctx.register_tool(
        name="chip_in",
        toolset="zeus",
        schema=CHIP_IN_SCHEMA,
        handler=handle_chip_in,
        description="Poll all specialist profiles in parallel for chip-in relevance scores and insights.",
    )
