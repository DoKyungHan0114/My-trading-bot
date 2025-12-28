"""Automation module for Claude analysis and scheduling."""

# Lazy imports to avoid circular dependencies and unnecessary loading
# Use: from automation.claude_analyzer import ClaudeAnalyzer
# Use: from automation.scheduler import AutomationScheduler

__all__ = ["ClaudeAnalyzer", "AutomationScheduler"]


def __getattr__(name):
    """Lazy import to avoid loading heavy dependencies."""
    if name == "ClaudeAnalyzer":
        from automation.claude_analyzer import ClaudeAnalyzer
        return ClaudeAnalyzer
    if name == "AutomationScheduler":
        from automation.scheduler import AutomationScheduler
        return AutomationScheduler
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
