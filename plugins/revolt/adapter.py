"""Revolt platform adapter (Hermes plugin).

Connects to Revolt (open-source, self-hostable, Discord-like messaging)
via REST API and WebSocket. Routes all messages to the Zeus profile by
default and sends responses back to the originating Revolt channel.

No official Python SDK exists — this adapter implements raw HTTP/WebSocket
using aiohttp (already a Hermes dependency).

Configuration in config.yaml::

    platforms:
      revolt:
        enabled: true
        extra:
          bot_token: "YOUR_BOT_TOKEN"
          api_url: "https://api.revolt.chat"   # or self-hosted URL
          ws_url: "wss://ws.revolt.chat"        # or self-hosted WS URL
          bot_name: "Olympus"                   # optional display name
          bot_avatar: "https://..."             # optional avatar URL

Environment variables (env wins over config.yaml extra):

    REVOLT_BOT_TOKEN       Bot authentication token (required)
    REVOLT_API_URL         REST API base URL (default: https://api.revolt.chat)
    REVOLT_WS_URL          WebSocket URL (default: wss://ws.revolt.chat)
    REVOLT_BOT_NAME        Bot display name
    REVOLT_BOT_AVATAR      Bot avatar URL
    REVOLT_ALLOWED_USERS   Comma-separated allowlist of user IDs
    REVOLT_ALLOW_ALL_USERS Allow any user (dev only)
"""

import asyncio
import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False
    aiohttp = None  # type: ignore[assignment]

from gateway.config import Platform, PlatformConfig
from gateway.platforms.base import (
    BasePlatformAdapter,
    MessageEvent,
    MessageType,
    SendResult,
)

from .client import RevoltClient
from .error_handler import RevoltErrorHandler, is_auth_error, parse_retry_after

logger = logging.getLogger(__name__)

DEFAULT_API_URL = "https://api.revolt.chat"
DEFAULT_WS_URL = "wss://ws.revolt.chat"
MAX_MESSAGE_LENGTH = 2000  # Revolt message limit


def check_requirements() -> bool:
    """Check whether the Revolt adapter is installable and minimally configured."""
    if not AIOHTTP_AVAILABLE:
        return False
    token = os.getenv("REVOLT_BOT_TOKEN", "").strip()
    return bool(token)


def validate_config(config) -> bool:
    """Validate that the configured Revolt platform has a bot token."""
    extra = getattr(config, "extra", {}) or {}
    token = extra.get("bot_token") or os.getenv("REVOLT_BOT_TOKEN", "")
    return bool(token)


def is_connected(config) -> bool:
    """Check whether Revolt is configured (env or config.yaml)."""
    extra = getattr(config, "extra", {}) or {}
    token = os.getenv("REVOLT_BOT_TOKEN") or extra.get("bot_token", "")
    return bool(token)


