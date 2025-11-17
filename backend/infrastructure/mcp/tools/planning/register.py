"""Registration of planning tools."""

from fastmcp import FastMCP
from .todo_write import todo_write


def register_planning_tools(mcp: FastMCP) -> None:
    """
    Register planning tools for task management and workflow tracking.

    Args:
        mcp: FastMCP server instance
    """
    mcp.tool()(todo_write)
