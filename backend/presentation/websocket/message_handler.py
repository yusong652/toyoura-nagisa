"""
Unified WebSocket message handler architecture.

This module provides a centralized, extensible message handling system
for all WebSocket communication in the aiNagisa platform.
"""
import json
import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Type
from datetime import datetime

from backend.presentation.websocket.connection import ConnectionManager
from backend.presentation.websocket.message_types import (
    MessageType, BaseWebSocketMessage, parse_message, create_message,
    LocationResponseMessage, ChatMessageRequest, ToolCallRequest
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
            logger.debug(f"Processed heartbeat ACK for session {session_id}")
        
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
    
    async def _handle_location_response(self, session_id: str, message: LocationResponseMessage):
        """Process location response from client"""
        logger.debug(f"Received location response for session {session_id}")
        
        # Store location data and trigger waiting events
        if session_id in self.location_events:
            event_info = self.location_events[session_id]
            
            if message.location_data:
                event_info["location_data"] = message.location_data
                event_info["timestamp"] = message.timestamp
                event_info["success"] = True
            else:
                event_info["error"] = message.error or "Unknown error"
                event_info["success"] = False
            
            # Trigger event for waiting tools
            event_info["event"].set()
            logger.debug(f"Location event triggered for session {session_id}")
    
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
        logger.debug(f"Forwarded location request to client {session_id}")
    
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
    """Handle chat and streaming messages"""
    
    async def handle(self, session_id: str, message: BaseWebSocketMessage) -> Optional[BaseWebSocketMessage]:
        if message.type == MessageType.CHAT_MESSAGE:
            await self._handle_chat_message(session_id, message)
        
        return None
    
    async def _handle_chat_message(self, session_id: str, message: ChatMessageRequest):
        """Process incoming chat message"""
        logger.info(f"Processing chat message for session {session_id}")
        
        # TODO: Integrate with chat service and LLM
        # For now, send acknowledgment
        response = create_message(
            MessageType.STATUS_UPDATE,
            session_id=session_id,
            status="chat_received",
            data={"message_length": len(message.message)}
        )
        
        await self.send_response(session_id, response)
        
        # If streaming requested, start chat stream
        if message.stream_response:
            await self._start_chat_stream(session_id, message)
    
    async def _start_chat_stream(self, session_id: str, message: ChatMessageRequest):
        """Start streaming chat response"""
        # Send stream start notification
        start_msg = create_message(
            MessageType.CHAT_STREAM_START,
            session_id=session_id,
            message_id=message.message_id
        )
        await self.send_response(session_id, start_msg)
        
        # TODO: Integrate with actual LLM streaming
        # For demo, send mock streaming response
        demo_response = "This is a mock streaming response that will be replaced with actual LLM integration."
        
        for i, word in enumerate(demo_response.split()):
            chunk = create_message(
                MessageType.CHAT_STREAM_CHUNK,
                session_id=session_id,
                content=word + " ",
                is_final=(i == len(demo_response.split()) - 1)
            )
            await self.send_response(session_id, chunk)
            await asyncio.sleep(0.1)  # Simulate streaming delay
        
        # Send stream end notification
        end_msg = create_message(
            MessageType.CHAT_STREAM_END,
            session_id=session_id,
            message_id=message.message_id
        )
        await self.send_response(session_id, end_msg)


class ToolCallHandler(MessageHandler):
    """Handle tool call requests"""
    
    async def handle(self, session_id: str, message: BaseWebSocketMessage) -> Optional[BaseWebSocketMessage]:
        if message.type == MessageType.TOOL_CALL_REQUEST:
            await self._handle_tool_call(session_id, message)
        
        return None
    
    async def _handle_tool_call(self, session_id: str, message: ToolCallRequest):
        """Process tool call request"""
        logger.info(f"Processing tool call '{message.tool_name}' for session {session_id}")
        
        # TODO: Integrate with MCP tool system
        # For now, send acknowledgment
        response = create_message(
            MessageType.TOOL_CALL_RESULT,
            session_id=session_id,
            data={
                "tool_name": message.tool_name,
                "request_id": message.request_id,
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
            logger.debug(f"Processing {message.type} message for session {session_id}")
            
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