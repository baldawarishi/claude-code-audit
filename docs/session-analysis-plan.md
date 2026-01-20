# Session Analysis Plan

Created: 2026-01-19 | Status: Ready to implement | Lines target: <300

## Overview

Human-in-the-loop approach to understand session patterns before automating. Replaces LLM classifier with structured analysis.

## Experiment Workflow (IMPORTANT)

1. **One experiment at a time** - Never start experiment N+1 until N is verified
2. **Each session = at most one experiment** - End session after manual verification
3. **Closed feedback loop** - Update this plan after each experiment with learnings
4. **Keep plan <300 lines** - Archive old experiment details to separate files if needed

## Continuation Prompt

```
Continue session analysis. Read docs/session-analysis-plan.md.

Current experiment: [NUMBER]
Status: [implementing | ready-for-verification | verified]
Next: [what to do]

Ask questions if anything unclear. Push often, use todos, read code directly.
```

## Architecture

```
Phase 1: Per-project analysis (Experiments 1-3)
├── Query sqlite for metrics → write context file
├── Invoke `claude` CLI with context → reads TOML files
└── Output: archive/analysis/run-{timestamp}/{project}.md

Phase 2: Global synthesis (Experiment 4)
├── Point Claude at all project analysis files
└── Output: archive/analysis/run-{timestamp}/global-synthesis.md

Phase 3: Interactive exploration (Experiment 5)
└── User asks questions, Claude digs into analysis + TOML as needed
```

## Session Quality Definitions (for Claude context)

| Quality | Turns | Tokens | Characteristics |
|---------|-------|--------|-----------------|
| Good | <5 | <20k | Quick, efficient, task completed |
| Okay | 5-15 | 20-50k | Normal work, some iteration |
| Ugly | >15 | >50k | Struggling, restarts, undo work |

## Implementation

### Files to Modify
- `cli.py` - Replace `analyze` command logic
- `analyzer/` - Simplify: remove classifier.py, claude_client.py

### Test Projects (hardcoded for now)
1. `repo-drift` (21 sessions) - known project
2. `claude-archive` (13 sessions) - this project
3. `cap-finreq` (20 sessions) - work variety

### Subprocess Invocation
```python
subprocess.run([
    "claude", "--print", "-p", prompt,
    "--output-format", "text"
], capture_output=True)
```

### Progress Output
```
[1/3] Analyzing repo-drift (21 sessions)...
[2/3] Analyzing claude-archive (13 sessions)...
[3/3] Analyzing cap-finreq (20 sessions)...
Done. Output: archive/analysis/run-20260119-143052/
```

---

## Current Experiment

### Experiment 1: Implement Phase 1 Runner

**Goal:** Modify `analyze` command to run per-project analysis for 3 hardcoded projects

**Implementation tasks:**
- [ ] Simplify analyzer/ (remove unused LLM code)
- [ ] Add sqlite query for project metrics
- [ ] Write prompt template with context
- [ ] Subprocess call to `claude` CLI
- [ ] Progress output to terminal
- [ ] Capture output to run-{timestamp}/ folder

**Verification (manual by user):**
1. Run: `claude-code-archive analyze --archive-dir ./archive`
2. Check: Output files created in `archive/analysis/run-{timestamp}/`
3. Review: Are the analysis files useful? Readable? Have file paths?
4. Decide: Proceed to Experiment 2, or iterate on Experiment 1?

**Status:** NOT STARTED

---

## Experiment Queue

| # | Name | Depends On | Goal |
|---|------|------------|------|
| 1 | Phase 1 Runner | - | Per-project analysis for 3 projects |
| 2 | Tune Prompt | 1 verified | Improve analysis quality based on review |
| 3 | All Projects | 2 verified | Remove hardcoding, run on all projects |
| 4 | Global Synthesis | 3 verified | Cross-project pattern detection |
| 5 | Interactive | 4 verified | Q&A against analysis files |

---

## Reference

### TOML Structure
```toml
[session]
id, slug, project, cwd, git_branch, started_at, ended_at
model, claude_version, input_tokens, output_tokens, cache_read_tokens

[[turns]]
number, timestamp
[turns.user] content
[turns.assistant] content, thinking
```

### Design Decisions
- Analysis depth: Detailed (step-by-step)
- Pattern threshold: Claude decides, focus pragmatic
- Include thinking: Yes
- Data: SQLite for stats, TOML for content

### Related Files
- `docs/analyzer-issues.md` - Problems with current approach
- `docs/analyzer-research.md` - Academic research
- `docs/analyzer-design.md` - Original design (Phase 3c reference)
