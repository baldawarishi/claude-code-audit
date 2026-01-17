"""Tests for JSONL parser."""

import json
import tempfile
from pathlib import Path

import pytest

from claude_code_archive.parser import (
    extract_text_content,
    extract_tool_calls,
    extract_tool_results,
    parse_jsonl_file,
    parse_session,
    get_project_name_from_dir,
)


class TestExtractTextContent:
    def test_string_content(self):
        assert extract_text_content("hello world") == "hello world"

    def test_text_block(self):
        content = [{"type": "text", "text": "hello"}]
        assert extract_text_content(content) == "hello"

    def test_multiple_text_blocks(self):
        content = [
            {"type": "text", "text": "hello"},
            {"type": "text", "text": "world"},
        ]
        assert extract_text_content(content) == "hello\nworld"

    def test_filters_thinking_blocks(self):
        content = [
            {"type": "thinking", "thinking": "hmm"},
            {"type": "text", "text": "hello"},
        ]
        assert extract_text_content(content) == "hello"

    def test_empty_content(self):
        assert extract_text_content([]) == ""
        assert extract_text_content("") == ""


class TestExtractToolCalls:
    def test_extracts_tool_use(self):
        content = [
            {
                "type": "tool_use",
                "id": "toolu_123",
                "name": "Bash",
                "input": {"command": "ls"},
            }
        ]
        calls = extract_tool_calls(content, "msg_1", "session_1", "2026-01-01T00:00:00Z")
        assert len(calls) == 1
        assert calls[0].tool_name == "Bash"
        assert calls[0].id == "toolu_123"
        assert json.loads(calls[0].input_json) == {"command": "ls"}

    def test_no_tool_calls(self):
        content = [{"type": "text", "text": "hello"}]
        calls = extract_tool_calls(content, "msg_1", "session_1", "2026-01-01T00:00:00Z")
        assert len(calls) == 0


class TestExtractToolResults:
    def test_extracts_tool_result(self):
        content = [
            {
                "type": "tool_result",
                "tool_use_id": "toolu_123",
                "content": "output here",
            }
        ]
        results = extract_tool_results(content, "session_1", "2026-01-01T00:00:00Z")
        assert len(results) == 1
        assert results[0].tool_call_id == "toolu_123"
        assert results[0].content == "output here"

    def test_error_result(self):
        content = [
            {
                "type": "tool_result",
                "tool_use_id": "toolu_123",
                "content": "error",
                "is_error": True,
            }
        ]
        results = extract_tool_results(content, "session_1", "2026-01-01T00:00:00Z")
        assert results[0].is_error is True


class TestParseJsonlFile:
    def test_parses_valid_jsonl(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write('{"type": "user", "message": {"content": "hello"}}\n')
            f.write('{"type": "assistant", "message": {"content": "hi"}}\n')
            f.flush()

            entries = list(parse_jsonl_file(Path(f.name)))
            assert len(entries) == 2
            assert entries[0]["type"] == "user"
            assert entries[1]["type"] == "assistant"

    def test_skips_invalid_json(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write('{"valid": true}\n')
            f.write('invalid json line\n')
            f.write('{"also": "valid"}\n')
            f.flush()

            entries = list(parse_jsonl_file(Path(f.name)))
            assert len(entries) == 2


class TestParseSession:
    def test_parses_session(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write(json.dumps({
                "type": "user",
                "sessionId": "test-session",
                "uuid": "msg-1",
                "timestamp": "2026-01-01T10:00:00Z",
                "cwd": "/test",
                "version": "2.1.9",
                "message": {"role": "user", "content": "hello"},
            }) + "\n")
            f.write(json.dumps({
                "type": "assistant",
                "sessionId": "test-session",
                "uuid": "msg-2",
                "parentUuid": "msg-1",
                "timestamp": "2026-01-01T10:00:01Z",
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "hi there"}],
                    "model": "claude-opus-4-5-20251101",
                    "usage": {"input_tokens": 10, "output_tokens": 5},
                },
            }) + "\n")
            f.flush()

            session = parse_session(Path(f.name), "test-project")
            assert session.project == "test-project"
            assert session.cwd == "/test"
            assert session.claude_version == "2.1.9"
            assert len(session.messages) == 2
            assert session.total_input_tokens == 10
            assert session.total_output_tokens == 5


class TestGetProjectNameFromDir:
    def test_extracts_last_component(self):
        assert get_project_name_from_dir("-Users-john-Development-myproject") == "myproject"

    def test_skips_common_paths(self):
        assert get_project_name_from_dir("-Users-john-Projects-cool-app") == "app"

    def test_handles_simple_name(self):
        assert get_project_name_from_dir("myproject") == "myproject"
