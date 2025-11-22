"""
Presentation Layer Exception Handling.

This module provides centralized exception handling for the presentation layer
including HTTP error responses, WebSocket error handling, and API error formatting.
"""

from .handlers import register_exception_handlers

__all__ = [
    "register_exception_handlers"
]