# Analyzer Improvements Investigation

Investigation into two improvements to the LLM classification phase.
Date: 2026-01-17

## Executive Summary

| Investigation | Feasibility | Recommendation | Complexity |
|---------------|-------------|----------------|------------|
| File-based pattern input | **Feasible** | Implement | Medium |
| Smarter pattern prioritization | **Feasible** | Implement | Low-Medium |

Both improvements are feasible and complementary. Recommend implementing in order:
1. Pattern prioritization (quick win, improves quality)
2. File-based input (enables scale, more complex)

---

## Investigation 1: File-based Pattern Input

### Problem Statement

Current implementation embeds all patterns directly in the prompt (`classifier.py:97`):
```python
patterns_json = json.dumps(all_patterns, indent=2)
return template.format(patterns_json=patterns_json, ...)
```

This hits token limits, forcing `max_patterns=50` (default). With typical archives containing 200-1000+ patterns, we're only analyzing ~5-25% of detected patterns.

### Research Findings

#### claude-agent-sdk Capabilities

The SDK **does support file-based input** via built-in tools. Key documentation findings:

1. **Built-in Read tool**: The SDK includes `Read`, `Write`, `Bash`, etc. tools by default
2. **Configuration**: Enable via `ClaudeAgentOptions`:
   ```python
   options = ClaudeAgentOptions(
       allowed_tools=["Read"],
       cwd="/path/to/working/directory",
       permission_mode='acceptEdits'  # auto-accept file reads
   )
   ```
3. **ClaudeSDKClient support**: Works with the client we already use

