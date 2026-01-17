# claude-code-archive Specification

## Purpose

Archive Claude Code transcripts from `~/.claude/projects/` into a structured SQLite database with optional TOML export for human-readable transcripts.

## Data Flow

```
~/.claude/projects/           claude-code-archive sync        archive/sessions.db
├── {project-dir}/       ──────────────────────────────►    (SQLite)
│   ├── {uuid}.jsonl                                              │
│   └── agent-{hash}.jsonl                                        │
                                                                  │
                              claude-code-archive render          ▼
                         ◄────────────────────────────────  archive/transcripts/
                                                            └── {project}/
                                                                └── {date}-{id}.toml
```

## Source Format (Claude Code JSONL)

Each line in `~/.claude/projects/{project-dir}/{session}.jsonl`:

```json
{
  "type": "user|assistant|file-history-snapshot|queue-operation",
  "sessionId": "uuid",
  "uuid": "message-uuid",
  "parentUuid": "parent-uuid|null",
  "timestamp": "ISO8601",
  "cwd": "/working/directory",
  "version": "2.1.9",
  "gitBranch": "branch-name",
  "message": {
    "role": "user|assistant",
    "content": "string | array of content blocks",
    "model": "claude-opus-4-5-20251101",
    "usage": {
      "input_tokens": 123,
      "output_tokens": 456,
      "cache_read_input_tokens": 789
    }
  }
}
```

### Content Block Types

```json
// Text
{"type": "text", "text": "..."}

// Tool use (assistant)
{"type": "tool_use", "id": "toolu_xxx", "name": "Bash", "input": {...}}

// Tool result (user message containing result)
{"type": "tool_result", "tool_use_id": "toolu_xxx", "content": "..."}

// Thinking (filtered out)
{"type": "thinking", "thinking": "..."}
```

## SQLite Schema

```sql
CREATE TABLE sessions (
    id TEXT PRIMARY KEY,
    project TEXT NOT NULL,
    cwd TEXT,
    git_branch TEXT,
    started_at TEXT,
    ended_at TEXT,
    claude_version TEXT,
    total_input_tokens INTEGER DEFAULT 0,
    total_output_tokens INTEGER DEFAULT 0,
    total_cache_read_tokens INTEGER DEFAULT 0,
    model TEXT
);

CREATE TABLE messages (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(id),
    parent_uuid TEXT,
    type TEXT NOT NULL,  -- user, assistant, tool_result
    timestamp TEXT,
    content TEXT,
    model TEXT,
    input_tokens INTEGER,
    output_tokens INTEGER
);

CREATE TABLE tool_calls (
    id TEXT PRIMARY KEY,
    message_id TEXT NOT NULL REFERENCES messages(id),
    session_id TEXT NOT NULL REFERENCES sessions(id),
    tool_name TEXT NOT NULL,
    input_json TEXT,
    timestamp TEXT
);

CREATE TABLE tool_results (
    id TEXT PRIMARY KEY,
    tool_call_id TEXT REFERENCES tool_calls(id),
    session_id TEXT NOT NULL REFERENCES sessions(id),
    content TEXT,
    is_error BOOLEAN DEFAULT FALSE,
    timestamp TEXT
);

-- Indexes
CREATE INDEX idx_messages_session ON messages(session_id);
CREATE INDEX idx_messages_timestamp ON messages(timestamp);
CREATE INDEX idx_tool_calls_session ON tool_calls(session_id);
CREATE INDEX idx_tool_results_session ON tool_results(session_id);
CREATE INDEX idx_sessions_project ON sessions(project);
CREATE INDEX idx_sessions_started ON sessions(started_at);
```

## TOML Output Format

```toml
[session]
id = "uuid"
project = "project-name"
cwd = "/working/directory"
git_branch = "branch"
started_at = "ISO8601"
ended_at = "ISO8601"
model = "claude-opus-4-5-20251101"
claude_version = "2.1.9"
input_tokens = 123
output_tokens = 456
cache_read_tokens = 789

[[turns]]
number = 1
timestamp = "ISO8601"

[turns.user]
content = '''
User message content (literal string, no escaping needed)
'''

[turns.assistant]
content = '''
Assistant response text
'''

[[turns.assistant.tool_calls]]
tool = "Bash"
id = "toolu_xxx"
timestamp = "ISO8601"

[turns.assistant.tool_calls.input]
command = "ls -la"
description = "List files"

[turns.assistant.tool_calls.result]
content = '''
Tool output here
'''
```

## CLI Commands

### `sync`
Archive sessions from Claude projects to SQLite.

```
claude-code-archive sync [OPTIONS]

Options:
  --projects-dir PATH   Source directory (default: ~/.claude/projects)
  --archive-dir PATH    Archive directory (default: ~/Development/claude-code-archive/archive)
  --project TEXT        Filter to specific project
  --force               Re-archive existing sessions
```

Behavior:
- Incremental by default (skips sessions already in database)
- Extracts project name from directory path
- Aggregates token usage per session
- Maps tool results to tool calls via `tool_use_id`

### `render`
Generate TOML transcripts from archived sessions.

```
claude-code-archive render [OPTIONS]

Options:
  --archive-dir PATH    Archive directory
  --output-dir PATH     Output directory (default: archive/transcripts)
  --session TEXT        Render specific session (prefix match)
  --project TEXT        Render all sessions for project
  --stdout              Output to stdout instead of files
```

### `stats`
Display archive statistics.

```
claude-code-archive stats [OPTIONS]

Options:
  --archive-dir PATH    Archive directory
```

### `config`
Manage configuration.

```
claude-code-archive config [OPTIONS]

Options:
  --archive-dir PATH    Set archive directory
  --projects-dir PATH   Set projects directory
  --show                Display current configuration
```

## Configuration

Location: `~/.config/claude-code-archive/config.json`

```json
{
  "archive_dir": "/path/to/archive",
  "projects_dir": "/path/to/.claude/projects"
}
```

CLI flags override config file values.

## Module Structure

```
src/claude_code_archive/
├── __init__.py      # Version
├── cli.py           # Click CLI entrypoint
├── config.py        # Configuration management
├── database.py      # SQLite operations
├── models.py        # Dataclasses (Session, Message, ToolCall, ToolResult)
├── parser.py        # JSONL parsing
└── toml_renderer.py # TOML output generation
```

## Testing Requirements

1. **Parser tests**: Verify JSONL parsing handles all message types
2. **Database tests**: CRUD operations, schema creation, incremental sync
3. **Renderer tests**: TOML output matches expected format
4. **CLI tests**: Commands execute without error
5. **Integration test**: Full sync → render cycle with sample data

## Error Handling

- Invalid JSON lines: Skip with warning, continue processing
- Missing files: Report error, continue with other files
- Database errors: Fail fast with descriptive message
- Empty sessions: Skip (no messages to archive)

## Performance Considerations

- Single-threaded processing (Claude Code sessions are typically small)
- Batch inserts within transaction per session
- No content truncation in database (full fidelity)
- TOML rendering truncates large tool results for readability

## Future Considerations (Out of Scope)

- Token cost calculations
- Web UI
- Multi-user support
- Cloud sync
- Markdown/JSON export (can be added later)
