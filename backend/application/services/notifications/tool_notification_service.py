"""
Tool Notification Application Service - DDD Application Layer

This service handles tool execution notification use cases by coordinating
between LLM tool calling logic and WebSocket infrastructure.

DDD Role: Application Service
- Implements tool notification use cases
- Uses ConnectionManager (infrastructure) for WebSocket delivery
- Contains business logic for tool calling status updates
"""

import logging
from typing import Dict, Any, Optional, List
from backend.infrastructure.websocket.connection_manager import ConnectionManager
from backend.presentation.websocket.message_types import create_message, MessageType

logger = logging.getLogger(__name__)


class ToolNotificationService:
    """
    Application Service for Tool Execution Notifications.

    Coordinates tool notification use cases:
    - notify_tool_use_started: When tools begin execution
    - notify_tool_use_concluded: When tools finish execution
    - notify_tool_error: When tool execution fails

    Uses ConnectionManager (infrastructure layer) for actual WebSocket delivery.
    Provides clean interface for LLM clients without coupling to WebSocket details.
    """

    def __init__(self, connection_manager: Optional[ConnectionManager] = None):
        """Initialize the tool notification service."""
        self._connection_manager = connection_manager

    def _get_connection_manager(self) -> ConnectionManager:
        """Get connection manager instance with lazy initialization."""
        if self._connection_manager is None:
            # Try to get the global connection manager first
            from backend.infrastructure.websocket.connection_manager import get_connection_manager
            global_manager = get_connection_manager()
            if global_manager is not None:
                self._connection_manager = global_manager
            else:
                # Fallback to creating a new instance
                self._connection_manager = ConnectionManager()
        return self._connection_manager
    
    async def notify_tool_use_started(
        self,
        session_id: str,
        tool_names: List[str],
        action: str,
        thinking: Optional[str] = None
    ) -> bool:
        """
        Send tool use started notification via WebSocket.
        
        Args:
            session_id: Target session ID
            tool_names: List of tool names being executed
            action: Human-readable action description
            thinking: Optional thinking content from LLM
            
        Returns:
            bool: Whether notification was sent successfully
        """
        try:
            connection_manager = self._get_connection_manager()
            
            # Create tool use started message
            message_data = {
                'type': MessageType.NAGISA_IS_USING_TOOL,
                'session_id': session_id,
                'tool_names': tool_names,
                'action': action
            }
            
            if thinking:
                message_data['thinking'] = thinking
            
            # Create WebSocket message
            ws_message = create_message(
                MessageType.NAGISA_IS_USING_TOOL,
                session_id=session_id,
                **{k: v for k, v in message_data.items() if k not in ['type', 'session_id']}
            )
            
            # Send via WebSocket
            success = await connection_manager.send_json(session_id, ws_message.model_dump())
            
            if success:
                logger.info(f"Sent tool use started notification to session {session_id}")
            else:
                logger.warning(f"Failed to send tool use started notification to session {session_id}")
                
            return success
            
        except Exception as e:
            logger.error(f"Error sending tool use started notification: {e}")
            return False
    
    async def notify_tool_use_concluded(
        self,
        session_id: str,
        tool_names: Optional[List[str]] = None,
        results: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Send tool use concluded notification via WebSocket.
        
        Args:
            session_id: Target session ID
            tool_names: List of tool names that were executed
            results: Optional results summary
            
        Returns:
            bool: Whether notification was sent successfully
        """
        try:
            connection_manager = self._get_connection_manager()
            
            # Create tool use concluded message
            message_data = {
                'type': MessageType.NAGISA_TOOL_USE_CONCLUDED,
                'session_id': session_id
            }
            
            if tool_names:
                message_data['tool_names'] = tool_names
            if results:
                message_data['results'] = results
            
            # Create WebSocket message
            ws_message = create_message(
                MessageType.NAGISA_TOOL_USE_CONCLUDED,
                session_id=session_id,
                **{k: v for k, v in message_data.items() if k not in ['type', 'session_id']}
            )
            
            # Send via WebSocket
            success = await connection_manager.send_json(session_id, ws_message.model_dump())
            
            if success:
                logger.info(f"Sent tool use concluded notification to session {session_id}")
            else:
                logger.warning(f"Failed to send tool use concluded notification to session {session_id}")
                
            return success
            
        except Exception as e:
            logger.error(f"Error sending tool use concluded notification: {e}")
            return False
    
    async def notify_tool_error(
        self,
        session_id: str,
        tool_name: str,
        error_message: str,
        error_details: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Send tool execution error notification via WebSocket.
        
        Args:
            session_id: Target session ID
            tool_name: Name of the tool that failed
            error_message: Error description
            error_details: Optional detailed error information
            
        Returns:
            bool: Whether notification was sent successfully
        """
        try:
            connection_manager = self._get_connection_manager()
            
            # Create error message
            error_data = {
                'tool_name': tool_name,
                'error_message': error_message
            }
            
            if error_details:
                error_data.update(error_details)
            
            ws_message = create_message(
                MessageType.ERROR,
                session_id=session_id,
                error_code='TOOL_EXECUTION_ERROR',
                error_message=f"Tool '{tool_name}' execution failed: {error_message}",
                details=error_data
            )
            
            # Send via WebSocket
            success = await connection_manager.send_json(session_id, ws_message.model_dump())
            
            if success:
                logger.info(f"Sent tool error notification to session {session_id}")
            else:
                logger.warning(f"Failed to send tool error notification to session {session_id}")
                
            return success
            
        except Exception as e:
            logger.error(f"Error sending tool error notification: {e}")
            return False
    
    def is_session_connected(self, session_id: str) -> bool:
        """
        Check if a session has an active WebSocket connection.
        
        Args:
            session_id: Session ID to check
            
        Returns:
            bool: Whether session has active WebSocket connection
        """
        try:
            connection_manager = self._get_connection_manager()
            # connection_manager already available from _get_connection_manager()
            return session_id in connection_manager.connections
        except Exception:
            return False


# Global service instance
_tool_notification_service: Optional[ToolNotificationService] = None


def get_tool_notification_service() -> ToolNotificationService:
    """
    Get singleton tool notification service instance.
    
    Returns:
        ToolNotificationService: Global service instance
    """
    global _tool_notification_service
    if _tool_notification_service is None:
        _tool_notification_service = ToolNotificationService()
    return _tool_notification_service


# Convenience functions for easy integration
async def notify_tool_started(
    session_id: str,
    tool_names: List[str],
    action: str,
    thinking: Optional[str] = None
) -> bool:
    """
    Convenience function to send tool use started notification.
    
    Args:
        session_id: Target session ID
        tool_names: List of tool names being executed
        action: Human-readable action description
        thinking: Optional thinking content
        
    Returns:
        bool: Whether notification was sent successfully
    """
    service = get_tool_notification_service()
    return await service.notify_tool_use_started(session_id, tool_names, action, thinking)


async def notify_tool_concluded(
    session_id: str,
    tool_names: Optional[List[str]] = None,
    results: Optional[Dict[str, Any]] = None
) -> bool:
    """
    Convenience function to send tool use concluded notification.
    
    Args:
        session_id: Target session ID
        tool_names: List of tool names that were executed
        results: Optional results summary
        
    Returns:
        bool: Whether notification was sent successfully
    """
    service = get_tool_notification_service()
    return await service.notify_tool_use_concluded(session_id, tool_names, results)


async def notify_tool_error(
    session_id: str,
    tool_name: str,
    error_message: str,
    error_details: Optional[Dict[str, Any]] = None
) -> bool:
    """
    Convenience function to send tool error notification.
    
    Args:
        session_id: Target session ID
        tool_name: Name of the tool that failed
        error_message: Error description
        error_details: Optional detailed error information
        
    Returns:
        bool: Whether notification was sent successfully
    """
    service = get_tool_notification_service()
    return await service.notify_tool_error(session_id, tool_name, error_message, error_details)