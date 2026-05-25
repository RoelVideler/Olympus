"""Integration tests for Phase 3a: Zeus delegation and chip-in review-refine."""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "plugins" / "zeus" / "skills"))

from routing import _detect_domain, handle_routing
from chip_in import CHIP_IN_PROMPT


class TestZeusDelegation:
    """Test Zeus delegation to specialists."""

    @pytest.mark.parametrize("query,expected_domain", [
        ("What's my schedule tomorrow?", "scheduling"),
        ("I need to track my sleep and nutrition", "health"),
        ("How's my portfolio doing?", "investments"),
    ])
    def test_routing_detects_domain(self, query, expected_domain):
        """Routing tool detects the correct domain for a query."""
        domain = _detect_domain(query)
        assert domain == expected_domain or expected_domain in domain

    def test_routing_with_zeus_answer(self):
        """Routing passes zeus_answer to specialist and gets response."""
        from unittest.mock import patch

        captured_prompt = None

        def capture_prompt(profile, prompt, timeout=10):
            nonlocal captured_prompt
            captured_prompt = prompt
            return "Confirmed, accurate."

        with patch("routing._call_profile", side_effect=capture_prompt):
            result = handle_routing({
                "query": "What's my schedule?",
                "zeus_answer": "You have a meeting at 10am.",
            })

        assert result["domain"] == "scheduling"
        assert result["matched_profile"] == "chronos"
        assert "Zeus's answer: You have a meeting at 10am." in captured_prompt


class TestChipInReview:
    """Test chip-in review-and-refine pattern."""

    def test_chip_in_prompt_includes_zeus_answer(self):
        """Chip-in prompt template includes zeus_answer placeholder."""
        prompt = CHIP_IN_PROMPT.format(query="Test", zeus_answer="Zeus says X")
        assert "Zeus's answer: Zeus says X" in prompt

    def test_chip_in_scoring_rules(self):
        """Chip-in prompt documents scoring rules."""
        assert "0.3" in CHIP_IN_PROMPT  # nothing to add
        assert "0.5-1.0" in CHIP_IN_PROMPT  # needs correction
        assert "0.0" in CHIP_IN_PROMPT  # not relevant
