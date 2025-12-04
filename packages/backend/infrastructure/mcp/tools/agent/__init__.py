"""Agent tools for SubAgent invocation.

This package provides tools for MainAgent to delegate tasks to specialized SubAgents.
"""

from .invoke_agent import invoke_agent, register_invoke_agent_tool

__all__ = [
    "invoke_agent",
    "register_invoke_agent_tool",
    "register_agent_tools",
]


def register_agent_tools(mcp):
    """Register all agent-related tools.

    Args:
        mcp: FastMCP server instance
    """
    register_invoke_agent_tool(mcp)
