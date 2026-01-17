"""Markdown output generation for analysis recommendations."""

from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Optional

from .classifier import ClassifiedPattern


def render_recommendations_markdown(
    classifications: list[ClassifiedPattern],
    total_sessions: int,
    total_projects: int,
    archive_dir: Optional[Path] = None,
) -> str:
    """Render classified patterns as markdown recommendations.

    Args:
        classifications: List of ClassifiedPattern objects
        total_sessions: Total sessions analyzed
        total_projects: Total projects in archive
        archive_dir: Path to archive directory (for display)

    Returns:
        Formatted markdown string
    """
    lines = []

    # Header
    lines.append("# Workflow Analysis Recommendations")
    lines.append(f"Generated: {datetime.utcnow().isoformat()}")
    archive_str = str(archive_dir) if archive_dir else "./archive"
    lines.append(f"Archive: {archive_str} ({total_sessions} sessions, {total_projects} projects)")
    lines.append("")

    # Group classifications by scope
    by_scope: dict[str, list[ClassifiedPattern]] = defaultdict(list)
    for c in classifications:
        by_scope[c.scope].append(c)

    # Sort scopes: global first, then projects alphabetically, then subdirs
    def scope_sort_key(scope: str) -> tuple[int, str]:
        if scope == "global":
            return (0, "")
        elif scope.startswith("project:"):
            return (1, scope[8:])
        elif scope.startswith("subdir:"):
            return (2, scope[7:])
        return (3, scope)

    sorted_scopes = sorted(by_scope.keys(), key=scope_sort_key)

    for scope in sorted_scopes:
        patterns = by_scope[scope]

        # Section header
        if scope == "global":
            lines.append("## Global Recommendations")
            lines.append("Patterns appearing across multiple projects.")
        elif scope.startswith("project:"):
            project_name = scope[8:]
            lines.append(f"## Project: {project_name}")
            lines.append("Patterns specific to this project.")
        elif scope.startswith("subdir:"):
            subdir_path = scope[7:]
            lines.append(f"## Subdirectory: {subdir_path}")
            lines.append("Patterns specific to this subdirectory.")
        else:
            lines.append(f"## {scope}")

        lines.append("")

        # Sort patterns within scope by confidence (high first) then occurrences
        patterns.sort(
            key=lambda p: (
                {"high": 0, "medium": 1, "low": 2}.get(p.confidence, 3),
                -p.raw_pattern.occurrences,
            )
        )

        for pattern in patterns:
            lines.extend(_render_pattern(pattern))
            lines.append("")

    return "\n".join(lines)


def _render_pattern(pattern: ClassifiedPattern) -> list[str]:
    """Render a single pattern as markdown."""
    lines = []

    # Pattern title
    pattern_type_label = {
        "tool_sequence": "Tool Sequence",
        "prompt_prefix": "Prompt Pattern",
        "prompt_phrase": "Prompt Phrase",
        "file_access": "File Access",
    }.get(pattern.raw_pattern.pattern_type, "Pattern")

    lines.append(f"### {pattern_type_label}: {pattern.raw_pattern.pattern_key}")

    # Metadata
    lines.append(f"- **Category**: {_format_category(pattern.category)}")
    lines.append(f"- **Confidence**: {pattern.confidence}")
    lines.append(
        f"- **Occurrences**: {pattern.raw_pattern.occurrences} "
        f"across {len(pattern.raw_pattern.sessions)} sessions"
    )

    # Time span if available
    if pattern.raw_pattern.first_seen and pattern.raw_pattern.last_seen:
        first = pattern.raw_pattern.first_seen[:10]
        last = pattern.raw_pattern.last_seen[:10]
        lines.append(f"- **Time span**: {first} to {last}")

    # Projects
    projects = sorted(pattern.raw_pattern.projects)
    if len(projects) <= 3:
        lines.append(f"- **Projects**: {', '.join(projects)}")
    else:
        shown = ", ".join(projects[:3])
        lines.append(f"- **Projects**: {shown} (+{len(projects) - 3} more)")

    # Reasoning
    if pattern.reasoning:
        lines.append("")
        lines.append(f"> {pattern.reasoning}")

    # Suggested content in details block
    if pattern.suggested_content:
        lines.append("")
        content_type = _get_content_type_label(pattern.category, pattern.suggested_name)
        lines.append(f"<details><summary>Suggested {content_type}</summary>")
        lines.append("")
        lines.append("```yaml" if pattern.category == "skill" else "```markdown")
        lines.append(pattern.suggested_content)
        lines.append("```")
        lines.append("")
        lines.append("</details>")

    lines.append("")
    lines.append("---")

    return lines


def _format_category(category: str) -> str:
    """Format category for display."""
    return {
        "skill": "Skill",
        "claude_md": "CLAUDE.md",
        "hook": "Hook",
    }.get(category, category)


def _get_content_type_label(category: str, suggested_name: str) -> str:
    """Get the content type label for the suggested content."""
    if category == "skill":
        return f"SKILL.md ({suggested_name})"
    elif category == "claude_md":
        return "CLAUDE.md addition"
    elif category == "hook":
        return "Hook configuration"
    return "content"


def render_summary_stdout(
    classifications: list[ClassifiedPattern],
    total_sessions: int,
    total_projects: int,
) -> str:
    """Render a summary for stdout output.

    Args:
        classifications: List of ClassifiedPattern objects
        total_sessions: Total sessions analyzed
        total_projects: Total projects in archive

    Returns:
        Summary string for stdout
    """
    lines = []
    lines.append(f"Analyzed {total_sessions} sessions across {total_projects} projects")
    lines.append("")

    # Count by category
    by_category: dict[str, int] = defaultdict(int)
    for c in classifications:
        by_category[c.category] += 1

    lines.append("Recommendations found:")
    for category in ["skill", "claude_md", "hook"]:
        count = by_category.get(category, 0)
        if count > 0:
            lines.append(f"  {_format_category(category)}: {count}")

    # Count by confidence
    lines.append("")
    lines.append("By confidence:")
    by_confidence: dict[str, int] = defaultdict(int)
    for c in classifications:
        by_confidence[c.confidence] += 1

    for level in ["high", "medium", "low"]:
        count = by_confidence.get(level, 0)
        if count > 0:
            lines.append(f"  {level}: {count}")

    # Count by scope type
    lines.append("")
    lines.append("By scope:")
    global_count = sum(1 for c in classifications if c.scope == "global")
    project_count = sum(1 for c in classifications if c.scope.startswith("project:"))
    subdir_count = sum(1 for c in classifications if c.scope.startswith("subdir:"))

    if global_count > 0:
        lines.append(f"  global: {global_count}")
    if project_count > 0:
        lines.append(f"  project-specific: {project_count}")
    if subdir_count > 0:
        lines.append(f"  subdirectory: {subdir_count}")

    return "\n".join(lines)


def write_recommendations(
    classifications: list[ClassifiedPattern],
    output_path: Path,
    total_sessions: int,
    total_projects: int,
    archive_dir: Optional[Path] = None,
) -> None:
    """Write recommendations to a markdown file.

    Args:
        classifications: List of ClassifiedPattern objects
        output_path: Path to write the markdown file
        total_sessions: Total sessions analyzed
        total_projects: Total projects in archive
        archive_dir: Path to archive directory (for display)
    """
    markdown = render_recommendations_markdown(
        classifications=classifications,
        total_sessions=total_sessions,
        total_projects=total_projects,
        archive_dir=archive_dir,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown)