class RevoltAdapter(BasePlatformAdapter):
    """Revolt platform adapter.

    Connects to Revolt via WebSocket for real-time events and REST API
    for sending messages. All incoming messages route to Zeus by default.
    """

    MAX_MESSAGE_LENGTH = MAX_MESSAGE_LENGTH

    def __init__(self, config: PlatformConfig):
        platform = Platform("revolt")
        super().__init__(config=config, platform=platform)

        extra = config.extra or {}
        self._bot_token: str = (
            extra.get("bot_token")
            or os.getenv("REVOLT_BOT_TOKEN", "")
        )
        self._api_url: str = (
            extra.get("api_url")
            or os.getenv("REVOLT_API_URL", DEFAULT_API_URL)
        ).rstrip("/")
        self._ws_url: str = (
            extra.get("ws_url")
            or os.getenv("REVOLT_WS_URL", DEFAULT_WS_URL)
        )
        self._bot_name: str = (
            extra.get("bot_name")
            or os.getenv("REVOLT_BOT_NAME", "Olympus")
        )
        self._bot_avatar: str = (
            extra.get("bot_avatar")
            or os.getenv("REVOLT_BOT_AVATAR", "")
        )

        # User allowlist: comma-separated user IDs, or empty for all users
        allow_all = os.getenv("REVOLT_ALLOW_ALL_USERS", "").lower() in ("1", "true", "yes")
        allowed_users_str = os.getenv("REVOLT_ALLOWED_USERS", "").strip()
        if allow_all:
            self._allowed_users: Optional[set] = None  # None = allow all
        elif allowed_users_str:
            self._allowed_users = {u.strip() for u in allowed_users_str.split(",") if u.strip()}
        else:
            self._allowed_users = None  # No allowlist configured = allow all

        self._client: Optional[RevoltClient] = None
        self._ws_task: Optional[asyncio.Task] = None
        self._error_handler = RevoltErrorHandler()

    # -- Connection lifecycle -----------------------------------------------

    async def connect(self) -> bool:
        """Connect to Revolt by authenticating and starting the WebSocket listener."""
        if not AIOHTTP_AVAILABLE:
            logger.warning("[%s] aiohttp not installed. Run: pip install aiohttp", self.name)
            return False
        if not self._bot_token:
            logger.warning("[%s] REVOLT_BOT_TOKEN not configured", self.name)
            return False

        try:
            self._client = RevoltClient(
                bot_token=self._bot_token,
                api_url=self._api_url,
                ws_url=self._ws_url,
            )

            # Authenticate and get bot user info
            auth_ok = await self._client.authenticate()
            if not auth_ok:
                logger.error("[%s] Authentication failed — check REVOLT_BOT_TOKEN", self.name)
                self._set_fatal_error(
                    "revolt_auth_failed",
                    "Revolt authentication failed. Check REVOLT_BOT_TOKEN.",
                    retryable=False,
                )
                return False

            # Set bot identity if configured
            if self._bot_name or self._bot_avatar:
                await self._set_bot_identity()

            # Start WebSocket event listener
            self._ws_task = asyncio.create_task(self._run_websocket())
            self._mark_connected()
            logger.info("[%s] Connected — listening on %s", self.name, self._ws_url)
            return True

        except Exception as e:
            logger.error("[%s] Failed to connect: %s", self.name, e)
            return False

    async def _set_bot_identity(self) -> None:
        """Set bot name and avatar via REST API."""
        if not self._client:
            return
        try:
            if self._bot_name:
                await self._client.update_bot_name(self._bot_name)
            if self._bot_avatar:
                await self._client.update_bot_avatar(self._bot_avatar)
            logger.info("[%s] Bot identity set: name=%s", self.name, self._bot_name)
        except Exception as e:
            logger.warning("[%s] Failed to set bot identity: %s", self.name, e)

    async def _run_websocket(self) -> None:
        """Run the WebSocket event loop with reconnection logic."""
        while self._running:
            try:
                await self._client.handle_events(self._on_revolt_event)
                # Successful connection — reset retry counter
                self._error_handler.reset()
            except asyncio.CancelledError:
                return
            except Exception as e:
                if not self._running:
                    return

                if is_auth_error(e):
                    logger.error("[%s] Authentication error — stopping reconnect: %s", self.name, e)
                    self._set_fatal_error(
                        "revolt_auth_error",
                        f"Revolt auth error: {e}",
                        retryable=False,
                    )
                    self._running = False
                    return

                retry_after = parse_retry_after(e)
                if retry_after:
                    logger.info("[%s] Rate limited — waiting %ds", self.name, retry_after)
                    await asyncio.sleep(retry_after)
                    continue

                delay = self._error_handler.get_backoff()
                if delay < 0:
                    logger.error("[%s] Max retries exceeded — stopping reconnect", self.name)
                    self._running = False
                    return
                logger.warning("[%s] WebSocket error: %s — reconnecting in %ds", self.name, e, delay)
                await asyncio.sleep(delay)

    async def _on_revolt_event(self, event: Dict[str, Any]) -> None:
        """Process a Revolt WebSocket event and dispatch messages to Hermes."""
        event_type = event.get("type")

        if event_type == "Message":
            await self._on_message(event.get("payload", {}))
        elif event_type == "Ping":
            pass  # Heartbeat handled by client
        else:
            logger.debug("[%s] Unhandled event type: %s", self.name, event_type)

    async def _on_message(self, payload: Dict[str, Any]) -> None:
        """Process an incoming Revolt message."""
        msg_id = payload.get("_id") or payload.get("id", "")
        if not msg_id:
            return

        # Skip messages from the bot itself
        author_id = payload.get("author", "")
        if self._client and author_id == self._client.bot_user_id:
            return

        # Enforce user allowlist
        if self._allowed_users is not None and author_id not in self._allowed_users:
            logger.debug("[%s] Ignoring message from unauthorized user %s", self.name, author_id)
            return

        text = (payload.get("content") or "").strip()
        if not text:
            return

        channel_id = payload.get("channel", "")
        if not channel_id:
            return

        # Determine channel type
        channel_type = payload.get("channel_type", "")
        if channel_type in ("DirectMessage", "DirectMessageGroup"):
            chat_type = "dm"
        else:
            chat_type = "channel"

        # Get user info
        user_id = author_id
        user_name = payload.get("author_name", author_id[:8])

        source = self.build_source(
            chat_id=channel_id,
            chat_name=channel_id,
            chat_type=chat_type,
            user_id=user_id,
            user_name=user_name,
        )

        timestamp = datetime.now(tz=timezone.utc)
        ts_str = payload.get("created_at", "")
        if ts_str:
            try:
                # Revolt uses snowflake IDs that embed timestamps
                timestamp = datetime.fromtimestamp(
                    int(ts_str) / 1000, tz=timezone.utc
                )
            except (ValueError, OSError):
                pass

        message_event = MessageEvent(
            text=text,
            message_type=MessageType.TEXT,
            source=source,
            message_id=msg_id,
            raw_message=payload,
            timestamp=timestamp,
        )

        logger.debug("[%s] Message from %s in %s: %s", self.name, user_name, channel_id, text[:80])
        await self.handle_message(message_event)

    async def disconnect(self) -> None:
        """Disconnect from Revolt."""
        self._running = False
        self._mark_disconnected()

        if self._ws_task:
            self._ws_task.cancel()
            try:
                await self._ws_task
            except asyncio.CancelledError:
                pass
            self._ws_task = None

        if self._client:
            await self._client.close()
            self._client = None

        logger.info("[%s] Disconnected", self.name)

    # -- Outbound messaging -------------------------------------------------

    async def send(
        self,
        chat_id: str,
        content: str,
        reply_to: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SendResult:
        """Send a message to a Revolt channel."""
        if not self._client:
            return SendResult(success=False, error="Revolt client not initialized")

        if len(content) > MAX_MESSAGE_LENGTH:
            logger.warning(
                "[%s] Message truncated from %d to %d chars (Revolt limit)",
                self.name, len(content), MAX_MESSAGE_LENGTH,
            )
            content = content[:MAX_MESSAGE_LENGTH]

        try:
            result = await self._client.send_message(
                channel_id=chat_id,
                content=content,
                reply_to=reply_to,
            )
            if result:
                return SendResult(success=True, message_id=result)
            return SendResult(success=False, error="Failed to send message")
        except Exception as e:
            logger.error("[%s] Send error: %s", self.name, e)
            return SendResult(success=False, error=str(e))

    async def send_typing(self, chat_id: str, metadata=None) -> None:
        """Send typing indicator to Revolt channel."""
        if not self._client:
            return
        try:
            await self._client.send_typing(chat_id)
        except Exception as e:
            logger.debug("[%s] Typing indicator failed: %s", self.name, e)

    async def get_chat_info(self, chat_id: str) -> Dict[str, Any]:
        """Return basic info about a Revolt channel."""
        if not self._client:
            return {"name": chat_id, "type": "unknown"}
        try:
            info = await self._client.get_channel(chat_id)
            return {
                "name": info.get("name", chat_id),
                "type": info.get("channel_type", "unknown"),
            }
        except Exception:
            return {"name": chat_id, "type": "unknown"}


# ---------------------------------------------------------------------------
# Plugin registration
# ---------------------------------------------------------------------------


def _env_enablement() -> dict | None:
    """Seed PlatformConfig.extra from env vars during gateway config load."""
    token = os.getenv("REVOLT_BOT_TOKEN", "").strip()
    if not token:
        return None
    seed: dict = {
        "bot_token": token,
    }
    api_url = os.getenv("REVOLT_API_URL", "").strip()
    if api_url:
        seed["api_url"] = api_url
    ws_url = os.getenv("REVOLT_WS_URL", "").strip()
    if ws_url:
        seed["ws_url"] = ws_url
    bot_name = os.getenv("REVOLT_BOT_NAME", "").strip()
    if bot_name:
        seed["bot_name"] = bot_name
    bot_avatar = os.getenv("REVOLT_BOT_AVATAR", "").strip()
    if bot_avatar:
        seed["bot_avatar"] = bot_avatar
    return seed


def register(ctx) -> None:
    """Plugin entry point — called by the Hermes plugin system at startup."""
    ctx.register_platform(
        name="revolt",
        label="Revolt",
        adapter_factory=lambda cfg: RevoltAdapter(cfg),
        check_fn=check_requirements,
        validate_config=validate_config,
        is_connected=is_connected,
        required_env=["REVOLT_BOT_TOKEN"],
        install_hint="pip install aiohttp   # already a Hermes dependency",
        env_enablement_fn=_env_enablement,
        max_message_length=MAX_MESSAGE_LENGTH,
        emoji="💬",
        platform_hint=(
            "You are communicating via Revolt messaging. "
            "Revolt supports markdown in messages. "
            f"Keep responses under {MAX_MESSAGE_LENGTH} characters. "
            "All messages route to the Zeus profile by default."
        ),
    )
