"""
WebSocket Message Handler System for toyoura-nagisa.

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
from typing import Dict, Any, Optional

from datetime import datetime

from backend.infrastructure.websocket.connection_manager import ConnectionManager
from backend.presentation.websocket.message_types import (
    MessageType, BaseWebSocketMessage, parse_incoming_websocket_message, create_message
)
from backend.application.services.shell import get_bash_execution_service
from backend.application.services.pfc import get_pfc_execution_service

logger = logging.getLogger(__name__)

class WebSocketMessageProcessor:
    """
    Central WebSocket message router for toyoura-nagisa.

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

        # Initialize tool confirmation handler
        tool_confirmation_handler = ToolConfirmationHandler(connection_manager)

        # Initialize user interrupt handler
        user_interrupt_handler = UserInterruptHandler(connection_manager)

        # Initialize move-to-background handler (ctrl+b)
        move_to_background_handler = MoveToBackgroundHandler(connection_manager)

        self.handlers: Dict[MessageType, MessageHandler] = {
            MessageType.HEARTBEAT_ACK: heartbeat_handler,
            MessageType.LOCATION_RESPONSE: location_handler,  # Only handle responses from frontend
            MessageType.CHAT_MESSAGE: chat_handler,
            MessageType.TOOL_CONFIRMATION_RESPONSE: tool_confirmation_handler,
            MessageType.USER_INTERRUPT: user_interrupt_handler,
            MessageType.MOVE_TO_BACKGROUND: move_to_background_handler,
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
        try:
            # Parse message into typed object
            message = parse_incoming_websocket_message(raw_message)
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
            await self.connection_manager.handle_heartbeat_response(session_id)


class LocationHandler(MessageHandler):
    """
    Handle geolocation responses from frontend.

    Purpose: Process location responses from frontend and notify waiting
    MCP tools via asyncio Event. Location requests are sent directly by tools.
    """

    async def handle(self, session_id: str, message: BaseWebSocketMessage) -> None:
        if message.type == MessageType.LOCATION_RESPONSE:
            # Extract location data from message
            location_data = getattr(message, 'location_data', None)
            error = getattr(message, 'error', None)

            # Notify waiting code via event manager
            from backend.infrastructure.websocket.location_response_manager import get_location_response_manager
            manager = get_location_response_manager()

            if location_data:
                manager.set_response(session_id, location_data=location_data)
            else:
                print(f"[LocationHandler] Received location error: {error}", flush=True)
                manager.set_response(session_id, error=error)
    
class ChatHandler(MessageHandler):
    """
    Handle user chat messages with queue-based processing.

    Purpose: This is the main handler that processes user messages and:
    1. Parses user input from frontend CHAT_MESSAGE events
    2. Adds messages to session queue (prevents message loss)
    3. Processes messages sequentially via queue
    4. Triggers LLM response generation for each message

    Queue Behavior:
    - Message arrives → Added to queue → Queue position returned
    - If session idle → Start processing immediately
    - If session busy → Wait in queue, process when ready
    - Sequential processing ensures messages are never lost

    Note: The actual assistant message creation (MESSAGE_CREATE) and content
    streaming (TTS_CHUNK) happens in the content processing pipeline,
    not directly in this handler.
    """

    def __init__(self, connection_manager: ConnectionManager):
        super().__init__(connection_manager)
        # Import chat service for LLM processing
        from backend.application.services.chat_service import get_chat_service
        from backend.infrastructure.messaging import get_queue_manager
        self.chat_service = get_chat_service()
        self.queue_manager = get_queue_manager()

    async def handle(self, session_id: str, message: BaseWebSocketMessage) -> None:
        if message.type == MessageType.CHAT_MESSAGE:
            try:
                # Convert WebSocket message to internal request format
                from backend.presentation.websocket.utils import convert_websocket_message_to_request
                request_data = convert_websocket_message_to_request(session_id, message)

                print(f"[ChatHandler] Received CHAT_MESSAGE from session {session_id}", flush=True)

                # Add message to queue instead of processing immediately
                queue_position = await self.queue_manager.enqueue_message(session_id, request_data)

                # Send queue confirmation to frontend
                await self._notify_message_queued(session_id, queue_position)

                # Start processing if session is idle
                if await self.queue_manager.start_processing(session_id):
                    print(f"[ChatHandler] Starting queue processing for session {session_id}", flush=True)
                    asyncio.create_task(
                        self.queue_manager.process_queue(
                            session_id,
                            self._process_single_message
                        )
                    )
                else:
                    print(f"[ChatHandler] Message queued (position {queue_position}) for busy session {session_id}", flush=True)

            except Exception as e:
                logger.error(f"Error handling chat message: {e}")
                await self.send_error(
                    session_id,
                    "CHAT_HANDLING_ERROR",
                    f"Failed to handle chat message: {str(e)}"
                )

    async def _process_single_message(self, session_id: str, request_data: dict) -> None:
        """
        Process a single message from the queue.

        This method is called by the queue manager for each message
        in the queue, ensuring sequential processing.

        Args:
            session_id: Session identifier
            request_data: Message data to process
        """
        try:
            print(f"[ChatHandler] Processing message from queue for session {session_id}", flush=True)

            # Prepare user message (parsing, reminders injection, but NO persistence)
            # Agent.execute() is now responsible for message persistence
            prepared_message = await self.chat_service.prepare_user_message(request_data)

            # Generate streaming response with explicit instruction passing
            from backend.presentation.handlers.chat_request_handler import process_chat_request
            await process_chat_request(prepared_message)

            print(f"[ChatHandler] Completed processing message for session {session_id}", flush=True)

        except Exception as e:
            logger.error(f"Error processing message from queue: {e}")
            await self.send_error(
                session_id,
                "CHAT_PROCESSING_ERROR",
                f"Failed to process chat message: {str(e)}"
            )
            # Note: Queue processing continues even if this message fails

    async def _notify_message_queued(self, session_id: str, queue_position: int) -> None:
        """
        Notify frontend that message was successfully queued.

        Args:
            session_id: Session identifier
            queue_position: Position in queue (0 = processing now, 1+ = waiting)
        """
        try:
            queue_msg = create_message(
                MessageType.MESSAGE_QUEUED,
                session_id=session_id,
                payload={
                    "position": queue_position,
                    "queue_size": self.queue_manager.get_queue_size(session_id),
                    "timestamp": datetime.now().isoformat()
                }
            )
            await self.connection_manager.send_json(session_id, queue_msg.model_dump())
        except Exception as e:
            logger.error(f"Failed to send queue notification: {e}")


class UserInterruptHandler(MessageHandler):
    """
    Handle user interrupt requests (ESC key pressed).

    Purpose: Process ESC key presses from frontend to interrupt ongoing LLM reasoning
    or tool execution. Sets the interrupt flag in the context manager to gracefully
    stop the current operation.
    """

    async def handle(self, session_id: str, message: BaseWebSocketMessage) -> None:
        if message.type == MessageType.USER_INTERRUPT:
            try:
                print(f"[UserInterruptHandler] Processing USER_INTERRUPT from session {session_id}", flush=True)

                # Set interrupt flag via StatusMonitor
                from backend.infrastructure.monitoring import get_status_monitor
                status_monitor = get_status_monitor(session_id)
                status_monitor.set_user_interrupted()
                print(f"[UserInterruptHandler] Set user_interrupted flag via StatusMonitor for session {session_id}", flush=True)

            except Exception as e:
                logger.error(f"Error processing user interrupt: {e}")
                await self.send_error(
                    session_id,
                    "INTERRUPT_PROCESSING_ERROR",
                    f"Failed to process user interrupt: {str(e)}"
                )


class ToolConfirmationHandler(MessageHandler):
    """
    Handle tool confirmation responses from frontend.

    Purpose: Process user responses to tool confirmation requests (bash, edit, write, etc.).
    When user approves/rejects a tool operation in the frontend, this handler
    routes the response to the ToolConfirmationService to unblock waiting tools.

    Supports three outcomes:
    - approve: Execute the tool
    - reject: Stop execution, save context for next message injection
    - reject_and_tell: Continue execution with user's instruction injected
    """

    async def handle(self, session_id: str, message: BaseWebSocketMessage) -> None:
        if message.type == MessageType.TOOL_CONFIRMATION_RESPONSE:
            try:
                print(f"[ToolConfirmationHandler] Processing TOOL_CONFIRMATION_RESPONSE from session {session_id}", flush=True)

                # Extract confirmation data from message
                tool_call_id = getattr(message, 'tool_call_id', None)
                outcome = getattr(message, 'outcome', None)
                user_message = getattr(message, 'user_message', None)
                approved = getattr(message, 'approved', None)  # Legacy field

                print(f"[ToolConfirmationHandler] tool_call_id={tool_call_id}, session_id={session_id}, outcome={outcome}, approved={approved}", flush=True)
                if user_message:
                    print(f"[ToolConfirmationHandler] user_message={user_message}", flush=True)

                if not tool_call_id:
                    logger.warning(f"Missing tool_call_id in TOOL_CONFIRMATION_RESPONSE from session {session_id}")
                    return

                # Get confirmation service and handle response
                from backend.application.services.notifications.tool_confirmation_service import get_tool_confirmation_service
                confirmation_service = get_tool_confirmation_service()

                if confirmation_service:
                    # Handle the confirmation response (supports both outcome and legacy approved)
                    handled = confirmation_service.handle_confirmation_response(
                        tool_call_id=tool_call_id,
                        outcome=outcome,
                        user_message=user_message,
                        approved=approved,  # Legacy fallback
                    )

                    if handled:
                        print(f"[ToolConfirmationHandler] Successfully processed tool call {tool_call_id} for session {session_id}", flush=True)
                    else:
                        logger.warning(f"Confirmation service could not handle tool call {tool_call_id} for session {session_id}")
                        await self.send_error(
                            session_id,
                            "CONFIRMATION_NOT_FOUND",
                            f"No active confirmation for session: {session_id}"
                        )
                else:
                    logger.error("Tool confirmation service not available")
                    await self.send_error(
                        session_id,
                        "SERVICE_UNAVAILABLE",
                        "Tool confirmation service is not available"
                    )

            except Exception as e:
                logger.error(f"Error processing tool confirmation response: {e}")
                await self.send_error(
                    session_id,
                    "CONFIRMATION_PROCESSING_ERROR",
                    f"Failed to process confirmation response: {str(e)}"
                )


class MoveToBackgroundHandler(MessageHandler):
    """
    Handle move-to-background requests (ctrl+b pressed).

    Purpose: Process ctrl+b key presses from frontend to move a running
    foreground process to background execution. Supports both bash commands
    and PFC simulation tasks.

    The process continues running but the tool call returns immediately,
    allowing the user to continue interacting.
    """

    async def handle(self, session_id: str, message: BaseWebSocketMessage) -> None:
        if message.type == MessageType.MOVE_TO_BACKGROUND:
            try:
                print(f"[MoveToBackgroundHandler] Processing MOVE_TO_BACKGROUND from session {session_id}", flush=True)

                # Try bash first, then PFC
                bash_service = get_bash_execution_service()
                pfc_service = get_pfc_execution_service()

                bash_success = bash_service.request_move_to_background(session_id)
                pfc_success = pfc_service.request_move_to_background(session_id)

                if bash_success:
                    print(f"[MoveToBackgroundHandler] Successfully signaled move-to-background for bash process in session {session_id}", flush=True)
                elif pfc_success:
                    print(f"[MoveToBackgroundHandler] Successfully signaled move-to-background for PFC task in session {session_id}", flush=True)
                else:
                    logger.warning(f"No foreground process found for session {session_id}")
                    await self.send_error(
                        session_id,
                        "NO_FOREGROUND_PROCESS",
                        "No foreground process is currently running"
                    )

            except Exception as e:
                logger.error(f"Error processing move-to-background request: {e}")
                await self.send_error(
                    session_id,
                    "MOVE_TO_BACKGROUND_ERROR",
                    f"Failed to move process to background: {str(e)}"
                )

