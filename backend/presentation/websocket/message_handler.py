"""
Unified WebSocket message handler architecture.

This module provides a centralized, extensible message handling system
for all WebSocket communication in the aiNagisa platform.
"""
import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Type
from datetime import datetime

from backend.presentation.websocket.connection import ConnectionManager
from backend.presentation.websocket.message_types import (
    MessageType, BaseWebSocketMessage, parse_message, create_message
)

logger = logging.getLogger(__name__)


class MessageHandler(ABC):
    """Abstract base class for message handlers"""
    
    def __init__(self, connection_manager: ConnectionManager):
        self.connection_manager = connection_manager
    
    @abstractmethod
    async def handle(self, session_id: str, message: BaseWebSocketMessage) -> Optional[BaseWebSocketMessage]:
        """
        Handle a specific message type.
        
        Args:
            session_id: WebSocket session ID
            message: Parsed message object
            
        Returns:
            Optional response message to send back
        """
        pass
    
    async def send_response(self, session_id: str, response: BaseWebSocketMessage):
        """Send response message to client"""
        await self.connection_manager.send_json(session_id, response.model_dump())
    
    async def send_error(self, session_id: str, error_code: str, error_message: str, 
                        details: Optional[Dict[str, Any]] = None):
        """Send error message to client"""
        error_msg = create_message(
            MessageType.ERROR,
            session_id=session_id,
            error_code=error_code,
            error_message=error_message,
            details=details
        )
        await self.send_response(session_id, error_msg)


class HeartbeatHandler(MessageHandler):
    """Handle heartbeat messages"""
    
    async def handle(self, session_id: str, message: BaseWebSocketMessage) -> Optional[BaseWebSocketMessage]:
        if message.type == MessageType.HEARTBEAT_ACK:
            # Update heartbeat timestamp
            await self.connection_manager.handle_heartbeat_response(session_id)
        
        return None  # Heartbeat doesn't send response


class LocationHandler(MessageHandler):
    """Handle location-related messages"""
    
    def __init__(self, connection_manager: ConnectionManager):
        super().__init__(connection_manager)
        # Store location request events for tool integration
        self.location_events: Dict[str, Dict[str, Any]] = {}
    
    async def handle(self, session_id: str, message: BaseWebSocketMessage) -> Optional[BaseWebSocketMessage]:
        if message.type == MessageType.LOCATION_RESPONSE:
            await self._handle_location_response(session_id, message)
        elif message.type == MessageType.LOCATION_REQUEST:
            await self._handle_location_request(session_id, message)

        return None
    
    async def _handle_location_response(self, session_id: str, message: BaseWebSocketMessage):
        """Process location response from client"""
        
        # Store location data and trigger waiting events
        if session_id in self.location_events:
            event_info = self.location_events[session_id]

            # Extract location data from message
            location_data = getattr(message, 'location_data', None)
            error = getattr(message, 'error', None)

            if location_data:
                event_info["location_data"] = location_data
                event_info["timestamp"] = message.timestamp
                event_info["success"] = True
            else:
                event_info["error"] = error or "Unknown error"
                event_info["success"] = False

            # Trigger event for waiting tools
            event_info["event"].set()
    
    async def _handle_location_request(self, session_id: str, message: BaseWebSocketMessage):
        """Handle location request from tools/backend"""
        request_id = getattr(message, 'request_id', None)
        
        # Create event for response waiting
        event = asyncio.Event()
        self.location_events[session_id] = {
            "request_id": request_id,
            "event": event,
            "timestamp": datetime.now().timestamp()
        }
        
        # Forward request to client
        await self.send_response(session_id, message)
    
    async def wait_for_location_response(self, session_id: str, timeout: float = 30.0) -> Dict[str, Any]:
        """
        Wait for location response from client (used by tools).
        
        Args:
            session_id: Session ID to wait for
            timeout: Timeout in seconds
            
        Returns:
            Dict containing location data or error
        """
        if session_id not in self.location_events:
            return {"success": False, "error": "No location request pending"}
        
        event_info = self.location_events[session_id]
        
        try:
            await asyncio.wait_for(event_info["event"].wait(), timeout=timeout)
            
            # Return result and cleanup
            result = {
                "success": event_info.get("success", False),
                "location_data": event_info.get("location_data"),
                "error": event_info.get("error"),
                "timestamp": event_info.get("timestamp")
            }
            
            del self.location_events[session_id]
            return result
            
        except asyncio.TimeoutError:
            del self.location_events[session_id]
            return {"success": False, "error": f"Location request timeout after {timeout}s"}


