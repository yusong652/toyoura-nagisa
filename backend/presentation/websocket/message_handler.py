"""
WebSocket Message Handler System for aiNagisa.

This module handles incoming WebSocket messages from the frontend and routes them
to appropriate processors. The main purpose is to:

1. Process user chat messages and trigger LLM response generation
2. Handle location requests/responses for geolocation tools
3. Manage heartbeat messages for connection health
4. Create assistant messages in the frontend UI

Key Flow:
- User sends CHAT_MESSAGE → ChatHandler processes → Streaming LLM response
- Backend needs to show assistant message → MESSAGE_CREATE sent to frontend
- TTS/content chunks sent via WebSocket for real-time display
"""
import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Type

from datetime import datetime

from backend.infrastructure.websocket.connection_manager import ConnectionManager
from backend.presentation.websocket.message_types import (
    MessageType, BaseWebSocketMessage, parse_message, create_message
)

logger = logging.getLogger(__name__)

class WebSocketMessageProcessor:
    """
    Central WebSocket message router for aiNagisa.

    Routes incoming WebSocket messages from frontend to appropriate handlers:
    - CHAT_MESSAGE → ChatHandler (main user interaction)
    - LOCATION_RESPONSE → LocationHandler (geolocation responses from frontend)
    - HEARTBEAT_ACK → HeartbeatHandler (connection health)

    This is the main entry point for all WebSocket message processing.
    """
    
    def __init__(self, connection_manager: ConnectionManager):
        self.connection_manager = connection_manager
        
        # Initialize handlers (use same instance for related message types)
        heartbeat_handler = HeartbeatHandler(connection_manager)
        location_handler = LocationHandler(connection_manager)
        chat_handler = ChatHandler(connection_manager)

        self.handlers: Dict[MessageType, MessageHandler] = {
            MessageType.HEARTBEAT_ACK: heartbeat_handler,
            MessageType.LOCATION_RESPONSE: location_handler,  # Only handle responses from frontend
            MessageType.CHAT_MESSAGE: chat_handler,
        }
        
        # Store location handler for external tool access
        self.location_handler = location_handler
    
    async def process_message(self, session_id: str, raw_message: str):
        """
        Process incoming WebSocket message.

        Args:
            session_id: WebSocket session ID
            raw_message: Raw JSON message string
        """
        processing_start = datetime.now()
        try:
            # Parse message into typed object
            message = parse_message(raw_message)
            print(f"[WebSocket] Backend received message type: {message.type} from session {session_id} at {processing_start.isoformat()}", flush=True)

            # Route to appropriate handler
            handler = self.handlers.get(message.type)
            if handler:
                await handler.handle(session_id, message)
            else:
                logger.warning(f"No handler for message type: {message.type}")
                await self._send_error(
                    session_id,
                    "UNSUPPORTED_MESSAGE_TYPE",
                    f"Message type '{message.type}' is not supported",
                    {"supported_types": list(self.handlers.keys())}
                )

        except ValueError as e:
            logger.error(f"Invalid message format from session {session_id}: {e}")
            await self._send_error(session_id, "MESSAGE_PARSE_ERROR", "Failed to parse message", {"error": str(e)})
        except Exception as e:
            logger.error(f"Error processing message from session {session_id}: {e}")
            await self._send_error(session_id, "INTERNAL_ERROR", "Internal server error occurred", {"error": str(e)})
    
    async def _send_error(self, session_id: str, error_code: str, error_message: str, details: Optional[Dict[str, Any]] = None):
        """Send error message to client"""
        error_msg = create_message(
            MessageType.ERROR,
            session_id=session_id,
            error_code=error_code,
            error_message=error_message,
            details=details or {}
        )
        await self.connection_manager.send_json(session_id, error_msg.model_dump())
    

class MessageHandler(ABC):
    """Abstract base class for message handlers"""
    
    def __init__(self, connection_manager: ConnectionManager):
        self.connection_manager = connection_manager
    
    @abstractmethod
    async def handle(self, session_id: str, message: BaseWebSocketMessage) -> None:
        """
        Handle a specific message type.

        Args:
            session_id: WebSocket session ID
            message: Parsed message object
        """
        pass

    async def send_error(self, session_id: str, error_code: str, error_message: str,
                        details: Optional[Dict[str, Any]] = None):
        """Send error message to client"""
        error_msg = create_message(
            MessageType.ERROR,
            session_id=session_id,
            error_code=error_code,
            error_message=error_message,
            details=details or {}
        )
        await self.connection_manager.send_json(session_id, error_msg.model_dump())


