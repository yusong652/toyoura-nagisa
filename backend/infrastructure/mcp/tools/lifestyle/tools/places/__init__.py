"""Places tools package - Google Places API integration for location search."""

from .search_places import register_search_places_tool
from .place_details import register_place_details_tool

def register_places_tools(mcp):
    """Register all places tools."""
    register_search_places_tool(mcp)
    register_place_details_tool(mcp)

__all__ = ["register_places_tools"]