class ChatHandler(MessageHandler):
    """Handle chat and streaming messages via WebSocket"""

    def __init__(self, connection_manager: ConnectionManager):
        super().__init__(connection_manager)
        # Import chat service for LLM processing
        from backend.domain.services.chat_service import get_chat_service
        self.chat_service = get_chat_service()

    async def handle(self, session_id: str, message: BaseWebSocketMessage) -> Optional[BaseWebSocketMessage]:
        if message.type == MessageType.CHAT_MESSAGE:
            await self._handle_chat_message(session_id, message)

        return None

    async def _handle_chat_message(self, session_id: str, message: BaseWebSocketMessage):
        """
        Process incoming chat message with full LLM integration.

        Replicates HTTP chat endpoint functionality in WebSocket architecture:
        1. Parse and validate message data
        2. Save user message to session
        3. Generate streaming LLM response
        4. Process TTS if enabled
        5. Handle tool calls and memory injection
        """
        try:
            # Convert WebSocket message to HTTP-compatible request format
            request_data = await self._convert_websocket_message_to_request(session_id, message)

            # Parse request using chat service
            result, enable_memory = await self.chat_service.parse_websocket_request(request_data)

            # Save user message to session
            self.chat_service.save_user_message_to_session(result)

            # Generate streaming response via existing chat service pipeline
            await self._process_streaming_response(session_id, result, enable_memory)

        except Exception as e:
            logger.error(f"Error processing chat message: {e}")
            await self.send_error(
                session_id,
                "CHAT_PROCESSING_ERROR",
                f"Failed to process chat message: {str(e)}"
            )

    async def _convert_websocket_message_to_request(self, session_id: str, message: BaseWebSocketMessage) -> dict:
        """Convert WebSocket ChatMessageRequest to HTTP request format"""
        return {
            "message": getattr(message, 'message', ''),
            "session_id": session_id,
            "agent_profile": getattr(message, 'agent_profile', 'general'),
            "type": getattr(message, 'type', 'text'),
            "message_id": message.message_id,
            "enable_memory": getattr(message, 'enable_memory', True),
            "tts_enabled": getattr(message, 'tts_enabled', False),
            "files": getattr(message, 'files', [])
        }

    async def _process_streaming_response(self, session_id: str, result: Any, enable_memory: bool):
        """
        Process streaming LLM response using existing chat service architecture.

        Integrates with existing streaming pipeline but outputs via WebSocket
        instead of HTTP SSE.
        """
        try:
            # Import chat stream handler which includes status notifications
            from backend.presentation.streaming.chat_stream import generate_chat_stream

            # Use the complete chat stream pipeline which includes status updates
            await generate_chat_stream(
                session_id=result['session_id'],
                enable_memory=enable_memory,
                agent_profile=result['agent_profile'],
                user_message_id=result.get('id')
            )

        except Exception as e:
            logger.error(f"Error in streaming response: {e}")
            await self.send_error(
                session_id,
                "STREAMING_ERROR",
                f"Streaming response failed: {str(e)}"
            )


