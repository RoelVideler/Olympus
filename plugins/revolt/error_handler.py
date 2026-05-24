"""Error handling utilities for the Revolt platform adapter.

Provides:
- Connection retry with exponential backoff (max 5 retries, base 2s)
- Auth failure detection (stop retrying, log error)
- Rate limit handling (parse Retry-After header, wait, retry)
"""

import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)

MAX_RETRIES = 5
BASE_BACKOFF_SECONDS = 2


class RevoltErrorHandler:
    """Manages connection retry logic with exponential backoff."""

    def __init__(self):
        self._retry_count = 0
        self._last_error_time: float = 0

    def get_backoff(self) -> float:
        """Calculate the backoff delay for the next retry.

        Uses exponential backoff: base * 2^retry_count, capped at max retries.
        Returns the delay in seconds, or -1 if max retries exceeded.
        """
        if self._retry_count >= MAX_RETRIES:
            logger.error(
                "Revolt: max retries (%d) exceeded. Stopping reconnect attempts.",
                MAX_RETRIES,
            )
            return -1

        delay = BASE_BACKOFF_SECONDS * (2 ** self._retry_count)
        self._retry_count += 1
        self._last_error_time = time.time()

        logger.info("Revolt: retry attempt %d/%d, backoff %.0fs", self._retry_count, MAX_RETRIES, delay)
        return delay

    def reset(self) -> None:
        """Reset the retry counter after a successful connection."""
        self._retry_count = 0
        self._last_error_time = 0

    @property
    def retry_count(self) -> int:
        return self._retry_count

    @property
    def is_exhausted(self) -> bool:
        return self._retry_count >= MAX_RETRIES


def is_auth_error(error: Exception) -> bool:
    """Check if an error indicates an authentication failure.

    Auth errors should not be retried — the token is invalid or expired.
    """
    error_str = str(error).lower()
    auth_indicators = [
        "401",
        "unauthorized",
        "invalid token",
        "bot token",
        "authentication failed",
        "token expired",
        "invalid session",
    ]
    return any(indicator in error_str for indicator in auth_indicators)


def parse_retry_after(error: Exception) -> Optional[float]:
    """Parse a rate limit retry delay from an error.

    Returns the number of seconds to wait, or None if not a rate limit error.
    """
    error_str = str(error).lower()
    if "429" not in error_str and "rate limit" not in error_str and "retry-after" not in error_str:
        return None

    # Try to extract the retry-after value
    import re
    match = re.search(r"retry[- ]?after[:\s]*(\d+)", error_str)
    if match:
        return float(match.group(1))

    # Default rate limit backoff
    return 5.0
