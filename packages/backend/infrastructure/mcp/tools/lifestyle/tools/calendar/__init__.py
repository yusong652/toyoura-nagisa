"""Google Calendar tools – comprehensive calendar management with enterprise-grade functionality.

This module aggregates and registers all calendar tools from their individual modules.
It provides atomic calendar operations focusing on Google Calendar integration
with rich metadata, security controls, and intelligent event processing.

Modeled after the coding tools' architecture for consistency and interoperability.
"""

from fastmcp import FastMCP

from .list_events import register_list_events_tool
from .create_event import register_create_event_tool
from .update_event import register_update_event_tool
from .delete_event import register_delete_event_tool

__all__ = ["register_calendar_tools"]

# -----------------------------------------------------------------------------
# Main registration function
# -----------------------------------------------------------------------------

def register_calendar_tools(mcp: FastMCP):
    """Register all Google Calendar tools with proper tags synchronization.
    
    This function aggregates all calendar tools from their individual modules
    and registers them with the MCP server.
    
    Args:
        mcp: FastMCP instance to register tools with
    """
    
    # Register individual tools from their modules
    register_list_events_tool(mcp)
    register_create_event_tool(mcp)
    register_update_event_tool(mcp)
    register_delete_event_tool(mcp)