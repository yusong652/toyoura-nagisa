"""
PFC Server - Lightweight WebSocket server for PFC GUI IPython shell.

This module provides a simple WebSocket server that can be started
directly from PFC GUI's IPython shell to enable remote command execution.

Quick Start (in PFC GUI IPython shell):
    >>> from pfc_server import server
    >>> server.start()  # Start server (blocking)

    Or for background execution:
    >>> server.start_background()  # Start server (non-blocking)
"""

__version__ = "0.1.0"

from . import server

__all__ = ["server"]
