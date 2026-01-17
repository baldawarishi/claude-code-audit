"""Tests for SQLite database operations."""

import tempfile
from pathlib import Path

import pytest

from claude_code_archive.database import Database
from claude_code_archive.models import Message, Session, ToolCall, ToolResult


@pytest.fixture
def db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    database = Database(db_path)
    database.connect()
    yield database
    database.close()
    db_path.unlink()


@pytest.fixture
def sample_session():
    """Create a sample session for testing."""
    return Session(
        id="test-session-123",
        project="test-project",
        cwd="/test/path",
        git_branch="main",
        slug="dapper-questing-pascal",
        summary="A test session summary",
        started_at="2026-01-01T10:00:00Z",
        ended_at="2026-01-01T11:00:00Z",
        claude_version="2.1.9",
        total_input_tokens=100,
        total_output_tokens=50,
        total_cache_read_tokens=200,
        model="claude-opus-4-5-20251101",
        messages=[
            Message(
                id="msg-1",
                session_id="test-session-123",
                type="user",
                timestamp="2026-01-01T10:00:00Z",
                content="Hello",
            ),
            Message(
                id="msg-2",
                session_id="test-session-123",
                type="assistant",
                timestamp="2026-01-01T10:00:01Z",
                content="Hi there",
                model="claude-opus-4-5-20251101",
                input_tokens=100,
                output_tokens=50,
                thinking="Let me think about this...",
                stop_reason="end_turn",
                is_sidechain=False,
            ),
        ],
        tool_calls=[
            ToolCall(
                id="tool-1",
                message_id="msg-2",
                session_id="test-session-123",
                tool_name="Bash",
                input_json='{"command": "ls"}',
                timestamp="2026-01-01T10:00:01Z",
            ),
        ],
        tool_results=[
            ToolResult(
                id="result-1",
                tool_call_id="tool-1",
                session_id="test-session-123",
                content="file1.txt\nfile2.txt",
                is_error=False,
                timestamp="2026-01-01T10:00:02Z",
            ),
        ],
    )


class TestDatabase:
    def test_session_not_exists(self, db):
        assert db.session_exists("nonexistent") is False

    def test_insert_and_check_exists(self, db, sample_session):
        db.insert_session(sample_session)
        assert db.session_exists("test-session-123") is True

    def test_get_session_ids(self, db, sample_session):
        db.insert_session(sample_session)
        ids = db.get_session_ids()
        assert "test-session-123" in ids

    def test_get_all_sessions(self, db, sample_session):
        db.insert_session(sample_session)
        sessions = db.get_all_sessions()
        assert len(sessions) == 1
        assert sessions[0]["id"] == "test-session-123"
        assert sessions[0]["project"] == "test-project"

    def test_get_sessions_by_project(self, db, sample_session):
        db.insert_session(sample_session)
        sessions = db.get_sessions_by_project("test-project")
        assert len(sessions) == 1

        sessions = db.get_sessions_by_project("other-project")
        assert len(sessions) == 0

    def test_get_messages_for_session(self, db, sample_session):
        db.insert_session(sample_session)
        messages = db.get_messages_for_session("test-session-123")
        assert len(messages) == 2
        assert messages[0]["content"] == "Hello"
        assert messages[1]["content"] == "Hi there"

    def test_stores_new_session_fields(self, db, sample_session):
        db.insert_session(sample_session)
        sessions = db.get_all_sessions()
        assert sessions[0]["slug"] == "dapper-questing-pascal"
        assert sessions[0]["summary"] == "A test session summary"

    def test_stores_new_message_fields(self, db, sample_session):
        db.insert_session(sample_session)
        messages = db.get_messages_for_session("test-session-123")
        # Second message is the assistant message with new fields
        assert messages[1]["thinking"] == "Let me think about this..."
        assert messages[1]["stop_reason"] == "end_turn"
        assert messages[1]["is_sidechain"] == 0  # SQLite stores bool as 0/1

    def test_get_tool_calls_for_session(self, db, sample_session):
        db.insert_session(sample_session)
        tool_calls = db.get_tool_calls_for_session("test-session-123")
        assert len(tool_calls) == 1
        assert tool_calls[0]["tool_name"] == "Bash"

    def test_get_tool_results_for_session(self, db, sample_session):
        db.insert_session(sample_session)
        results = db.get_tool_results_for_session("test-session-123")
        assert len(results) == 1
        assert "file1.txt" in results[0]["content"]

    def test_get_stats(self, db, sample_session):
        db.insert_session(sample_session)
        stats = db.get_stats()
        assert stats["total_sessions"] == 1
        assert stats["total_messages"] == 2
        assert stats["total_tool_calls"] == 1
        assert stats["total_input_tokens"] == 100
        assert stats["total_output_tokens"] == 50
        assert "test-project" in stats["projects"]

    def test_insert_replaces_existing(self, db, sample_session):
        db.insert_session(sample_session)

        # Modify and re-insert
        sample_session.total_input_tokens = 999
        db.insert_session(sample_session)

        sessions = db.get_all_sessions()
        assert len(sessions) == 1
        assert sessions[0]["total_input_tokens"] == 999

    def test_context_manager(self, sample_session):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)

        with Database(db_path) as db:
            db.insert_session(sample_session)
            assert db.session_exists("test-session-123")

        db_path.unlink()
