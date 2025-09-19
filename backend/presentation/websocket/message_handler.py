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
from typing import Dict, Any, Optional, Type, TYPE_CHECKING

if TYPE_CHECKING:
    from backend.presentation.websocket.message_handler import WebSocketMessageProcessor
from datetime import datetime

from backend.infrastructure.websocket.connection_manager import ConnectionManager
from backend.presentation.websocket.message_types import (
    MessageType, BaseWebSocketMessage, parse_message, create_message
)

logger = logging.getLogger(__name__)

# ==== Global Message Processor Management ====
# Allows external services to send messages via WebSocket when needed

_global_message_processor: Optional['WebSocketMessageProcessor'] = None

def set_message_processor(processor: 'WebSocketMessageProcessor') -> None:
    """Set global message processor instance"""
    global _global_message_processor
    _global_message_processor = processor

def get_message_processor() -> Optional['WebSocketMessageProcessor']:
    """Get global message processor instance"""
    return _global_message_processor


class WebSocketMessageProcessor:
    """
    Central WebSocket message router for aiNagisa.

    Routes incoming WebSocket messages from frontend to appropriate handlers:
    - CHAT_MESSAGE → ChatHandler (main user interaction)
    - LOCATION_* → LocationHandler (geolocation for tools)
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
            MessageType.LOCATION_REQUEST: location_handler,
            MessageType.LOCATION_RESPONSE: location_handler,  # Same instance for shared state
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
                response = await handler.handle(session_id, message)

                # Send response if handler returned one
                if response:
                    await handler.send_response(session_id, response)
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
    """
    Handle WebSocket connection heartbeat messages.

    Purpose: Maintain connection health by responding to heartbeat acknowledgments
    from the frontend. Prevents connection timeout and monitors client availability.
    """

    async def handle(self, session_id: str, message: BaseWebSocketMessage) -> Optional[BaseWebSocketMessage]:
        if message.type == MessageType.HEARTBEAT_ACK:
            handle_time = datetime.now().isoformat()
            print(f"[HeartbeatHandler] Processing HEARTBEAT_ACK from session {session_id} at {handle_time}", flush=True)
            await self.connection_manager.handle_heartbeat_response(session_id)
            print(f"[HeartbeatHandler] Completed HEARTBEAT_ACK processing for session {session_id} at {datetime.now().isoformat()}", flush=True)
        return None


class LocationHandler(MessageHandler):
    """
    Handle geolocation requests and responses.

    Purpose: Coordinate with location-based tools by:
    1. Sending location requests to frontend when tools need GPS data
    2. Receiving location responses from browser geolocation API
    3. Providing location data to waiting tools via event synchronization
    """
    
    def __init__(self, connection_manager: ConnectionManager):
        super().__init__(connection_manager)
        # Store location request futures for tool integration - Future-based pattern
        self.pending_requests: Dict[str, asyncio.Future] = {}
    
    async def handle(self, session_id: str, message: BaseWebSocketMessage) -> Optional[BaseWebSocketMessage]:
        if message.type == MessageType.LOCATION_RESPONSE:
            print(f"[LocationHandler] Processing LOCATION_RESPONSE from session {session_id}", flush=True)
            await self._handle_location_response(session_id, message)
        elif message.type == MessageType.LOCATION_REQUEST:
            print(f"[LocationHandler] Processing LOCATION_REQUEST for session {session_id}", flush=True)
            await self._handle_location_request(session_id, message)

        return None
    
    async def _handle_location_response(self, session_id: str, message: BaseWebSocketMessage):
        """Process location response from frontend and notify waiting tools"""
        print(f"[LocationHandler] Processing location response for session {session_id}", flush=True)

        # Get request_id from message to find the corresponding Future
        # The request_id should be in the parsed message data
        request_id = getattr(message, 'request_id', None)
        if not request_id:
            print(f"[LocationHandler] No request_id in message, cannot correlate response", flush=True)
            return

        if request_id not in self.pending_requests:
            print(f"[LocationHandler] No pending location request found for request_id {request_id}", flush=True)
            return

        future = self.pending_requests[request_id]
        location_data = getattr(message, 'location_data', None)
        error = getattr(message, 'error', None)

        try:
            if location_data:
                print(f"[LocationHandler] Received location data for request {request_id}: {location_data}", flush=True)
                result = {
                    "success": True,
                    "location_data": location_data,
                    "timestamp": message.timestamp
                }
            else:
                print(f"[LocationHandler] Received location error for request {request_id}: {error}", flush=True)
                result = {
                    "success": False,
                    "error": error or "Unknown error"
                }

            # Set Future result using thread-safe callback to handle cross-event-loop communication
            print(f"[LocationHandler] Setting Future result for request {request_id} using call_soon_threadsafe", flush=True)
            loop = future.get_loop()
            loop.call_soon_threadsafe(future.set_result, result)

        except Exception as e:
            print(f"[LocationHandler] Error setting Future result: {e}", flush=True)
            if not future.done():
                # Use thread-safe callback for exception too
                try:
                    loop = future.get_loop()
                    loop.call_soon_threadsafe(future.set_exception, e)
                except Exception as loop_error:
                    print(f"[LocationHandler] Failed to set exception via call_soon_threadsafe: {loop_error}", flush=True)
        finally:
            # Clean up
            if request_id in self.pending_requests:
                del self.pending_requests[request_id]
    
    async def _handle_location_request(self, session_id: str, message: BaseWebSocketMessage):
        """Handle location request from backend tools"""
        request_id = getattr(message, 'request_id', None)
        print(f"[LocationHandler] Creating location request Future for session {session_id}, request_id: {request_id}", flush=True)

        # Create Future for response - this is registered elsewhere by the tool
        print(f"[LocationHandler] Future should already be registered for request_id: {request_id}", flush=True)

        print(f"[LocationHandler] Sending location request to frontend for session {session_id}", flush=True)
        await self.send_response(session_id, message)
        print(f"[LocationHandler] Location request sent to session {session_id}", flush=True)
    
    async def create_location_request(self, request_id: str, timeout: float = 30.0) -> Dict[str, Any]:
        """
        Create a location request and wait for response using Future pattern.

        This is the new elegant solution that doesn't block the event loop.
        """
        print(f"[LocationHandler] Creating location request Future for request_id: {request_id} (timeout: {timeout}s)", flush=True)

        # Create Future for this request
        future = asyncio.Future()
        self.pending_requests[request_id] = future

        try:
            # Wait for the Future to be resolved by _handle_location_response
            # This is NON-BLOCKING - other coroutines can continue processing
            result = await asyncio.wait_for(future, timeout=timeout)
            print(f"[LocationHandler] Location request completed for {request_id}: success={result.get('success')}", flush=True)
            return result

        except asyncio.TimeoutError:
            print(f"[LocationHandler] Location request timeout for {request_id} after {timeout}s", flush=True)
            # Clean up on timeout
            if request_id in self.pending_requests:
                del self.pending_requests[request_id]
            return {"success": False, "error": f"Location request timeout after {timeout}s"}

        except Exception as e:
            print(f"[LocationHandler] Location request error for {request_id}: {e}", flush=True)
            # Clean up on error
            if request_id in self.pending_requests:
                del self.pending_requests[request_id]
            return {"success": False, "error": f"Location request error: {str(e)}"}


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

    async def handle(self, session_id: str, message: BaseWebSocketMessage) -> Optional[BaseWebSocketMessage]:
        if message.type == MessageType.CHAT_MESSAGE:
            await self._handle_chat_message(session_id, message)

        return None

    async def _handle_chat_message(self, session_id: str, message: BaseWebSocketMessage):
        """
        Process user chat message and initiate LLM response.

        Flow:
        1. Convert WebSocket message to internal request format
        2. Save user message to conversation history
        3. Trigger streaming LLM response via chat service

        Note: The assistant message creation (MESSAGE_CREATE) happens later
        in the content processing pipeline, not here. This handler only
        initiates the processing chain.
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

    async def _process_streaming_response(self, session_id: str, result: Any, enable_memory: bool):
        """
        Initiate LLM response generation via existing streaming pipeline.

        This delegates to the chat_stream module which handles:
        - LLM response generation
        - MESSAGE_CREATE events (to create assistant messages in frontend)
        - TTS_CHUNK streaming (for real-time text/audio display)
        - Status updates and error handling
        """
        try:
            # Import chat stream handler which includes status notifications
            from backend.presentation.streaming.chat_stream import generate_chat_stream

            # Use the complete chat stream pipeline which includes status updates
            await generate_chat_stream(
                session_id=session_id,  # Use the WebSocket session_id, not the result's session_id
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



