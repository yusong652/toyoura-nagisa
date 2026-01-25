"""Planning tools for task management and workflow tracking.

This package implements Claude Code-compatible todo_write functionality with
cross-session persistence for maintaining workflow continuity.
"""

from .todo_write import todo_write, register_todo_write_tool

__all__ = [
    "todo_write",
    "register_todo_write_tool",
    "register_planning_tools",
]


def register_planning_tools(mcp):
    """Aggregate registration of all planning tools.

    Args:
        mcp: Tool registrar instance
    """
    register_todo_write_tool(mcp)