class HeartbeatHandler(MessageHandler):
    """
    Handle WebSocket connection heartbeat messages.

    Purpose: Maintain connection health by responding to heartbeat acknowledgments
    from the frontend. Prevents connection timeout and monitors client availability.
    """

    async def handle(self, session_id: str, message: BaseWebSocketMessage) -> None:
        if message.type == MessageType.HEARTBEAT_ACK:
            handle_time = datetime.now().isoformat()
            print(f"[HeartbeatHandler] Processing HEARTBEAT_ACK from session {session_id} at {handle_time}", flush=True)
            await self.connection_manager.handle_heartbeat_response(session_id)
            print(f"[HeartbeatHandler] Completed HEARTBEAT_ACK processing for session {session_id} at {datetime.now().isoformat()}", flush=True)


class LocationHandler(MessageHandler):
    """
    Handle geolocation responses from frontend.

    Purpose: Process location responses from frontend and store them in cache
    for MCP tools to access. Location requests are sent directly by tools.
    """

    async def handle(self, session_id: str, message: BaseWebSocketMessage) -> None:
        if message.type == MessageType.LOCATION_RESPONSE:
            print(f"[LocationHandler] Processing LOCATION_RESPONSE from session {session_id}", flush=True)

            # Extract location data from message
            location_data = getattr(message, 'location_data', None)
            error = getattr(message, 'error', None)

            if location_data:
                print(f"[LocationHandler] Received location data: lat={location_data.get('latitude')}, "
                      f"lng={location_data.get('longitude')}, accuracy={location_data.get('accuracy')}", flush=True)

                # Store in cache for MCP tools to access
                from backend.infrastructure.websocket.message_cache import get_message_cache
                cache = get_message_cache()
                cache.store_message("location", session_id, location_data)
            else:
                print(f"[LocationHandler] Received location error: {error}", flush=True)
    
class ChatHandler(MessageHandler):
    """
    Handle user chat messages and trigger LLM response generation.

    Purpose: This is the main handler that processes user messages and:
    1. Parses user input from frontend CHAT_MESSAGE events
    2. Saves user message to conversation history
    3. Triggers LLM response generation via existing chat service
    4. Initiates streaming response delivery to frontend

    Note: The actual assistant message creation (MESSAGE_CREATE) and content
    streaming (TTS_CHUNK) happens in the content processing pipeline,
    not directly in this handler.
    """

    def __init__(self, connection_manager: ConnectionManager):
        super().__init__(connection_manager)
        # Import chat service for LLM processing
        from backend.application.services.chat_service import get_chat_service
        self.chat_service = get_chat_service()

    async def handle(self, session_id: str, message: BaseWebSocketMessage) -> None:
        if message.type == MessageType.CHAT_MESSAGE:
            try:
                # Convert WebSocket message to internal request format
                request_data = await self._convert_websocket_message_to_request(session_id, message)

                # Parse request using chat service
                result, enable_memory = await self.chat_service.parse_websocket_request(request_data)

                # Save user message to session
                self.chat_service.save_user_message_to_session(result)

                # Generate streaming response in background task (non-blocking)
                from backend.presentation.streaming.chat_stream import generate_chat_stream
                asyncio.create_task(generate_chat_stream(
                    session_id=session_id,
                    enable_memory=enable_memory,
                    agent_profile=result['agent_profile'],
                    user_message_id=result.get('id')
                ))

            except Exception as e:
                logger.error(f"Error processing chat message: {e}")
                await self.send_error(
                    session_id,
                    "CHAT_PROCESSING_ERROR",
                    f"Failed to process chat message: {str(e)}"
                )

    async def _convert_websocket_message_to_request(self, session_id: str, message: BaseWebSocketMessage) -> dict:
        """Convert WebSocket message to internal request format for chat service"""
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
