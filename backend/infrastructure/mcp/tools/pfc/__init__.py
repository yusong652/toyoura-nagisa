"""
PFC Tools - ITASCA PFC simulation integration for aiNagisa.

This package provides MCP tools for controlling ITASCA PFC simulations
through a WebSocket connection to a PFC server running in the PFC GUI.
"""

from .pfc_commands import register_pfc_tools

__all__ = [
    "register_pfc_tools",
]
