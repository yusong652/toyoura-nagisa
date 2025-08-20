"""Email Tools Module - Gmail integration for email communication."""

from fastmcp import FastMCP
from .send_email import register_send_email_tool
from .check_emails import register_check_emails_tool
from .read_email import register_read_email_tool


def register_email_tools(mcp: FastMCP):
    """Register all Gmail API based email tools."""
    register_send_email_tool(mcp)
    register_check_emails_tool(mcp)
    register_read_email_tool(mcp)