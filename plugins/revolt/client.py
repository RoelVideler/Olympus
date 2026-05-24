"""Revolt REST API and WebSocket client.

No official Python SDK exists for Revolt. This client implements:
- REST API calls via aiohttp
- WebSocket connection for real-time events
- Bot token authentication
- Configurable base URL for self-hosted instances

Revolt API: https://developers.revolt.chat/api.html
"""

import asyncio
import json
import logging
from typing import Any, Callable, Dict, Optional

import aiohttp

logger = logging.getLogger(__name__)

REVOLT_API_VERSION = "v1"


class RevoltClient:
    """Minimal Revolt API client using aiohttp.

    Supports both REST API calls and WebSocket event streaming.
    """

    def __init__(
        self,
        bot_token: str,
        api_url: str = "https://api.revolt.chat",
        ws_url: str = "wss://ws.revolt.chat",
    ):
        self._bot_token = bot_token
        self._api_url = api_url
        self._ws_url = ws_url
        self._session: Optional[aiohttp.ClientSession] = None
        self._ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self.bot_user_id: str = ""
        self._headers: Dict[str, str] = {}

    async def authenticate(self) -> bool:
        """Authenticate with the bot token and fetch user info.

        Returns True if authentication succeeded, False otherwise.
        """
        self._headers = {
            "x-bot-token": self._bot_token,
            "Content-Type": "application/json",
        }

        try:
            self._session = aiohttp.ClientSession()
            async with self._session.get(
                f"{self._api_url}/{REVOLT_API_VERSION}/auth/account",
                headers=self._headers,
            ) as resp:
                if resp.status == 401:
                    logger.error("Revolt auth failed: invalid bot token")
                    await self._session.close()
                    self._session = None
                    return False
                if resp.status == 429:
                    retry_after = _parse_retry_after_header(resp)
                    logger.warning("Revolt rate limited: retry after %ds", retry_after)
                    await self._session.close()
                    self._session = None
                    return False
                if resp.status >= 400:
                    logger.error("Revolt auth failed: HTTP %d", resp.status)
                    await self._session.close()
                    self._session = None
                    return False

                data = await resp.json()
                self.bot_user_id = data.get("_id", "")
                logger.info("Revolt authenticated as user %s", self.bot_user_id)
                return True

        except aiohttp.ClientError as e:
            logger.error("Revolt connection failed: %s", e)
            if self._session:
                await self._session.close()
                self._session = None
            return False

    async def send_message(
        self,
        channel_id: str,
        content: str,
        reply_to: Optional[str] = None,
    ) -> Optional[str]:
        """Send a message to a Revolt channel.

        Returns the message ID on success, None on failure.
        """
        if not self._session:
            logger.error("Cannot send message: session not initialized")
            return None

        payload: Dict[str, Any] = {"content": content}
        if reply_to:
            payload["replies"] = [reply_to]

        try:
            async with self._session.post(
                f"{self._api_url}/{REVOLT_API_VERSION}/channels/{channel_id}/messages",
                headers=self._headers,
                json=payload,
            ) as resp:
                if resp.status == 429:
                    retry_after = _parse_retry_after_header(resp)
                    logger.warning("Rate limited on send — waiting %ds", retry_after)
                    await asyncio.sleep(retry_after)
                    # Retry once
                    return await self.send_message(channel_id, content, reply_to)

                if resp.status >= 400:
                    body = await resp.text()
                    logger.error("Failed to send message: HTTP %d — %s", resp.status, body[:200])
                    return None

                data = await resp.json()
                return data.get("_id")

        except aiohttp.ClientError as e:
            logger.error("Send message failed: %s", e)
            return None

    async def send_typing(self, channel_id: str) -> None:
        """Send typing indicator to a channel."""
        if not self._session:
            return

        try:
            async with self._session.post(
                f"{self._api_url}/{REVOLT_API_VERSION}/channels/{channel_id}/typing",
                headers=self._headers,
            ) as resp:
                if resp.status >= 400:
                    logger.debug("Typing indicator failed: HTTP %d", resp.status)
        except aiohttp.ClientError:
            pass  # Typing indicator is non-critical

    async def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Fetch user information by ID."""
        if not self._session:
            return None

        try:
            async with self._session.get(
                f"{self._api_url}/{REVOLT_API_VERSION}/users/{user_id}",
                headers=self._headers,
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                return None
        except aiohttp.ClientError as e:
            logger.error("Get user failed: %s", e)
            return None

    async def get_channel(self, channel_id: str) -> Dict[str, Any]:
        """Fetch channel information."""
        if not self._session:
            return {"name": channel_id, "channel_type": "unknown"}

        try:
            async with self._session.get(
                f"{self._api_url}/{REVOLT_API_VERSION}/channels/{channel_id}",
                headers=self._headers,
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                return {"name": channel_id, "channel_type": "unknown"}
        except aiohttp.ClientError:
            return {"name": channel_id, "channel_type": "unknown"}

    async def update_bot_name(self, name: str) -> None:
        """Update the bot's display name."""
        if not self._session:
            return

        try:
            async with self._session.patch(
                f"{self._api_url}/{REVOLT_API_VERSION}/auth/account",
                headers=self._headers,
                json={"username": name},
            ) as resp:
                if resp.status >= 400:
                    logger.warning("Failed to update bot name: HTTP %d", resp.status)
        except aiohttp.ClientError as e:
            logger.warning("Failed to update bot name: %s", e)

    async def update_bot_avatar(self, avatar_url: str) -> None:
        """Update the bot's avatar by setting an avatar URL."""
        if not self._session:
            return

        try:
            async with self._session.patch(
                f"{self._api_url}/{REVOLT_API_VERSION}/auth/account",
                headers=self._headers,
                json={"avatar": {"url": avatar_url}},
            ) as resp:
                if resp.status >= 400:
                    logger.warning("Failed to update bot avatar: HTTP %d", resp.status)
        except aiohttp.ClientError as e:
            logger.warning("Failed to update bot avatar: %s", e)

    async def handle_events(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Connect to Revolt WebSocket and dispatch events to callback.

        This is a blocking call that runs until the connection is closed
        or cancelled.
        """
        if not self._session:
            logger.error("Cannot handle events: session not initialized")
            return

        logger.info("Connecting to Revolt WebSocket: %s", self._ws_url)

        async with self._session.ws_connect(
            self._ws_url,
            headers={"x-bot-token": self._bot_token},
            heartbeat=30,
        ) as ws:
            self._ws = ws
            logger.info("Revolt WebSocket connected")

            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    try:
                        event = json.loads(msg.data)
                        await callback(event)
                    except json.JSONDecodeError:
                        logger.debug("Invalid JSON from WebSocket: %s", msg.data[:100])
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    logger.error("WebSocket error: %s", ws.exception())
                    break
                elif msg.type == aiohttp.WSMsgType.CLOSED:
                    logger.info("WebSocket closed")
                    break

    async def close(self) -> None:
        """Close the HTTP session and WebSocket connection."""
        if self._ws:
            await self._ws.close()
            self._ws = None
        if self._session:
            await self._session.close()
            self._session = None


def _parse_retry_after_header(resp: aiohttp.ClientResponse) -> int:
    """Parse the Retry-After header from a response.

    Returns the number of seconds to wait, defaulting to 5 if not present.
    """
    retry_after = resp.headers.get("Retry-After", "5")
    try:
        return int(retry_after)
    except ValueError:
        return 5