Source: [Agent SDK Python Reference](https://platform.claude.com/docs/en/agent-sdk/python)

#### Current Implementation Gap

The current `claude_client.py:49` creates a bare client without options:
```python
self.client = ClaudeSDKClient()  # No options passed
```

This means Claude cannot use tools like `Read` even though the SDK supports them.

### Proposed Solution

#### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     classify_patterns()                          │
├─────────────────────────────────────────────────────────────────┤
│  1. Write patterns to temp file                                  │
│     /tmp/claude-archive-patterns-{uuid}.json                     │
│                                                                  │
│  2. Configure ClaudeAgentOptions                                 │
│     allowed_tools=["Read"]                                       │
│     cwd=temp_dir                                                 │
│     permission_mode='acceptEdits'                                │
│                                                                  │
│  3. Prompt instructs Claude to read the file                     │
│     "Read the patterns from patterns.json and classify them"     │
│                                                                  │
│  4. Claude uses Read tool → file contents in context             │
│     (bypasses prompt token limit)                                │
│                                                                  │
│  5. Cleanup temp file after classification                       │
└─────────────────────────────────────────────────────────────────┘
```

#### Code Changes Required

**`claude_client.py`** - Add options support:
```python
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions

class AnalyzerClaudeClient:
    def __init__(self, options: ClaudeAgentOptions | None = None):
        self.options = options
        self.client: Optional[ClaudeSDKClient] = None

    async def _connect(self) -> None:
        # ... existing validation ...
        self.client = ClaudeSDKClient(options=self.options)
        await self.client.connect()
```

**`classifier.py`** - Use temp file for large pattern sets:
```python
import tempfile
from pathlib import Path

async def classify_patterns_with_file(
    patterns_result: dict,
    max_inline_patterns: int = 50,
) -> list[ClassifiedPattern]:
    all_patterns = flatten_patterns(patterns_result)

    if len(all_patterns) <= max_inline_patterns:
        # Use existing inline approach
        return await classify_patterns_inline(patterns_result)

    # Write to temp file for large pattern sets
    with tempfile.TemporaryDirectory() as temp_dir:
        patterns_file = Path(temp_dir) / "patterns.json"
        patterns_file.write_text(json.dumps(all_patterns, indent=2))

        options = ClaudeAgentOptions(
            allowed_tools=["Read"],
            cwd=temp_dir,
            permission_mode='acceptEdits'
        )

        async with AnalyzerClaudeClient(options=options) as client:
            prompt = build_file_based_prompt(patterns_file.name, ...)
            response = await client.query(prompt)
            # ... parse response ...
```

**`prompts/classification.md`** - Add file-reading variant:
```markdown
## Input Patterns

Read the patterns from `{patterns_file}` using the Read tool, then classify each pattern.

The file contains a JSON array of patterns to classify.
```

### Considerations

#### Token Limits Still Apply (But Higher)

The Read tool output goes into context, so there's still an effective limit. However:
- Prompt tokens: ~8K limit for comfortable operation
- Context window: ~200K tokens (Claude 3.5/Opus 4.5)
- Read tool output: treated as tool result, larger capacity

Estimated capacity: 1000-5000 patterns depending on pattern size.

#### Large File Warning

The SDK may warn about large files. Handle gracefully:
```python
# Chunk if file is very large (>100KB)
if patterns_file.stat().st_size > 100_000:
    return await classify_patterns_chunked(patterns_result)
```

#### Error Handling

- Tool execution may fail (permissions, file not found)
- Need fallback to inline approach if file-based fails

### Prototype Status

Not yet prototyped. Ready for implementation with above design.

---

## Investigation 2: Smarter Pattern Prioritization

### Problem Statement

Current sorting (`classifier.py:94`):
```python
all_patterns.sort(key=lambda x: x.get("occurrences", 0), reverse=True)
```

This misses valuable patterns:
- Pattern in 5/36 projects with 20 occurrences (high spread, actionable)
- Ranked lower than pattern in 1 project with 500 occurrences (noise)

### Current Data Available

Each pattern has (from `RawPattern.to_dict()`):
- `occurrences`: Total count
- `session_count`: Unique sessions
- `project_count`: Unique projects
- `pattern_type`: tool_sequence, prompt_prefix, prompt_phrase, file_access

### Proposed Scoring Heuristic

#### Formula

```python
import math

def compute_pattern_score(
    pattern: dict,
    total_projects: int,
    weights: dict | None = None
) -> float:
    """Compute a score balancing frequency, spread, and actionability."""

    w = weights or {
        "occurrence": 1.0,
        "spread": 2.0,      # Weight cross-project patterns
        "session": 0.5,
        "type": 1.5,        # Boost actionable types
    }

    # Actionability by pattern type
    type_multiplier = {
        "tool_sequence": 1.5,   # Highly actionable, clear workflow
        "file_access": 1.2,     # Clear documentation candidate
        "prompt_prefix": 1.0,   # Moderate actionability
        "prompt_phrase": 0.7,   # Often too vague
    }

    occurrences = pattern.get("occurrences", 1)
    session_count = pattern.get("session_count", 1)
    project_count = pattern.get("project_count", 1)
    pattern_type = pattern.get("pattern_type", "unknown")

    # Logarithmic scaling for frequency (diminishing returns)
    frequency_score = math.log(occurrences + 1)

    # Linear spread score (normalized by total projects)
    spread_score = project_count / max(total_projects, 1)
    # Bonus for appearing in multiple projects
    spread_bonus = 1.0 + (0.5 if project_count >= 3 else 0)

    # Session diversity
    session_score = math.log(session_count + 1)

    # Type multiplier
    type_score = type_multiplier.get(pattern_type, 1.0)

    return (
        w["occurrence"] * frequency_score +
        w["spread"] * spread_score * spread_bonus +
        w["session"] * session_score +
        w["type"] * type_score
    )
```

#### Example Scores

| Pattern | Occurrences | Projects | Sessions | Type | Old Rank | New Score | New Rank |
|---------|-------------|----------|----------|------|----------|-----------|----------|
| git workflow | 47 | 8/10 | 12 | tool_sequence | 1 | 8.2 | 1 |
| internal loop | 500 | 1/10 | 3 | prompt_phrase | 2 | 4.1 | 5 |
| config read | 20 | 5/10 | 15 | file_access | 4 | 6.8 | 2 |
| test pattern | 23 | 4/10 | 8 | prompt_prefix | 3 | 5.9 | 3 |

### Chunked Analysis Approach

For large pattern sets (especially with file-based input), analyze in chunks:

#### Three-Pass Strategy

```
┌─────────────────────────────────────────────────────────────────┐
│  Pass 1: Categorize                                              │
│  ─────────────────                                               │
│  Group patterns by type:                                         │
│  - tool_sequences: [...]                                         │
│  - file_access: [...]                                           │
│  - prompt_prefixes: [...]                                       │
│  - prompt_phrases: [...]                                        │
├─────────────────────────────────────────────────────────────────┤
│  Pass 2: Score & Rank (per category)                            │
│  ───────────────────────────────────                            │
│  For each category:                                             │
│  1. Apply scoring heuristic                                     │
│  2. Sort by score descending                                    │
│  3. Keep top N patterns                                         │
├─────────────────────────────────────────────────────────────────┤
│  Pass 3: Aggregate                                              │
│  ────────────────                                                │
│  Combine top patterns from each category:                       │
│  - Ensure diversity (not all one type)                          │
│  - Balance by expected recommendation type                      │
│  - Final limit for LLM classification                           │
└─────────────────────────────────────────────────────────────────┘
```

#### Implementation

```python
def prioritize_patterns(
    patterns: dict[str, list[dict]],
    total_projects: int,
    max_per_type: int = 25,
    max_total: int = 100,
) -> list[dict]:
    """Prioritize patterns using scoring heuristic with category balance."""

    scored_by_type: dict[str, list[tuple[float, dict]]] = {}

    # Pass 1 & 2: Score and rank per type
    for pattern_type, pattern_list in patterns.items():
        scored = [
            (compute_pattern_score(p, total_projects), p)
            for p in pattern_list
        ]
        scored.sort(reverse=True, key=lambda x: x[0])
        scored_by_type[pattern_type] = scored[:max_per_type]

    # Pass 3: Aggregate with balance
    # Priority order for recommendation types
    type_priority = ["tool_sequences", "file_access", "prompt_prefixes", "prompt_phrases"]

    result = []
    for ptype in type_priority:
        if ptype in scored_by_type:
            for score, pattern in scored_by_type[ptype]:
                if len(result) >= max_total:
                    break
                pattern["_score"] = score  # Include for debugging
                result.append(pattern)

    return result
```

### Integration Points

1. **`classifier.py:87-95`**: Replace simple sort with `prioritize_patterns()`
2. **CLI flag**: Add `--scoring-weights` for tuning (optional)
3. **Output**: Include score in debug output for tuning

---

## Implementation Recommendations

### Phase 1: Pattern Prioritization (Quick Win)

**Effort**: 2-4 hours
**Impact**: Immediate quality improvement

1. Add `prioritize_patterns()` function to `classifier.py`
2. Replace current sorting logic
3. Add tests with sample patterns
4. Tune weights based on real data

### Phase 2: File-based Input (Scale Enabler)

**Effort**: 4-8 hours
**Impact**: 20x capacity increase

1. Update `claude_client.py` to accept `ClaudeAgentOptions`
2. Add temp file writing logic to `classifier.py`
3. Create file-based prompt variant
4. Add fallback for tool execution failures
5. Test with large pattern sets

### Phase 3: Combined Approach (Full Solution)

With both improvements:
- Score and prioritize 1000+ patterns
- Select top 100-200 diverse patterns
- Write to temp file
- Claude reads and classifies
- Results cover all important patterns across the archive

---

## Testing Strategy

### Pattern Prioritization Tests

```python
def test_scoring_prefers_spread():
    """Pattern in many projects should score higher than single-project pattern."""
    high_spread = {"occurrences": 20, "project_count": 5, "session_count": 10, "pattern_type": "tool_sequence"}
    single_project = {"occurrences": 100, "project_count": 1, "session_count": 5, "pattern_type": "tool_sequence"}

    assert compute_pattern_score(high_spread, 10) > compute_pattern_score(single_project, 10)

def test_type_multiplier():
    """Tool sequences should score higher than prompt phrases with same stats."""
    tool_seq = {"occurrences": 10, "project_count": 2, "session_count": 5, "pattern_type": "tool_sequence"}
    phrase = {"occurrences": 10, "project_count": 2, "session_count": 5, "pattern_type": "prompt_phrase"}

    assert compute_pattern_score(tool_seq, 10) > compute_pattern_score(phrase, 10)
```

### File-based Input Tests

```python
@pytest.mark.asyncio
async def test_file_based_classification():
    """Large pattern sets should use file-based approach."""
    patterns = generate_test_patterns(count=100)

    with patch_claude_client() as mock:
        mock.configure_read_tool_enabled()
        result = await classify_patterns(patterns)

        # Verify Read tool was offered
        assert "Read" in mock.options.allowed_tools

@pytest.mark.asyncio
async def test_fallback_on_tool_failure():
    """Should fall back to inline if file read fails."""
    patterns = generate_test_patterns(count=100)

    with patch_claude_client() as mock:
        mock.simulate_read_tool_failure()
        result = await classify_patterns(patterns)

        # Should still produce results via fallback
        assert len(result) > 0
```

---

## Appendix: Reference Documentation

- [Agent SDK Python Reference](https://platform.claude.com/docs/en/agent-sdk/python)
- [GitHub: claude-agent-sdk-python](https://github.com/anthropics/claude-agent-sdk-python)
- Current implementation: `src/claude_code_archive/analyzer/classifier.py`
- Prompt template: `src/claude_code_archive/prompts/classification.md`
