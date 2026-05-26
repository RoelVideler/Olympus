"""Tests for Hermes gmail_triage tool."""

from __future__ import annotations

import json
import sqlite3
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from plugins.hermes.skills.gmail_triage import (
    GMAIL_TRIAGE_SCHEMA,
    _ensure_schema,
    _get_db,
    _triage_score,
    handle_gmail_triage,
)


class TestGmailTriageSchema(unittest.TestCase):
    """Test schema validation."""

    def test_schema_has_required_fields(self):
        params = GMAIL_TRIAGE_SCHEMA["function"]["parameters"]
        assert "action" in params["required"]
        assert "properties" in params

    def test_action_enum_values(self):
        props = GMAIL_TRIAGE_SCHEMA["function"]["parameters"]["properties"]
        actions = props["action"]["enum"]
        assert "list_emails" in actions
        assert "read_email" in actions
        assert "draft_reply" in actions
        assert "draft_new" in actions
        assert "query_drafts" in actions
        assert "share_fact" in actions

    def test_no_send_email_action(self):
        """Hermes must never send emails autonomously."""
        props = GMAIL_TRIAGE_SCHEMA["function"]["parameters"]["properties"]
        actions = props["action"]["enum"]
        assert "send_email" not in actions


class TestTriageScore(unittest.TestCase):
    """Test email triage scoring logic."""

    def test_urgent_keywords(self):
        score, category = _triage_score("This is urgent, please respond ASAP", "boss@company.com", "URGENT: Project deadline")
        assert score >= 0.9
        assert category == "urgent"

    def test_financial_sender(self):
        score, category = _triage_score("Your statement is ready", "billing@bank.com", "Monthly Statement")
        assert score >= 0.7
        assert category == "financial"

    def test_automated_sender(self):
        score, category = _triage_score("Your order has shipped", "noreply@amazon.com", "Order Shipped")
        assert score <= 0.3
        assert category == "automated"

    def test_normal_email(self):
        score, category = _triage_score("Hey, want to grab lunch?", "friend@gmail.com", "Lunch?")
        assert 0.3 < score < 0.8
        assert category == "normal"


class TestEnsureSchema(unittest.TestCase):
    """Test database schema creation."""

    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row

    def tearDown(self):
        self.conn.close()

    def test_ensure_schema_creates_tables(self):
        _ensure_schema(self.conn)
        cursor = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='gmail_triage_cache'"
        )
        assert cursor.fetchone() is not None

        cursor = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='gmail_sent_log'"
        )
        assert cursor.fetchone() is not None

        cursor = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='gmail_sync_state'"
        )
        assert cursor.fetchone() is not None


class TestHandleGmailTriage(unittest.TestCase):
    """Test the main handler function."""

    def test_unknown_action(self):
        result = json.loads(handle_gmail_triage({"action": "send_email"}))
        assert "error" in result
        assert "send_email" in result["error"]

    def test_missing_action(self):
        result = json.loads(handle_gmail_triage({}))
        assert "error" in result

    def test_list_emails_requires_token(self):
        """Should fail gracefully when token is missing."""
        with patch("plugins.hermes.skills.gmail_triage.TOKEN_PATH") as mock_path:
            mock_path.exists.return_value = False
            result = json.loads(handle_gmail_triage({"action": "list_emails"}))
            assert "error" in result

    def test_read_email_requires_message_id(self):
        """Should fail when message_id is missing."""
        with patch("plugins.hermes.skills.gmail_triage.TOKEN_PATH") as mock_path:
            mock_path.exists.return_value = False
            result = json.loads(handle_gmail_triage({"action": "read_email"}))
            assert "error" in result

    def test_draft_reply_requires_message_id(self):
        """Should fail when message_id is missing."""
        with patch("plugins.hermes.skills.gmail_triage.TOKEN_PATH") as mock_path:
            mock_path.exists.return_value = False
            result = json.loads(handle_gmail_triage({"action": "draft_reply", "body": "test"}))
            assert "error" in result

    def test_draft_new_requires_fields(self):
        """Should fail when required fields are missing."""
        with patch("plugins.hermes.skills.gmail_triage.TOKEN_PATH") as mock_path:
            mock_path.exists.return_value = False
            result = json.loads(handle_gmail_triage({"action": "draft_new"}))
            assert "error" in result

    def test_share_fact_requires_fact(self):
        """Should fail when fact is missing."""
        result = json.loads(handle_gmail_triage({"action": "share_fact"}))
        assert "error" in result


