"""Integration tests for Phase 3a: Zeus delegation and chip-in review-refine."""

import subprocess
import pytest


class TestZeusDelegation:
    """Test Zeus delegation to specialists."""

    @pytest.mark.parametrize("query,expected_domain", [
        ("What's my schedule tomorrow?", "scheduling"),
        ("How's my sleep quality?", "health"),
        ("How's my portfolio doing?", "investments"),
    ])
    def test_routing_detects_domain(self, query, expected_domain):
        """Routing tool detects the correct domain for a query."""
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent.parent / "plugins" / "zeus" / "skills"))
        from routing import _detect_domain

        domain = _detect_domain(query)
        assert domain == expected_domain or expected_domain in domain

    def test_routing_with_zeus_answer(self):
        """Routing passes zeus_answer to specialist and gets response."""
        import sys
        from pathlib import Path
        from unittest.mock import patch
        sys.path.insert(0, str(Path(__file__).parent.parent / "plugins" / "zeus" / "skills"))
        from routing import handle_routing

        with patch("routing._call_profile", return_value="Confirmed, accurate."):
            result = handle_routing({
                "query": "What's my schedule?",
                "zeus_answer": "You have a meeting at 10am.",
            })

        assert result["domain"] == "scheduling"
        assert result["matched_profile"] == "chronos"


class TestChipInReview:
    """Test chip-in review-and-refine pattern."""

    def test_chip_in_prompt_includes_zeus_answer(self):
        """Chip-in prompt template includes zeus_answer placeholder."""
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent.parent / "plugins" / "zeus" / "skills"))
        from chip_in import CHIP_IN_PROMPT

        prompt = CHIP_IN_PROMPT.format(query="Test", zeus_answer="Zeus says X")
        assert "Zeus's answer: Zeus says X" in prompt

    def test_chip_in_scoring_rules(self):
        """Chip-in prompt documents scoring rules."""
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent.parent / "plugins" / "zeus" / "skills"))
        from chip_in import CHIP_IN_PROMPT

        assert "0.3" in CHIP_IN_PROMPT
        assert "0.5-1.0" in CHIP_IN_PROMPT
        assert "0.0" in CHIP_IN_PROMPT
