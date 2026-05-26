"""Hermes communication plugin.

Registers the gmail_triage tool for email triage, reading, and drafting.
Registers the whatsapp_safety tool for WhatsApp message safety scanning.
Registers the whatsapp_reader tool for reading WhatsApp messages with safety shielding.
Never sends emails autonomously — drafts only.
"""

from __future__ import annotations

from .skills.gmail_triage import GMAIL_TRIAGE_SCHEMA, handle_gmail_triage
from .skills.whatsapp_reader import WHATSAPP_READER_SCHEMA, handle_whatsapp_reader
from .skills.whatsapp_safety import WHATSAPP_SAFETY_SCHEMA, handle_whatsapp_safety


def register(ctx) -> None:
    """Register Hermes tools. Called once by the plugin loader."""

    ctx.register_tool(
        name="gmail_triage",
        toolset="hermes",
        schema=GMAIL_TRIAGE_SCHEMA,
        handler=handle_gmail_triage,
        description="Triage Gmail inbox, read emails, and draft replies. Never sends emails autonomously.",
    )

    ctx.register_tool(
        name="whatsapp_safety",
        toolset="hermes",
        schema=WHATSAPP_SAFETY_SCHEMA,
        handler=handle_whatsapp_safety,
        description="Scan WhatsApp messages for safety threats including prompt injection, phishing, and social engineering.",
    )

    ctx.register_tool(
        name="whatsapp_reader",
        toolset="hermes",
        schema=WHATSAPP_READER_SCHEMA,
        handler=handle_whatsapp_reader,
        description="Read WhatsApp messages, list chats, and search contacts. All messages are safety-scanned before return.",
    )
