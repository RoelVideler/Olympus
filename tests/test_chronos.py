"""Tests for Chronos calendar_query tool."""

from __future__ import annotations

import json
import sqlite3
import unittest
from unittest.mock import patch

from plugins.chronos.skills.calendar_query import (
    CALENDAR_QUERY_SCHEMA,
    _ensure_schema,
    _format_event,
    handle_calendar_query,
)


class TestCalendarQuerySchema(unittest.TestCase):
    """Test schema validation."""

    def test_schema_has_required_fields(self):
        params = CALENDAR_QUERY_SCHEMA["function"]["parameters"]
        assert "action" in params["required"]
        assert "properties" in params

    def test_action_enum_values(self):
        props = CALENDAR_QUERY_SCHEMA["function"]["parameters"]["properties"]
        actions = props["action"]["enum"]
        assert "list_calendars" in actions
        assert "list_events" in actions
        assert "get_event" in actions
        assert "free_busy" in actions
        assert "search_events" in actions
        assert "share_fact" in actions


class TestFormatEvent(unittest.TestCase):
    """Test event formatting."""

    def test_format_datetime_event(self):
        event = {
            "id": "evt1",
            "summary": "Meeting",
            "description": "Discuss project",
            "location": "Office",
            "start": {"dateTime": "2026-05-26T10:00:00+02:00"},
            "end": {"dateTime": "2026-05-26T11:00:00+02:00"},
            "status": "confirmed",
            "attendees": [{"email": "test@example.com", "displayName": "Test", "responseStatus": "accepted"}],
            "htmlLink": "https://calendar.google.com/event?eid=1",
        }
        result = _format_event(event)
        assert result["event_id"] == "evt1"
        assert result["summary"] == "Meeting"
        assert result["is_all_day"] is False
        assert len(result["attendees"]) == 1

    def test_format_all_day_event(self):
        event = {
            "id": "evt2",
            "summary": "Holiday",
            "start": {"date": "2026-05-26"},
            "end": {"date": "2026-05-27"},
            "status": "confirmed",
        }
        result = _format_event(event)
        assert result["is_all_day"] is True
        assert result["start"] == "2026-05-26"

    def test_format_no_title(self):
        event = {
            "id": "evt3",
            "start": {"dateTime": "2026-05-26T10:00:00+02:00"},
            "end": {"dateTime": "2026-05-26T11:00:00+02:00"},
        }
        result = _format_event(event)
        assert result["summary"] == "(no title)"


class TestHandleCalendarQuery(unittest.TestCase):
    """Test the main handler function."""

    def test_unknown_action(self):
        result = json.loads(handle_calendar_query({"action": "create_event"}))
        assert "error" in result

    def test_missing_action(self):
        result = json.loads(handle_calendar_query({}))
        assert "error" in result

    def test_get_event_requires_event_id(self):
        result = json.loads(handle_calendar_query({"action": "get_event"}))
        assert "error" in result

    def test_search_events_requires_query(self):
        result = json.loads(handle_calendar_query({"action": "search_events"}))
        assert "error" in result

    def test_share_fact_requires_fact(self):
        result = json.loads(handle_calendar_query({"action": "share_fact"}))
        assert "error" in result


class TestCalendarQueryIntegration(unittest.TestCase):
    """Integration tests with mocked Calendar API."""

    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        _ensure_schema(self.conn)

    def tearDown(self):
        self.conn.close()

    @patch("plugins.chronos.skills.calendar_query._calendar_request")
    def test_list_calendars_returns_results(self, mock_request):
        mock_request.return_value = {
            "items": [
                {"id": "primary", "summary": "My Calendar", "primary": True, "accessRole": "owner"},
                {"id": "family@group.calendar.google.com", "summary": "Family", "primary": False, "accessRole": "writer"},
            ]
        }

        result = json.loads(handle_calendar_query({"action": "list_calendars"}))

        assert result["status"] == "ok"
        assert result["count"] == 2
        assert result["calendars"][0]["primary"] is True

    @patch("plugins.chronos.skills.calendar_query._calendar_request")
    def test_list_events_returns_formatted_events(self, mock_request):
        mock_request.return_value = {
            "items": [
                {
                    "id": "evt1",
                    "summary": "Team meeting",
                    "start": {"dateTime": "2026-05-26T10:00:00+02:00"},
                    "end": {"dateTime": "2026-05-26T11:00:00+02:00"},
                    "status": "confirmed",
                },
                {
                    "id": "evt2",
                    "summary": "Cancelled event",
                    "start": {"dateTime": "2026-05-26T12:00:00+02:00"},
                    "end": {"dateTime": "2026-05-26T13:00:00+02:00"},
                    "status": "cancelled",
                },
            ]
        }

        result = json.loads(handle_calendar_query({
            "action": "list_events",
            "max_results": 10,
        }))

        assert result["status"] == "ok"
        # Cancelled event should be filtered
        assert result["count"] == 1
        assert result["events"][0]["summary"] == "Team meeting"

    @patch("plugins.chronos.skills.calendar_query._calendar_request")
    def test_search_events_returns_results(self, mock_request):
        mock_request.return_value = {
            "items": [
                {
                    "id": "evt1",
                    "summary": "Dentist appointment",
                    "start": {"dateTime": "2026-05-26T14:00:00+02:00"},
                    "end": {"dateTime": "2026-05-26T15:00:00+02:00"},
                    "status": "confirmed",
                },
            ]
        }

        result = json.loads(handle_calendar_query({
            "action": "search_events",
            "query": "dentist",
        }))

        assert result["status"] == "ok"
        assert result["query"] == "dentist"
        assert result["count"] == 1

    @patch("plugins.chronos.skills.calendar_query._calendar_request")
    def test_free_busy_returns_results(self, mock_request):
        mock_request.return_value = {
            "calendars": [
                {
                    "id": "primary",
                    "busy": [
                        {"start": "2026-05-26T10:00:00Z", "end": "2026-05-26T11:00:00Z"},
                    ],
                }
            ]
        }

        result = json.loads(handle_calendar_query({
            "action": "free_busy",
        }))

        assert result["status"] == "ok"
        assert result["calendars"][0]["id"] == "primary"
        assert len(result["calendars"][0]["busy_slots"]) == 1


if __name__ == "__main__":
    unittest.main()
