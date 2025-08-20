"""Contact Tools Module - Google Contacts integration for directory access."""

from fastmcp import FastMCP
from .list_contacts import register_list_contacts_tool
from .search_contacts import register_search_contacts_tool


def register_contact_tools(mcp: FastMCP):
    """Register all Google Contacts API based tools."""
    register_list_contacts_tool(mcp)
    register_search_contacts_tool(mcp)