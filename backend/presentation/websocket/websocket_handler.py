"""
Unified WebSocket handler - replaces router.py with simplified architecture.

This module provides a single entry point for all WebSocket connections,
integrating connection management with message processing in a clean,
maintainable architecture.
"""
import logging
from typing import Optional
from fastapi import WebSocket, WebSocketDisconnect

from backend.presentation.websocket.connection import ConnectionManager
from backend.presentation.websocket.message_handler import WebSocketMessageProcessor
from backend.presentation.websocket.status_notification_service import (
    MessageStatusNotificationService,
    get_status_notification_service
)

logger = logging.getLogger(__name__)


class WebSocketHandler:
    """
    Unified WebSocket handler that manages connections and message processing.
    
    This class replaces the previous router.py + connection.py separation,
    providing a single, cohesive interface for WebSocket operations.
    """
    
    def __init__(self):
        self.connection_manager = ConnectionManager()
        self.message_processor = WebSocketMessageProcessor(self.connection_manager)
        self.status_service = get_status_notification_service(self.connection_manager)
    
    async def handle_connection(self, websocket: WebSocket, session_id: str):
        """
        Handle complete WebSocket connection lifecycle.

        This method manages connection establishment, message processing loop,
        and cleanup on disconnection.

        Args:
            websocket: WebSocket connection instance
            session_id: Unique session identifier
        """
        # Establish connection
        connected = await self.connection_manager.connect(websocket, session_id)
        if not connected:
            logger.error(f"Failed to establish WebSocket connection for session {session_id}")
            return
        
        try:
            # Message processing loop
            async for message in websocket.iter_text():
                await self.message_processor.process_message(session_id, message)
                
        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected for session {session_id}")
        except Exception as e:
            logger.error(f"Unexpected error in WebSocket handler for session {session_id}: {e}")
        finally:
            # Ensure cleanup
            await self.connection_manager.disconnect(session_id)
    
    def get_connection_manager(self) -> ConnectionManager:
        """Get connection manager instance for external access"""
        return self.connection_manager
    
    def get_message_processor(self) -> WebSocketMessageProcessor:
        """Get message processor for external access"""
        return self.message_processor
    
    async def broadcast_message(self, message_data: dict, exclude_sessions: Optional[set] = None):
        """
        Broadcast message to all connected sessions.
        
        Args:
            message_data: Message data to broadcast
            exclude_sessions: Set of session IDs to exclude from broadcast
        """
        exclude_sessions = exclude_sessions or set()
        
        for session_id in self.connection_manager.get_active_sessions():
            if session_id not in exclude_sessions:
                await self.connection_manager.send_json(session_id, message_data)
    
    async def send_to_session(self, session_id: str, message_data: dict) -> bool:
        """
        Send message to specific session.
        
        Args:
            session_id: Target session ID
            message_data: Message data to send
            
        Returns:
            bool: Whether message was sent successfully
        """
        return await self.connection_manager.send_json(session_id, message_data)
    
    def get_connection_stats(self) -> dict:
        """
        Get current connection statistics.
        
        Returns:
            dict: Connection statistics with active session count and details
        """
        active_sessions = self.connection_manager.get_active_sessions()
        
        return {
            "active_connections": len(active_sessions),
            "session_ids": active_sessions,
            "supported_message_types": list(self.message_processor.handlers.keys()),
            "connection_manager_type": type(self.connection_manager).__name__
        }


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
    Initialize and return WebSocket handler.
    
    This function can be called during application startup to ensure
    the handler is properly initialized.
    
    Returns:
        WebSocketHandler: Initialized handler instance
    """
    global _websocket_handler
    _websocket_handler = WebSocketHandler()
    logger.info("WebSocket handler initialized")
    return _websocket_handler


# Convenience functions for external use
async def handle_websocket_connection(websocket: WebSocket, session_id: str):
    """
    Convenience function to handle WebSocket connection.
    
    Args:
        websocket: WebSocket connection instance
        session_id: Session identifier
    """
    handler = get_websocket_handler()
    await handler.handle_connection(websocket, session_id)


async def send_message_to_session(session_id: str, message_data: dict) -> bool:
    """
    Convenience function to send message to specific session.
    
    Args:
        session_id: Target session ID
        message_data: Message data to send
        
    Returns:
        bool: Whether message was sent successfully
    """
    handler = get_websocket_handler()
    return await handler.send_to_session(session_id, message_data)


async def broadcast_message_to_all(message_data: dict, exclude_sessions: Optional[set] = None):
    """
    Convenience function to broadcast message to all sessions.
    
    Args:
        message_data: Message data to broadcast
        exclude_sessions: Sessions to exclude from broadcast
    """
    handler = get_websocket_handler()
    await handler.broadcast_message(message_data, exclude_sessions)


def get_connection_statistics() -> dict:
    """
    Convenience function to get connection statistics.
    
    Returns:
        dict: Current connection statistics
    """
    handler = get_websocket_handler()
    return handler.get_connection_stats()