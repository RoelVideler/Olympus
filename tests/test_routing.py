"""Tests for plugins/zeus/skills/routing.py."""

from unittest.mock import patch
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "plugins" / "zeus" / "skills"))


class TestRoutingWithZeusAnswer:
    """Test routing tool with zeus_answer parameter."""

    def test_routing_accepts_zeus_answer(self):
        """handle_routing accepts zeus_answer parameter."""
        from routing import handle_routing

        with patch("routing._call_profile", return_value="Confirmed, accurate."):
            result = handle_routing({
                "query": "What's my schedule tomorrow?",
                "zeus_answer": "You have meetings at 10am and 2pm.",
            })

        assert result["domain"] == "scheduling"
        assert result["matched_profile"] == "chronos"
        assert "chronos" in result["specialist_responses"]

    def test_routing_passes_zeus_answer_to_specialist(self):
        """The specialist prompt includes Zeus's answer."""
        from routing import handle_routing, SPECIALIST_PROMPT

        captured_prompt = None

        def capture_prompt(profile, prompt, timeout=10):
            nonlocal captured_prompt
            captured_prompt = prompt
            return "Confirmed."

        with patch("routing._call_profile", side_effect=capture_prompt):
            handle_routing({
                "query": "Test query",
                "zeus_answer": "Zeus's answer here.",
            })

        assert "Zeus's answer: Zeus's answer here." in captured_prompt
        assert "Test query" in captured_prompt

    def test_routing_natural_language_no_match(self):
        """No-match detection uses natural language, not exact string."""
        from routing import _is_no_match

        assert _is_no_match("This is not within my domain expertise.")
        assert _is_no_match("That's not my area of expertise.")
        assert _is_no_match("I don't handle that topic.")
        assert not _is_no_match("Confirmed, accurate.")
        assert not _is_no_match("You should check with Plutus for this.")
