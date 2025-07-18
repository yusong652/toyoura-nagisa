"""Register all built-in tools."""

from .google_web_search import register_google_web_search_tool

def register_builtin_tools(mcp):
    """Aggregate registration of all built-in tools."""
    register_google_web_search_tool(mcp)
