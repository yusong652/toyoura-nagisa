"""
WebSocket Routes - Centralized WebSocket endpoint definitions.

This module provides WebSocket routes using the new unified handler architecture,
simplifying the routing layer and providing better extensibility.
"""
from fastapi import FastAPI, WebSocket
from backend.presentation.websocket.message_types import MessageType


def register_websocket_routes(app: FastAPI):
    """
    Register all WebSocket routes with the FastAPI application.
    
    Uses the new unified WebSocket handler architecture for simplified
    message processing and connection management.
    
    Args:
        app: FastAPI application instance to register routes on
        
    Note:
        The new architecture eliminates the need for separate router
        and connection manager instances in the app state.
    """
    
    @app.websocket("/ws/{session_id}")
    async def websocket_session_endpoint(websocket: WebSocket, session_id: str):
        """
        Unified WebSocket endpoint for session-based real-time communication.

        Handles all WebSocket connections using the new message handler architecture,
        supporting multiple message types including chat, location, tools, and more.

        Args:
            websocket: WebSocket connection instance
            session_id: Session UUID for connection context

        Features:
            - Unified message processing with type validation
            - Extensible handler system for new message types
            - Improved error handling and logging
            - Stream-capable chat responses
            - Tool integration support
        """
        try:
            # Directly use the WebSocket handler from app state
            # No need for wrapper function - simpler and clearer
            handler = app.state.websocket_handler
            await handler.handle_connection(websocket, session_id)
        except Exception as e:
            print(f"[WebSocket] Error in unified handler: {e}")
            raise


def get_websocket_info() -> dict:
    """
    Get information about registered WebSocket routes and capabilities.
    
    Provides comprehensive metadata about the WebSocket system including
    supported message types, handlers, and features.
    
    Returns:
        dict: WebSocket system information with structure:
            - routes: List of WebSocket route definitions
            - message_types: List of supported message types
            - handlers: List of available message handlers
            - features: List of supported features
    
    Example:
        info = get_websocket_info()
        print(f"Supported message types: {len(info['message_types'])}")
    """
    # Get all message types
    message_types = [msg_type.value for msg_type in MessageType]
    
    return {
        "routes": [
            {
                "path": "/ws/{session_id}",
                "description": "Unified real-time communication endpoint",
                "parameters": ["session_id"],
                "architecture": "unified_handler"
            }
        ],
        "message_types": message_types,
        "handlers": [
            "HeartbeatHandler",
            "LocationHandler", 
            "ChatHandler",
            "ToolCallHandler"
        ],
        "features": [
            "heartbeat_monitoring",
            "location_services",
            "chat_streaming", 
            "tool_integration",
            "file_operations",
            "error_handling",
            "type_validation",
            "extensible_architecture"
        ],
        "architecture_info": {
            "version": "2.0",
            "type": "unified_handler",
            "connection_management": "integrated",
            "message_validation": "pydantic_based",
            "extensibility": "handler_plugin_system"
        }
    }