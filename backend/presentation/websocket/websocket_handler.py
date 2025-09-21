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
import asyncio
from datetime import datetime
from fastapi import WebSocket, WebSocketDisconnect

from backend.infrastructure.websocket.connection_manager import ConnectionManager, set_connection_manager
from backend.presentation.websocket.message_handler import WebSocketMessageProcessor

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

        # Initialize application services
        from backend.application.services.notifications.message_status_service import MessageStatusService
        from backend.application.services.notifications.bash_confirmation_service import BashConfirmationService
        self.status_service = MessageStatusService(self.connection_manager)
        self.bash_confirmation_service = BashConfirmationService(self.connection_manager)

        # Set global instances for external services to access
        set_connection_manager(self.connection_manager)  # For TTS streaming, notifications
    
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
            # Main message receiving loop - use receive_text() for immediate processing
            # iter_text() may buffer messages, causing delays in processing
            while True:
                # Receive message immediately without buffering
                raw_message = await websocket.receive_text()
                print(f"[WebSocket] Raw message received for session {session_id}: {raw_message}", flush=True)
                print(f"[WebSocket] Message received at: {datetime.now().isoformat()}", flush=True)

                # Debug event loop information
                import threading
                current_loop = asyncio.get_event_loop()
                current_thread = threading.current_thread()
                print(f"[WebSocket] Message processing in thread: {current_thread.name}, event loop: {id(current_loop)}", flush=True)

                # Special debug for LOCATION messages like HEARTBEAT_ACK
                if "LOCATION_RESPONSE" in raw_message:
                    print(f"[LOCATION] Frontend sent LOCATION_RESPONSE to backend: {raw_message}", flush=True)

                # Delegate message content processing to message_handler.py
                # We just receive the raw text and pass it along
                await self.message_processor.process_message(session_id, raw_message)

        except WebSocketDisconnect:
            print(f"[WebSocket] Client disconnected for session {session_id}")
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
    

def create_websocket_handler() -> WebSocketHandler:
    """
    Create a new WebSocket handler instance for application use.

    Called by app.py during FastAPI startup to create the WebSocket
    connection handling system.

    Returns:
        WebSocketHandler: New connection lifecycle manager instance

    Note: The returned instance should be stored in app.state.websocket_handler
    for access throughout the application.
    """
    handler = WebSocketHandler()
    logger.info("WebSocket handler created with bash confirmation service")

    return handler

