"""Bot identity configuration for the Revolt platform adapter.

Manages bot identity (name, avatar) and presence/status.
Reads from plugin config or environment variables.
"""

import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class RevoltBotIdentity:
    """Manages the bot's identity configuration for Revolt.

    Identity can be configured via:
    1. Plugin config (config.yaml extra section)
    2. Environment variables (REVOLT_BOT_NAME, REVOLT_BOT_AVATAR, REVOLT_BOT_STATUS)

    Environment variables take precedence over config values.
    """

    def __init__(self, config_extra: Optional[Dict[str, Any]] = None):
        config_extra = config_extra or {}

        self.name: str = (
            os.getenv("REVOLT_BOT_NAME", "")
            or config_extra.get("bot_name", "")
            or "Olympus"
        )

        self.avatar_url: str = (
            os.getenv("REVOLT_BOT_AVATAR", "")
            or config_extra.get("bot_avatar", "")
            or ""
        )

        self.status: str = (
            os.getenv("REVOLT_BOT_STATUS", "")
            or config_extra.get("bot_status", "")
            or "online"
        )

        self.status_text: str = (
            os.getenv("REVOLT_BOT_STATUS_TEXT", "")
            or config_extra.get("bot_status_text", "")
            or "Powered by Olympus"
        )

    def to_dict(self) -> Dict[str, str]:
        """Return identity as a dictionary for API calls."""
        result: Dict[str, str] = {"username": self.name}
        if self.avatar_url:
            result["avatar"] = self.avatar_url
        return result

    def presence_payload(self) -> Dict[str, str]:
        """Return presence/status payload for the API."""
        return {
            "status": self.status,
            "text": self.status_text,
        }

    def is_configured(self) -> bool:
        """Return True if custom identity is configured."""
        return bool(
            os.getenv("REVOLT_BOT_NAME")
            or os.getenv("REVOLT_BOT_AVATAR")
            or self.name != "Olympus"
            or self.avatar_url
        )

    def __repr__(self) -> str:
        return f"RevoltBotIdentity(name={self.name!r}, status={self.status!r})"
