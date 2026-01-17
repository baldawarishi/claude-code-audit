"""Analyzer module for pattern detection and workflow analysis."""

from .patterns import (
    PatternDetector,
    RawPattern,
    detect_patterns,
)

# Lazy imports for components that require claude_agent_sdk
# This allows the pattern detection to work without the SDK installed


def __getattr__(name: str):
    """Lazy import for optional dependencies."""
    if name in (
        "ClassifiedPattern",
        "PatternClassifier",
        "classify_patterns",
    ):
        from . import classifier

        return getattr(classifier, name)
    if name == "AnalyzerClaudeClient":
        from . import claude_client

        return claude_client.AnalyzerClaudeClient
    if name in (
        "render_recommendations_markdown",
        "render_summary_stdout",
        "write_recommendations",
    ):
        from . import renderer

        return getattr(renderer, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    # Pattern detection
    "PatternDetector",
    "RawPattern",
    "detect_patterns",
    # Classification (lazy loaded)
    "ClassifiedPattern",
    "PatternClassifier",
    "classify_patterns",
    "AnalyzerClaudeClient",
    # Rendering (lazy loaded)
    "render_recommendations_markdown",
    "render_summary_stdout",
    "write_recommendations",
]
