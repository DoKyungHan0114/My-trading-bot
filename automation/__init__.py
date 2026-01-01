"""Automation module for Claude analysis and scheduling."""
import importlib

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
    if name == "scheduler":
        # Use importlib to avoid recursion through __getattr__
        return importlib.import_module("automation.scheduler")
    if name == "claude_analyzer":
        # Use importlib to avoid recursion through __getattr__
        return importlib.import_module("automation.claude_analyzer")
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