class ToolCallHandler(MessageHandler):
    """Handle tool call requests"""
    
    async def handle(self, session_id: str, message: BaseWebSocketMessage) -> Optional[BaseWebSocketMessage]:
        if message.type == MessageType.TOOL_CALL_REQUEST:
            await self._handle_tool_call(session_id, message)

        return None

    async def _handle_tool_call(self, session_id: str, message: BaseWebSocketMessage):
        """Process tool call request"""
        
        # TODO: Integrate with MCP tool system
        # For now, send acknowledgment
        tool_name = getattr(message, 'tool_name', 'unknown')
        request_id = getattr(message, 'request_id', '')

        response = create_message(
            MessageType.TOOL_CALL_RESULT,
            session_id=session_id,
            data={
                "tool_name": tool_name,
                "request_id": request_id,
                "status": "acknowledged",
                "result": "Tool integration coming soon"
            }
        )
        
        await self.send_response(session_id, response)


class WebSocketMessageProcessor:
    """Central message processor that routes messages to appropriate handlers"""
    
    def __init__(self, connection_manager: ConnectionManager):
        self.connection_manager = connection_manager
        
        # Initialize handlers (use same instance for related message types)
        heartbeat_handler = HeartbeatHandler(connection_manager)
        location_handler = LocationHandler(connection_manager)
        chat_handler = ChatHandler(connection_manager)
        tool_handler = ToolCallHandler(connection_manager)
        
        self.handlers: Dict[MessageType, MessageHandler] = {
            MessageType.HEARTBEAT_ACK: heartbeat_handler,
            MessageType.LOCATION_REQUEST: location_handler,
            MessageType.LOCATION_RESPONSE: location_handler,  # Same instance for shared state
            MessageType.CHAT_MESSAGE: chat_handler,
            MessageType.TOOL_CALL_REQUEST: tool_handler,
        }
        
        # Store handler instances for cross-handler communication
        self.location_handler = location_handler
    
    async def process_message(self, session_id: str, raw_message: str):
        """
        Process incoming WebSocket message.

        Args:
            session_id: WebSocket session ID
            raw_message: Raw JSON message string
        """
        try:
            # Parse message into typed object
            message = parse_message(raw_message)

            # Route to appropriate handler
            handler = self.handlers.get(message.type)
            if handler:
                response = await handler.handle(session_id, message)

                # Send response if handler returned one
                if response:
                    await handler.send_response(session_id, response)
            else:
                logger.warning(f"No handler for message type: {message.type}")
                await self._send_unsupported_message_error(session_id, message.type)
                
        except ValueError as e:
            logger.error(f"Invalid message format from session {session_id}: {e}")
            await self._send_parse_error(session_id, str(e))
        except Exception as e:
            logger.error(f"Error processing message from session {session_id}: {e}")
            await self._send_internal_error(session_id, str(e))
    
    async def _send_unsupported_message_error(self, session_id: str, message_type: str):
        """Send unsupported message type error"""
        error_msg = create_message(
            MessageType.ERROR,
            session_id=session_id,
            error_code="UNSUPPORTED_MESSAGE_TYPE",
            error_message=f"Message type '{message_type}' is not supported",
            details={"supported_types": list(self.handlers.keys())}
        )
        await self.connection_manager.send_json(session_id, error_msg.model_dump())
    
    async def _send_parse_error(self, session_id: str, error_details: str):
        """Send message parsing error"""
        error_msg = create_message(
            MessageType.ERROR,
            session_id=session_id,
            error_code="MESSAGE_PARSE_ERROR",
            error_message="Failed to parse message",
            details={"error": error_details}
        )
        await self.connection_manager.send_json(session_id, error_msg.model_dump())
    
    async def _send_internal_error(self, session_id: str, error_details: str):
        """Send internal processing error"""
        error_msg = create_message(
            MessageType.ERROR,
            session_id=session_id,
            error_code="INTERNAL_ERROR",
            error_message="Internal server error occurred",
            details={"error": error_details}
        )
        await self.connection_manager.send_json(session_id, error_msg.model_dump())
    
    def get_handler(self, handler_type: Type[MessageHandler]) -> Optional[MessageHandler]:
        """Get handler instance by type for cross-handler communication"""
        for handler in self.handlers.values():
            if isinstance(handler, handler_type):
                return handler
        return None