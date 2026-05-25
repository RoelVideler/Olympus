"""Tests for plugins/zeus/skills/chip_in.py."""

import json
from unittest.mock import patch, MagicMock, AsyncMock
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "plugins" / "zeus" / "skills"))


class TestChipInWithZeusAnswer:
    """Test chip_in tool with zeus_answer parameter."""

    def test_chip_in_accepts_zeus_answer(self):
        """handle_chip_in accepts zeus_answer parameter."""
        from chip_in import handle_chip_in

        async def mock_call(*args, **kwargs):
            return {"profile": "chronos", "score": 0.8, "insight": "Added detail."}

        with patch("chip_in._call_profile_async", new_callable=AsyncMock, side_effect=mock_call):
            result = handle_chip_in({
                "query": "What's my schedule?",
                "zeus_answer": "You have meetings.",
            })

        assert result["query"] == "What's my schedule?"
        assert len(result["chip_ins"]) == 8
        assert result["chip_ins"][0]["insight"] == "Added detail."

    def test_chip_in_passes_zeus_answer_to_specialist(self):
        """The chip_in prompt includes Zeus's answer."""
        from chip_in import CHIP_IN_PROMPT

        prompt = CHIP_IN_PROMPT.format(
            query="Test query",
            zeus_answer="Zeus's answer here.",
        )

        assert "Zeus's answer: Zeus's answer here." in prompt
        assert "Test query" in prompt
        assert "score" in prompt
        assert "insight" in prompt

    def test_chip_in_scoring_with_nothing_to_add(self):
        """Score 0.3 when Zeus is correct but nothing to add."""
        from chip_in import handle_chip_in

        async def mock_call(*args, **kwargs):
            return {"profile": "chronos", "score": 0.3, "insight": None}

        with patch("chip_in._call_profile_async", new_callable=AsyncMock, side_effect=mock_call):
            result = handle_chip_in({
                "query": "Test",
                "zeus_answer": "Correct answer.",
                "threshold": 0.5,
            })

        # Score 0.3 is below threshold, should not appear in chip_ins
        assert len(result["chip_ins"]) == 0
