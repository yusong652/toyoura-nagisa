"""Agent tools for SubAgent invocation and skill triggering.

This package provides tools for MainAgent to:
- Delegate tasks to specialized SubAgents (invoke_agent)
- Load skill instructions into conversation context (trigger_skill)
"""

from .invoke_agent import invoke_agent, register_invoke_agent_tool
from .trigger_skill import register_trigger_skill_tool

__all__ = [
    "invoke_agent",
    "register_invoke_agent_tool",
    "register_trigger_skill_tool",
    "register_agent_tools",
]


def register_agent_tools(mcp):
    """Register all agent-related tools.

    Args:
        mcp: Tool registrar instance
    """
    register_invoke_agent_tool(mcp)
    register_trigger_skill_tool(mcp)
