"""Message routing for the Revolt platform adapter.

Routes incoming Revolt messages to the Zeus profile by default.
Handles DMs and group channel mentions.
Forwards Zeus responses back to Revolt.
"""

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Default profile for all Revolt messages
DEFAULT_PROFILE = "zeus"


class RevoltMessageRouter:
    """Routes Revolt messages to Hermes profiles.

    All messages route to Zeus by default. Future extensions could add:
    - Channel-specific routing rules
    - User-based routing
    - Command-based routing (e.g., /chronos routes to Chronos profile)
    """

    def __init__(self, default_profile: str = DEFAULT_PROFILE):
        self._default_profile = default_profile
        self._routing_rules: Dict[str, str] = {}

    def add_rule(self, channel_id: str, profile: str) -> None:
        """Add a routing rule for a specific channel."""
        self._routing_rules[channel_id] = profile
        logger.info("Revolt routing rule: channel %s -> profile %s", channel_id, profile)

    def remove_rule(self, channel_id: str) -> None:
        """Remove a routing rule."""
        self._routing_rules.pop(channel_id, None)

    def resolve_profile(self, message: Dict[str, Any]) -> str:
        """Determine which profile should handle this message.

        Checks:
        1. Channel-specific routing rules
        2. Bot mentions in group channels
        3. Default profile (Zeus)

        Args:
            message: The raw Revolt message payload.

        Returns:
            The profile name that should handle this message.
        """
        channel_id = message.get("channel", "")

        # Check channel-specific rules first
        if channel_id in self._routing_rules:
            return self._routing_rules[channel_id]

        # Check for bot mention in group channels
        channel_type = message.get("channel_type", "")
        if channel_type == "Group":
            content = message.get("content", "")
            if self._is_bot_mentioned(content, message):
                return self._default_profile
            return ""  # No mention in group, ignore

        # DMs and default: route to Zeus
        return self._default_profile

    def _is_bot_mentioned(self, content: str, message: Dict[str, Any]) -> bool:
        """Check if the bot is mentioned in the message content.

        Revolt mentions use the format <@user_id>.
        """
        bot_id = message.get("bot_id", "")
        if bot_id and f"<@{bot_id}>" in content:
            return True

        # Also check for @name mentions (less reliable but useful)
        bot_name = message.get("bot_name", "").lower()
        if bot_name and f"@{bot_name}" in content.lower():
            return True

        return False

    def should_respond(self, message: Dict[str, Any], bot_user_id: str) -> bool:
        """Determine if the bot should respond to this message.

        Returns True for:
        - Direct messages to the bot
        - Group messages where the bot is mentioned
        - Messages in channels with routing rules

        Returns False for:
        - Messages from the bot itself
        - Group messages without bot mention
        """
        author_id = message.get("author", "")
        if author_id == bot_user_id:
            return False

        channel_type = message.get("channel_type", "")

        # Always respond to DMs
        if channel_type in ("DirectMessage", "DirectMessageGroup"):
            return True

        # In groups/channels, only respond if mentioned or has routing rule
        channel_id = message.get("channel", "")
        if channel_id in self._routing_rules:
            return True

        return self._is_bot_mentioned(message.get("content", ""), message)


# Module-level singleton for use in adapter
_router: Optional[RevoltMessageRouter] = None


def get_router() -> RevoltMessageRouter:
    """Get or create the message router singleton."""
    global _router
    if _router is None:
        _router = RevoltMessageRouter()
    return _router


def reset_router() -> None:
    """Reset the router singleton (useful for testing)."""
    global _router
    _router = None
