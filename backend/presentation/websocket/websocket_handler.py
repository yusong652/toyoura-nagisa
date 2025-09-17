"""
WebSocket Connection Lifecycle Manager for aiNagisa.

This module manages the WebSocket connection lifecycle - NOT message content processing.

Key Responsibilities:
1. Accept/reject WebSocket connections from FastAPI routes
2. Manage connection establishment and authentication
3. Handle connection cleanup on disconnect/error
4. Coordinate between infrastructure (ConnectionManager) and presentation (MessageProcessor)
5. Initialize global services for external access

Difference from message_handler.py:
- websocket_handler.py: Connection LIFECYCLE (connect/disconnect/cleanup)
- message_handler.py: Message CONTENT processing (parse/route/handle)

Flow: FastAPI route → websocket_handler.py → message_handler.py → specific handlers
"""
import logging
from typing import Optional
from fastapi import WebSocket, WebSocketDisconnect

from backend.infrastructure.websocket.connection_manager import ConnectionManager, set_connection_manager
from backend.presentation.websocket.message_handler import WebSocketMessageProcessor
from backend.application.services.notifications import get_message_status_service

logger = logging.getLogger(__name__)


class WebSocketHandler:
    """
    WebSocket Connection Lifecycle Coordinator.

    Purpose: Handle WebSocket connections at the FastAPI integration level.
    This is NOT about message content - it's about connection management.

    Responsibilities:
    - Accept WebSocket connections from FastAPI routes
    - Initialize connection manager and message processor
    - Run the connection message loop (websocket.iter_text())
    - Handle disconnections and cleanup resources
    - Bridge between FastAPI and internal message processing

    Note: Actual message parsing and handling happens in message_handler.py
    """
    
    def __init__(self):
        """
        Initialize WebSocket lifecycle components.

        Creates and coordinates the main WebSocket infrastructure:
        - ConnectionManager: Low-level WebSocket connection handling
        - MessageProcessor: High-level message parsing and routing
        - StatusService: WebSocket notification services
        - Global instances: For external service access (TTS, notifications, etc.)
        """
        self.connection_manager = ConnectionManager()  # Infrastructure layer
        self.message_processor = WebSocketMessageProcessor(self.connection_manager)  # Presentation layer
        self.status_service = get_message_status_service(self.connection_manager)  # Application service

        # Set global instances for external services to access
        set_connection_manager(self.connection_manager)  # For TTS streaming, notifications
        from backend.presentation.websocket.message_handler import set_message_processor
        set_message_processor(self.message_processor)  # For external message broadcasting
    
    async def handle_connection(self, websocket: WebSocket, session_id: str):
        """
        Main connection lifecycle handler - called by FastAPI WebSocket route.

        This method handles the entire connection from establishment to cleanup:
        1. Establish connection via ConnectionManager (infrastructure)
        2. Run message receiving loop (websocket.iter_text())
        3. Delegate message parsing/handling to MessageProcessor (presentation)
        4. Handle disconnections and ensure proper cleanup

        Args:
            websocket: FastAPI WebSocket connection instance
            session_id: Unique session identifier from route parameter

        Note: This is the bridge between FastAPI's WebSocket and our internal
        message processing system. Raw message content handling happens in
        message_handler.py, not here.
        """
        # Establish connection
        connected = await self.connection_manager.connect(websocket, session_id)
        if not connected:
            logger.error(f"Failed to establish WebSocket connection for session {session_id}")
            return
        
        try:
            # Main message receiving loop - this is the core WebSocket lifecycle
            async for raw_message in websocket.iter_text():
                # Delegate message content processing to message_handler.py
                # We just receive the raw text and pass it along
                await self.message_processor.process_message(session_id, raw_message)

        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected for session {session_id}")
        except Exception as e:
            logger.error(f"Unexpected error in WebSocket handler for session {session_id}: {e}")
        finally:
            # Critical: Always clean up connection resources
            await self.connection_manager.disconnect(session_id)
    
    def get_connection_manager(self) -> ConnectionManager:
        """Get connection manager instance for external access"""
        return self.connection_manager
    
    def get_message_processor(self) -> WebSocketMessageProcessor:
        """Get message processor for external access"""
        return self.message_processor
    


# Global handler instance for application use
_websocket_handler: Optional[WebSocketHandler] = None


def get_websocket_handler() -> WebSocketHandler:
    """
    Get singleton WebSocket handler instance.
    
    Returns:
        WebSocketHandler: Global handler instance
    """
    global _websocket_handler
    if _websocket_handler is None:
        _websocket_handler = WebSocketHandler()
    return _websocket_handler


def initialize_websocket_handler() -> WebSocketHandler:
    """
    Application startup initialization for WebSocket system.

    Called by app.py during FastAPI startup to initialize the WebSocket
    connection handling system and set up global instances.

    Returns:
        WebSocketHandler: Initialized connection lifecycle manager

    Note: This sets up the global infrastructure that other services
    (TTS, notifications, etc.) will use to send messages via WebSocket.
    """
    global _websocket_handler
    _websocket_handler = WebSocketHandler()
    logger.info("WebSocket handler initialized")
    return _websocket_handler


# Convenience functions for external use
async def handle_websocket_connection(websocket: WebSocket, session_id: str):
    """
    FastAPI route convenience function.

    This is the function that gets called directly by FastAPI WebSocket routes.
    It's the entry point from the web framework into our WebSocket system.

    Args:
        websocket: FastAPI WebSocket connection instance
        session_id: Session identifier from route parameter (/ws/{session_id})

    Usage in routes.py:
        @app.websocket("/ws/{session_id}")
        async def websocket_endpoint(websocket: WebSocket, session_id: str):
            await handle_websocket_connection(websocket, session_id)
    """
    handler = get_websocket_handler()
    await handler.handle_connection(websocket, session_id)


