"""Revolt platform adapter — Hermes gateway plugin for the Revolt messaging platform.

Connects to Revolt (open-source, self-hostable, Discord-like) via REST API
and WebSocket for real-time events. Routes all messages to the Zeus profile
by default.

No official Python SDK exists — this plugin implements raw HTTP/WebSocket
client using aiohttp (already a Hermes dependency).
"""

from .adapter import register

__all__ = ["register"]
