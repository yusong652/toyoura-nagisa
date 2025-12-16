"""
PFC Infrastructure Module - Core integration with ITASCA PFC simulation.

This module provides the foundational infrastructure for toyoura-nagisa's PFC agent capabilities,
one of the project's key differentiating features.

Provides:
- WebSocket communication with PFC server
- Command execution (native PFC commands)
- Script execution (Python SDK scripts)
"""

from .client import PFCWebSocketClient, get_client

__all__ = ["PFCWebSocketClient", "get_client"]
