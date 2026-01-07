"""Register all built-in tools."""

from .web_search import register_web_search_tool
from .web_fetch import register_web_fetch_tool


def register_builtin_tools(mcp):
    """Aggregate registration of all built-in tools."""
    register_web_search_tool(mcp)
    register_web_fetch_tool(mcp)
