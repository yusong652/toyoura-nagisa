"""
WebSocket utility functions for toyoura-nagisa.

This module contains utility functions for WebSocket message processing,
including data conversion and transformation utilities.
"""
from typing import Dict, Any
from backend.presentation.websocket.message_types import BaseWebSocketMessage
from backend.domain.models.agent_types import DEFAULT_AGENT_PROFILE


def convert_websocket_message_to_request(session_id: str, message: BaseWebSocketMessage) -> Dict[str, Any]:
    """
    Convert WebSocket message to internal request format for chat service.

    Args:
        session_id: WebSocket session ID
        message: Parsed WebSocket message object

    Returns:
        Dict containing request data in format expected by chat service
    """
    return {
        "message": getattr(message, 'message', ''),
        "session_id": session_id,
        "agent_profile": getattr(message, 'agent_profile', DEFAULT_AGENT_PROFILE),
        "type": getattr(message, 'type', 'text'),
        "message_id": message.message_id,
        "enable_memory": getattr(message, 'enable_memory', True),
        "files": getattr(message, 'files', []),
        "mentioned_files": getattr(message, 'mentioned_files', [])
    }
