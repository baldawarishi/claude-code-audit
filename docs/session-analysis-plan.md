# Session Analysis Plan

Created: 2026-01-19
Status: Ready to implement

## Overview

A human-in-the-loop approach to understanding session patterns before automating recommendations. Replaces the LLM classifier with structured analysis that Claude agents can build on.

## Goals

1. Understand what patterns actually matter (vs noise)
2. Incremental improvements, not groundbreaking changes
3. Each experiment ends with manual verification
4. Analysis files enable future interactive exploration

## Architecture

```
Phase 1: Per-project analysis
├── For each archive project folder:
│   ├── Query sqlite for session metrics (good/bad/ugly definitions)
│   ├── Point Claude at TOML files in archive/transcripts/{project}/
│   ├── Claude randomly picks sessions, reads until patterns emerge
│   └── Output: archive/analysis/run-{timestamp}/{project}.md

Phase 2: Global synthesis
├── Point Claude at archive/analysis/run-{timestamp}/*.md
├── Find cross-project patterns worth optimizing
└── Output: archive/analysis/run-{timestamp}/global-synthesis.md

Phase 3: Interactive exploration (free)
└── User can spin up Claude, point at analysis folder
    └── File paths in analysis let Claude dig into raw TOML when needed
```

## Session Quality Definitions

Based on sqlite data, provide Claude with these heuristics:

| Quality | Criteria (approximate) |
|---------|------------------------|
| **Good** | Few turns (<5), low tokens (<20k), task completed |
| **Okay** | Medium turns (5-15), medium tokens (20k-50k) |
| **Ugly** | Many turns (>15), high tokens (>50k), lots of back-and-forth |

These come from actual data:
- Average turns per session varies by project (5-18)
- Average tokens varies widely (28k-55k)
- High token sessions often indicate struggling or complex tasks

## Output Format Requirements

Each project analysis file must include:

1. **Session summaries** with file paths to source TOML
2. **Metrics observed** (turns, tokens, duration, tools used)
3. **Patterns worth noting** (interesting observations)
4. **Potential optimizations** (things that could help)

Format should support:
- Human review (readable markdown)
- Claude analysis (structured enough to parse)
- Future Phase 3c (skill generation, CLAUDE.md updates)

## Implementation Details

### File Locations

- Input: `archive/transcripts/{project}/*.toml`
- Metrics: `archive/sessions.db` (sqlite)
- Output: `archive/analysis/run-{timestamp}/{project}.md`
- Global: `archive/analysis/run-{timestamp}/global-synthesis.md`

### Projects in Archive

```
Total: 38 project folders
Top by session count:
- java-tools-ai-tools-repo-drift (206 sessions)
- quamina-go-rs-quamina-rs (121 sessions)
- personal-rishibaldawa-banking-ai-onboarding (31 sessions)
- java-build-split (26 sessions)
- repo-drift (21 sessions)
```

### Hardcoded Starting Projects

For initial validation, run on 3 projects in parallel:
1. `repo-drift` - 21 sessions, known project
2. `claude-archive` - 13 sessions, this project
3. `cap-finreq` - 20 sessions, work project variety

This is hardcoded for now; will expand to all projects later.

## Continuation Prompt

Paste this at the start of each new session:

```
Continue work on session analysis. Read docs/session-analysis-plan.md for context.

Current phase: [FILL IN]
Last completed: [FILL IN]
Next step: [FILL IN]

Ask me questions if anything is unclear before proceeding.
```

## Experiment Log

### Experiment 1: [NOT STARTED]
**Goal:** Implement Phase 1 for 3 hardcoded projects
**Status:** Not started
**Verification:** Manual review of output files

### Experiment 2: [NOT STARTED]
**Goal:** Run Phase 2 global synthesis
**Status:** Blocked on Experiment 1
**Verification:** Manual review of global-synthesis.md

---

## TOML Structure (Resolved)

Each session TOML file contains:

```toml
[session]
id = "uuid"
slug = "human-readable-slug"
project = "project-name"
cwd = "/path/to/working/dir"
git_branch = "branch-name"
started_at = "ISO timestamp"
ended_at = "ISO timestamp"
model = "claude-opus-4-5-20251101"
claude_version = "2.1.1"
input_tokens = 2775
output_tokens = 13593
cache_read_tokens = 4581111

[[turns]]
number = 1
timestamp = "ISO timestamp"

[turns.user]
content = "user message"

[turns.assistant]
content = "assistant response"
thinking = "thinking content (if available)"
```

## Questions to Resolve

Before implementing, need answers on:

1. **Analysis depth:** How detailed should each session summary be? (1-2 sentences per session? More?)
2. **Pattern threshold:** How many sessions should show a pattern before it's "worth noting"?
3. **Include thinking blocks?** Should Claude analyze the thinking content too, or just user/assistant?

## Related Files

- `docs/analyzer-issues.md` - Problems with current analyzer
- `docs/analyzer-research.md` - Academic research on pattern mining
- `docs/analyzer-design.md` - Original analyzer design (Phase 3c reference)
- `src/claude_code_archive/analyzer/` - Current analyzer code (to be replaced/simplified)
