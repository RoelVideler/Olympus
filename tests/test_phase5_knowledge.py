"""Tests for Phase 5: Knowledge Gathering — interview and document ingestion."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

# Add plugins to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "plugins" / "zeus" / "skills"))

from interview import handle_interview, INTERVIEW_TOPICS, INTERVIEW_STATE_DIR
from document_ingest import handle_document_ingest, INGEST_STATE_DIR


@pytest.fixture(autouse=True)
def clean_state(tmp_path, monkeypatch):
    """Use temp directories for state files."""
    interview_dir = tmp_path / "interviews"
    ingest_dir = tmp_path / "ingestion"
    monkeypatch.setattr("interview.INTERVIEW_STATE_DIR", interview_dir)
    monkeypatch.setattr("document_ingest.INGEST_STATE_DIR", ingest_dir)
    yield


class TestInterviewTopics:
    """Test that all expected interview topics are defined."""

    def test_has_personal_topic(self):
        assert "personal" in INTERVIEW_TOPICS
        assert INTERVIEW_TOPICS["personal"]["name"] == "Personal Background"

    def test_has_health_topic(self):
        assert "health" in INTERVIEW_TOPICS
        assert len(INTERVIEW_TOPICS["health"]["questions"]) >= 5

    def test_has_relationships_topic(self):
        assert "relationships" in INTERVIEW_TOPICS

    def test_has_business_topic(self):
        assert "business" in INTERVIEW_TOPICS

    def test_has_finance_topic(self):
        assert "finance" in INTERVIEW_TOPICS

    def test_has_home_topic(self):
        assert "home" in INTERVIEW_TOPICS

    def test_has_creative_topic(self):
        assert "creative" in INTERVIEW_TOPICS

    def test_all_topics_have_questions(self):
        for key, topic in INTERVIEW_TOPICS.items():
            assert len(topic["questions"]) > 0, f"Topic {key} has no questions"


class TestInterviewStatus:
    """Test interview status and topic listing."""

    def test_initial_status_shows_no_active(self):
        result = handle_interview({"action": "status"})
        assert result["status"] == "ok"
        assert result["current_topic"] is None
        assert result["remaining_count"] == len(INTERVIEW_TOPICS)

    def test_initial_status_suggests_first_topic(self):
        result = handle_interview({"action": "status"})
        assert result["next_suggested"] is not None

    def test_topics_lists_all_available(self):
        result = handle_interview({"action": "topics"})
        assert len(result["available_topics"]) == len(INTERVIEW_TOPICS)
        assert result["completed_topics"] == []


class TestInterviewStart:
    """Test starting interviews."""

    def test_start_auto_picks_first_topic(self):
        result = handle_interview({"action": "start"})
        assert result["status"] == "started"
        assert result["topic"] in INTERVIEW_TOPICS

    def test_start_specific_topic(self):
        result = handle_interview({"action": "start", "topic": "health"})
        assert result["status"] == "started"
        assert result["topic"] == "health"
        assert result["topic_name"] == "Health & Fitness"

    def test_start_unknown_topic_errors(self):
        result = handle_interview({"action": "start", "topic": "nonexistent"})
        assert result["error"] is not None

    def test_start_includes_guidance(self):
        result = handle_interview({"action": "start", "topic": "personal"})
        assert "guidance" in result
        assert "share_knowledge" in result["guidance"]


class TestInterviewComplete:
    """Test completing interviews."""

    def test_complete_marks_topic_done(self):
        handle_interview({"action": "start", "topic": "health"})
        result = handle_interview({"action": "complete", "topic": "health", "facts_count": 5})
        assert result["status"] == "completed"
        assert "health" in result["topic"]

    def test_complete_tracks_facts(self):
        handle_interview({"action": "start", "topic": "health"})
        result = handle_interview({"action": "complete", "topic": "health", "facts_count": 5})
        assert result["total_facts"] == 5

    def test_complete_clears_current_topic(self):
        handle_interview({"action": "start", "topic": "health"})
        handle_interview({"action": "complete", "topic": "health", "facts_count": 3})
        status = handle_interview({"action": "status"})
        assert status["current_topic"] is None

    def test_complete_suggests_next_topic(self):
        handle_interview({"action": "start", "topic": "health"})
        result = handle_interview({"action": "complete", "topic": "health", "facts_count": 3})
        assert result["next_suggested"] is not None
        assert result["next_suggested"] != "health"


class TestDocumentIngestCSV:
    """Test CSV document ingestion."""

    def test_ingest_csv_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write("name,value\nhealth_score,85\nsleep_hours,7.5\n")
            f.flush()
            result = handle_document_ingest({
                "action": "ingest",
                "file_path": f.name,
                "domain": "health",
                "scope": "personal",
            })
        assert result["status"] == "ok"
        assert result["document_type"] == "csv"
        assert result["facts_extracted"] == 2

    def test_ingest_csv_guidance_mentions_share_knowledge(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write("key,val\na,1\n")
            f.flush()
            result = handle_document_ingest({
                "action": "ingest",
                "file_path": f.name,
            })
        assert "share_knowledge" in result["guidance"]


class TestDocumentIngestJSON:
    """Test JSON document ingestion."""

    def test_ingest_json_object(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"name": "John", "age": 30}, f)
            f.flush()
            result = handle_document_ingest({
                "action": "ingest",
                "file_path": f.name,
                "domain": "personal",
            })
        assert result["status"] == "ok"
        assert result["document_type"] == "json"
        assert result["facts_extracted"] == 1

    def test_ingest_json_array(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump([{"a": 1}, {"b": 2}, {"c": 3}], f)
            f.flush()
            result = handle_document_ingest({
                "action": "ingest",
                "file_path": f.name,
            })
        assert result["facts_extracted"] == 3


class TestDocumentIngestText:
    """Test text document ingestion."""

    def test_ingest_text_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("First paragraph.\n\nSecond paragraph.\n\nThird paragraph.\n")
            f.flush()
            result = handle_document_ingest({
                "action": "ingest",
                "file_path": f.name,
                "domain": "personal",
            })
        assert result["status"] == "ok"
        assert result["document_type"] == "text"
        assert result["facts_extracted"] == 3


class TestDocumentIngestMarkdown:
    """Test markdown document ingestion."""

    def test_ingest_markdown_sections(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("# Health Info\n\nI have no chronic conditions.\n\n# Appointments\n\nNext doctor visit: March 15.\n")
            f.flush()
            result = handle_document_ingest({
                "action": "ingest",
                "file_path": f.name,
                "domain": "health",
            })
        assert result["status"] == "ok"
        assert result["document_type"] == "markdown"
        assert result["facts_extracted"] == 2


class TestDocumentIngestStatus:
    """Test document ingestion status."""

    def test_initial_status(self):
        result = handle_document_ingest({"action": "status"})
        assert result["status"] == "ok"
        assert result["documents_ingested"] == 0

    def test_status_after_ingest(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("Some text.\n")
            f.flush()
            handle_document_ingest({
                "action": "ingest",
                "file_path": f.name,
            })
        result = handle_document_ingest({"action": "status"})
        assert result["documents_ingested"] == 1
        assert result["total_facts_extracted"] == 1


class TestDocumentIngestErrors:
    """Test document ingestion error handling."""

    def test_ingest_missing_file_path(self):
        result = handle_document_ingest({"action": "ingest"})
        assert result["error"] is not None

    def test_ingest_nonexistent_file(self):
        result = handle_document_ingest({
            "action": "ingest",
            "file_path": "/nonexistent/file.csv",
        })
        assert result["error"] is not None

    def test_unknown_action(self):
        result = handle_document_ingest({"action": "unknown"})
        assert result["error"] is not None
