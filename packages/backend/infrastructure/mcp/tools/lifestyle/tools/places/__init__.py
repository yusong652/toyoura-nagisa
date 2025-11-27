"""Places tools package - Google Places API integration for location search."""

from .search_places import register_search_places_tool

def register_places_tools(mcp):
    """Register places search tool."""
    register_search_places_tool(mcp)

__all__ = ["register_places_tools"]