class TestGmailTriageIntegration(unittest.TestCase):
    """Integration tests with mocked Gmail API."""

    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        _ensure_schema(self.conn)

    def tearDown(self):
        self.conn.close()

    @patch("plugins.hermes.skills.gmail_triage._get_access_token")
    def test_list_emails_returns_triage_results(self, mock_token):
        mock_token.return_value = "fake_token"

        call_count = [0]
        def mock_request_side_effect(path, method="GET", body=None):
            call_count[0] += 1
            if call_count[0] == 1:
                return {
                    "messages": [
                        {"id": "msg1"},
                        {"id": "msg2"},
                    ],
                    "resultSizeEstimate": 2,
                }
            elif call_count[0] == 2:
                return {
                    "id": "msg1",
                    "threadId": "thread1",
                    "snippet": "URGENT: Please respond immediately",
                    "payload": {
                        "headers": [
                            {"name": "From", "value": "boss@company.com"},
                            {"name": "Subject", "value": "URGENT: Project deadline"},
                            {"name": "Date", "value": "Mon, 26 May 2026 10:00:00 +0200"},
                        ]
                    },
                    "labelIds": ["INBOX", "UNREAD"],
                }
            else:
                return {
                    "id": "msg2",
                    "threadId": "thread2",
                    "snippet": "Your order has shipped",
                    "payload": {
                        "headers": [
                            {"name": "From", "value": "noreply@amazon.com"},
                            {"name": "Subject", "value": "Order Shipped"},
                            {"name": "Date", "value": "Mon, 26 May 2026 09:00:00 +0200"},
                        ]
                    },
                    "labelIds": ["INBOX"],
                }

        with patch("plugins.hermes.skills.gmail_triage._gmail_request", side_effect=mock_request_side_effect):
            result = json.loads(handle_gmail_triage({"action": "list_emails", "query": "is:unread"}))

            assert result["status"] == "ok"
            assert result["count"] == 2
            assert result["urgent_count"] >= 1
            # First email should be urgent (higher score)
            assert result["emails"][0]["triage_category"] == "urgent"

    @patch("plugins.hermes.skills.gmail_triage._create_draft")
    @patch("plugins.hermes.skills.gmail_triage._get_message_detail")
    @patch("plugins.hermes.skills.gmail_triage._get_access_token")
    def test_draft_reply_creates_draft(self, mock_token, mock_detail, mock_create):
        mock_token.return_value = "fake_token"
        mock_detail.return_value = {
            "id": "msg1",
            "threadId": "thread1",
            "payload": {
                "headers": [
                    {"name": "From", "value": "Alice <alice@example.com>"},
                    {"name": "Subject", "value": "Meeting tomorrow"},
                    {"name": "Date", "value": "Mon, 26 May 2026 10:00:00 +0200"},
                ]
            },
        }
        mock_create.return_value = {"id": "draft123"}

        result = json.loads(handle_gmail_triage({
            "action": "draft_reply",
            "message_id": "msg1",
            "body": "Sounds good, see you there!",
        }))

        assert result["status"] == "drafted"
        assert result["draft_id"] == "draft123"
        assert "Re:" in result["subject"]
        assert "Review and send manually" in result["note"]

    @patch("plugins.hermes.skills.gmail_triage._create_draft")
    @patch("plugins.hermes.skills.gmail_triage._get_access_token")
    def test_draft_new_creates_draft(self, mock_token, mock_create):
        mock_token.return_value = "fake_token"
        mock_create.return_value = {"id": "draft456"}

        result = json.loads(handle_gmail_triage({
            "action": "draft_new",
            "to": "colleague@example.com",
            "subject": "Project update",
            "body": "Here's the latest status...",
        }))

        assert result["status"] == "drafted"
        assert result["draft_id"] == "draft456"
        assert result["to"] == "colleague@example.com"
        assert "Review and send manually" in result["note"]


if __name__ == "__main__":
    unittest.main()
