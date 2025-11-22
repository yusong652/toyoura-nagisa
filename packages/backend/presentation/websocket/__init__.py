"""
WebSocket module for real-time client-server communication.

This module provides:
- Message handling: Processing incoming WebSocket messages
- Message sending: Sending outgoing messages to clients
- Message types: WebSocket message definitions and utilities
"""

from .message_sender import send_message_create, send_tts_chunk

__all__ = [
    'send_message_create',
    'send_tts_chunk'
]