"""
PFC Tools - ITASCA PFC simulation integration for aiNagisa.

This package provides MCP tools for controlling ITASCA PFC simulations
through a WebSocket connection to a PFC server running in the PFC GUI.

Tools:
- pfc_execute_command: Execute native PFC commands (no return values)
- pfc_execute_script: Execute Python SDK scripts (with return values)
"""

from .pfc_commands import register_pfc_tools
from .pfc_script import register_pfc_script_tool

__all__ = [
    "register_pfc_tools",
    "register_pfc_script_tool",
]
