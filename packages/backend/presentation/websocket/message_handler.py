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
from backend.presentation.websocket.messages.user_shell import UserShellResultMessage
from backend.presentation.websocket.messages.user_pfc_console import UserPfcConsoleResultMessage
from backend.application.services.shell import get_bash_execution_service
from backend.application.services.pfc import get_pfc_execution_service
from backend.application.services.pfc.pfc_console_service import (
    get_pfc_console_service,
    PfcConsoleExecutionResult,
    PfcConsoleMoveToBackgroundRequest,
)

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

        # Initialize user shell handler (! prefix commands)
        user_shell_handler = UserShellHandler(connection_manager)

        # Initialize user PFC console handler (> prefix commands)
        user_pfc_console_handler = UserPfcConsoleHandler(connection_manager)

        self.handlers: Dict[MessageType, MessageHandler] = {
            MessageType.HEARTBEAT_ACK: heartbeat_handler,
            MessageType.LOCATION_RESPONSE: location_handler,  # Only handle responses from frontend
            MessageType.CHAT_MESSAGE: chat_handler,
            MessageType.TOOL_CONFIRMATION_RESPONSE: tool_confirmation_handler,
            MessageType.USER_INTERRUPT: user_interrupt_handler,
            MessageType.MOVE_TO_BACKGROUND: move_to_background_handler,
            MessageType.USER_SHELL_EXECUTE: user_shell_handler,
            MessageType.USER_PFC_CONSOLE_EXECUTE: user_pfc_console_handler,
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


class UserShellHandler(MessageHandler):
    """
    Handle user shell command execution requests (! prefix commands).

    Purpose: Execute shell commands initiated by user via CLI `!` prefix.
    Uses foreground execution with Ctrl+B backgrounding support.

    Flow:
    1. Frontend sends USER_SHELL_EXECUTE with command
    2. Backend starts foreground execution (registered for Ctrl+B)
    3. Handler returns immediately, wait runs in background task
    4. If Ctrl+B: adopt to background, notify frontend
    5. If completed: send USER_SHELL_RESULT with output

    Architecture:
    - Uses asyncio.create_task() to avoid blocking the WebSocket message loop
    - This allows MOVE_TO_BACKGROUND messages to be processed during execution
    - Task tracking enables cleanup when WebSocket disconnects
    """

    # Cache ShellService instances per session+profile
    _shell_services: dict = {}

    # Track waiting tasks per session for cleanup on disconnect
    _waiting_tasks: dict = {}  # session_id -> asyncio.Task

    async def _get_shell_service(self, session_id: str, agent_profile: str):
        """Get or create ShellService for a session and profile."""
        from backend.application.services.shell.shell_service import ShellService
        from backend.shared.utils.workspace import get_workspace_for_profile

        cache_key = (session_id, agent_profile)
        if cache_key not in self._shell_services:
            workspace_root = await get_workspace_for_profile(agent_profile, session_id)
            self._shell_services[cache_key] = ShellService(workspace_root=workspace_root)
        return self._shell_services[cache_key]

    async def handle(self, session_id: str, message: BaseWebSocketMessage) -> None:
        if message.type != MessageType.USER_SHELL_EXECUTE:
            return

        command = getattr(message, 'command', '')
        agent_profile = getattr(message, 'agent_profile', 'general')
        timeout_ms = getattr(message, 'timeout_ms', None)

        logger.info(f"[UserShellHandler] Executing command for session {session_id}: {command[:50]}...")

        try:
            service = await self._get_shell_service(session_id, agent_profile)

            # Start foreground execution (supports Ctrl+B)
            handle, immediate_result, actual_command, has_cd = await service.start_foreground(
                command=command,
                timeout_ms=timeout_ms,
            )

            # Pure cd command - no process needed, result is immediate
            if handle is None and immediate_result is not None:
                result, context = immediate_result
                await self._send_result(session_id, service, command, result, context)
                return

            # Register for Ctrl+B signal handling
            from backend.infrastructure.shell.foreground_task_registry import get_foreground_task_registry

            registry = get_foreground_task_registry()
            registry.register(session_id, handle)

            # Run wait in background task to avoid blocking message loop
            # This allows MOVE_TO_BACKGROUND messages to be processed while waiting
            import asyncio

            task = asyncio.create_task(
                self._wait_and_send_result(
                    session_id=session_id,
                    service=service,
                    handle=handle,
                    command=command,
                    has_cd=has_cd,
                    agent_profile=agent_profile,
                    registry=registry,
                )
            )
            self._waiting_tasks[session_id] = task

            logger.info(f"[UserShellHandler] Command scheduled in background task: {command[:50]}...")

        except Exception as e:
            logger.error(f"[UserShellHandler] Error starting command: {e}")
            await self._send_error(session_id, agent_profile, str(e))

    async def _wait_and_send_result(
        self,
        session_id: str,
        service,
        handle,
        command: str,
        has_cd: bool,
        agent_profile: str,
        registry,
    ) -> None:
        """Background task: wait for shell command completion and send result.

        This runs in a separate task to avoid blocking the WebSocket message loop,
        allowing Ctrl+B (MOVE_TO_BACKGROUND) messages to be processed during execution.
        """
        import asyncio
        from backend.infrastructure.shell.executor import MoveToBackgroundRequest

        try:
            wait_result = await handle.wait()

            # Handle Ctrl+B: user wants to background the process
            if isinstance(wait_result, MoveToBackgroundRequest):
                from backend.infrastructure.shell.background_process_manager import get_process_manager

                process_manager = get_process_manager()
                process_id = process_manager.adopt_process(
                    session_id=session_id,
                    handle=wait_result.handle,
                    description=f"User shell: {command[:50]}",
                )

                logger.info(f"[UserShellHandler] Command moved to background: {process_id}")

                # Send backgrounded result
                result_msg = UserShellResultMessage(
                    type=MessageType.USER_SHELL_RESULT,
                    session_id=session_id,
                    stdout=f"Command moved to background with ID: {process_id}",
                    stderr="",
                    exit_code=0,
                    cwd=service.get_cwd(),
                    context="",
                    success=True,
                    backgrounded=True,
                    process_id=process_id,
                )
                await self.connection_manager.send_json(session_id, result_msg.model_dump())
                return

            # Normal completion - process result
            exec_result = wait_result
            result, context = service.process_foreground_result(
                result=exec_result,
                original_command=command,
                has_cd=has_cd,
            )

            await self._send_result(session_id, service, command, result, context)

        except asyncio.CancelledError:
            logger.info(f"[UserShellHandler] Background task cancelled for session {session_id}")
            # Don't send error on cancellation (session likely disconnected)
            raise
        except Exception as e:
            logger.error(f"[UserShellHandler] Error in background wait: {e}")
            await self._send_error(session_id, agent_profile, str(e))
        finally:
            # Always unregister from Ctrl+B handling
            registry.unregister(session_id)
            # Remove from tracking
            if session_id in self._waiting_tasks:
                del self._waiting_tasks[session_id]

    def cleanup_session(self, session_id: str) -> None:
        """Clean up background tasks for a session.

        Called when WebSocket disconnects to cancel any pending shell tasks.
        This prevents orphaned tasks from trying to send to disconnected sessions.
        """
        if session_id in self._waiting_tasks:
            task = self._waiting_tasks[session_id]
            if not task.done():
                task.cancel()
                logger.info(f"[UserShellHandler] Cancelled waiting task for session {session_id}")
            del self._waiting_tasks[session_id]

        # Also clean up shell service cache for this session
        keys_to_remove = [k for k in self._shell_services if k[0] == session_id]
        for key in keys_to_remove:
            del self._shell_services[key]

    async def _send_result(self, session_id: str, service, command: str, result, context: str):
        """Send successful execution result to frontend."""
        from backend.infrastructure.monitoring.status_monitor import get_status_monitor

        # Store context for LLM injection (intent awareness)
        status_monitor = get_status_monitor(session_id)
        status_monitor.add_user_bash_context(
            command=command,
            stdout=result.stdout,
            stderr=result.stderr,
        )

        result_msg = UserShellResultMessage(
            type=MessageType.USER_SHELL_RESULT,
            session_id=session_id,
            stdout=result.stdout,
            stderr=result.stderr,
            exit_code=result.exit_code,
            cwd=service.get_cwd(),
            context=context,
            success=True,
        )
        await self.connection_manager.send_json(session_id, result_msg.model_dump())

        logger.info(f"[UserShellHandler] Command completed with exit code {result.exit_code}")

    async def _send_error(self, session_id: str, agent_profile: str, error: str):
        """Send error result to frontend."""
        try:
            service = await self._get_shell_service(session_id, agent_profile)
            cwd = service.get_cwd()
        except Exception:
            cwd = ""

        result_msg = UserShellResultMessage(
            type=MessageType.USER_SHELL_RESULT,
            session_id=session_id,
            stdout="",
            stderr=error,
            exit_code=1,
            cwd=cwd,
            context="",
            success=False,
            error_message=error,
        )
        await self.connection_manager.send_json(session_id, result_msg.model_dump())


class UserPfcConsoleHandler(MessageHandler):
    """
    Handle user PFC console command execution requests (> prefix commands).

    Purpose: Execute PFC Python commands initiated by user via CLI `>` prefix.
    Uses foreground execution with Ctrl+B backgrounding support, aligned with
    pfc_execute_task tool flow.

    Flow:
    1. Frontend sends USER_PFC_CONSOLE_EXECUTE with code
    2. Backend starts foreground execution via PfcConsoleService
    3. Handler returns immediately, wait runs in background task
    4. If Ctrl+B: move to background, notify frontend
    5. If completed: send USER_PFC_CONSOLE_RESULT with output

    Architecture:
    - Uses asyncio.create_task() to avoid blocking the WebSocket message loop
    - Reuses same ForegroundHandle/Registry/NotificationService as pfc_execute_task
    - Ctrl+B handled by MoveToBackgroundHandler via get_pfc_execution_service
    """

    # Track waiting tasks per session for cleanup on disconnect
    _waiting_tasks: dict = {}  # session_id -> asyncio.Task

    async def handle(self, session_id: str, message: BaseWebSocketMessage) -> None:
        if message.type != MessageType.USER_PFC_CONSOLE_EXECUTE:
            return

        code = getattr(message, 'code', '')
        agent_profile = getattr(message, 'agent_profile', 'pfc_expert')
        timeout_ms = getattr(message, 'timeout_ms', None)

        logger.info(f"[UserPfcConsoleHandler] Executing code for session {session_id}: {code[:50]}...")

        # Skip empty code
        if not code.strip():
            await self._send_empty_result(session_id)
            return

        try:
            # Get workspace for profile
            from backend.shared.utils.workspace import get_workspace_for_profile
            workspace_path = await get_workspace_for_profile(agent_profile, session_id)

            # Get console service
            service = get_pfc_console_service(workspace_path, session_id)

            # Run execution in background task to avoid blocking message loop
            # This allows MOVE_TO_BACKGROUND messages to be processed while waiting
            task = asyncio.create_task(
                self._execute_and_send_result(
                    session_id=session_id,
                    service=service,
                    code=code,
                    timeout_ms=timeout_ms,
                )
            )
            self._waiting_tasks[session_id] = task

            logger.info(f"[UserPfcConsoleHandler] Code execution scheduled in background task")

        except Exception as e:
            logger.error(f"[UserPfcConsoleHandler] Error starting execution: {e}")
            await self._send_error(session_id, str(e))

    async def _execute_and_send_result(
        self,
        session_id: str,
        service,
        code: str,
        timeout_ms: Optional[int],
    ) -> None:
        """Background task: execute PFC code and send result.

        This runs in a separate task to avoid blocking the WebSocket message loop,
        allowing Ctrl+B (MOVE_TO_BACKGROUND) messages to be processed during execution.
        """
        try:
            # Execute with foreground support (asyncio.wait inside)
            wait_result, task_id, error = await service.execute_foreground(
                code=code,
                timeout_ms=timeout_ms,
            )

            # Early error (connection failed, etc.)
            if error:
                await self._send_error(session_id, error, task_id=task_id)
                return

            # Empty code (shouldn't happen, checked above)
            if wait_result is None:
                await self._send_empty_result(session_id)
                return

            # Handle Ctrl+B: user wants to background the execution
            if isinstance(wait_result, PfcConsoleMoveToBackgroundRequest):
                context = await service.process_backgrounded(code, task_id, wait_result)

                # Store context for LLM injection
                from backend.infrastructure.monitoring.status_monitor import get_status_monitor
                status_monitor = get_status_monitor(session_id)
                status_monitor.add_user_pfc_python_context(
                    code=code,
                    task_id=task_id,
                    output=f"Execution backgrounded. Task ID: {task_id}",
                    error="",
                )

                if wait_result.reason == "user_request":
                    output = f"Code execution backgrounded by user. Task ID: {task_id}"
                else:
                    output = f"Code execution timed out, continuing in background. Task ID: {task_id}"

                result_msg = UserPfcConsoleResultMessage(
                    type=MessageType.USER_PFC_CONSOLE_RESULT,
                    session_id=session_id,
                    task_id=task_id,
                    output=output,
                    context=context,
                    success=True,
                    backgrounded=True,
                    connected=True,
                )
                await self.connection_manager.send_json(session_id, result_msg.model_dump())

                logger.info(f"[UserPfcConsoleHandler] Execution moved to background: {task_id}")
                return

            # Normal completion
            exec_result: PfcConsoleExecutionResult = wait_result
            context = service.process_completion(code, exec_result)

            # Store context for LLM injection
            from backend.infrastructure.monitoring.status_monitor import get_status_monitor
            status_monitor = get_status_monitor(session_id)
            status_monitor.add_user_pfc_python_context(
                code=code,
                task_id=exec_result.task_id,
                output=exec_result.output,
                error=exec_result.error or "",
            )

            result_msg = UserPfcConsoleResultMessage(
                type=MessageType.USER_PFC_CONSOLE_RESULT,
                session_id=session_id,
                task_id=exec_result.task_id,
                output=exec_result.output,
                error=exec_result.error,
                result=exec_result.result,
                elapsed_time=exec_result.elapsed_time,
                context=context,
                success=(exec_result.status == "completed"),
                connected=True,
            )
            await self.connection_manager.send_json(session_id, result_msg.model_dump())

            logger.info(f"[UserPfcConsoleHandler] Execution completed: {exec_result.status}")

        except asyncio.CancelledError:
            logger.info(f"[UserPfcConsoleHandler] Background task cancelled for session {session_id}")
            raise
        except Exception as e:
            logger.error(f"[UserPfcConsoleHandler] Error in background execution: {e}")
            await self._send_error(session_id, str(e))
        finally:
            # Remove from tracking
            if session_id in self._waiting_tasks:
                del self._waiting_tasks[session_id]

    def cleanup_session(self, session_id: str) -> None:
        """Clean up background tasks for a session.

        Called when WebSocket disconnects to cancel any pending PFC tasks.
        """
        if session_id in self._waiting_tasks:
            task = self._waiting_tasks[session_id]
            if not task.done():
                task.cancel()
                logger.info(f"[UserPfcConsoleHandler] Cancelled waiting task for session {session_id}")
            del self._waiting_tasks[session_id]

    async def _send_empty_result(self, session_id: str):
        """Send empty result for empty code."""
        result_msg = UserPfcConsoleResultMessage(
            type=MessageType.USER_PFC_CONSOLE_RESULT,
            session_id=session_id,
            output="",
            context="",
            success=True,
            connected=True,
        )
        await self.connection_manager.send_json(session_id, result_msg.model_dump())

    async def _send_error(self, session_id: str, error: str, task_id: Optional[str] = None):
        """Send error result to frontend."""
        result_msg = UserPfcConsoleResultMessage(
            type=MessageType.USER_PFC_CONSOLE_RESULT,
            session_id=session_id,
            task_id=task_id,
            output="",
            error=error,
            context="",
            success=False,
            error_message=error,
            connected=False,
        )
        await self.connection_manager.send_json(session_id, result_msg.model_dump())

