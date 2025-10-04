"""
PFC Infrastructure Module - Core integration with ITASCA PFC simulation.

This module provides the foundational infrastructure for aiNagisa's PFC agent capabilities,
one of the project's key differentiating features.

Provides:
- WebSocket communication with PFC server
- Command execution (native PFC commands)
- Script execution (Python SDK scripts)
"""

from .websocket_client import PFCWebSocketClient, get_client

__all__ = ["PFCWebSocketClient", "get_client"]
