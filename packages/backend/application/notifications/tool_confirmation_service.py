"""
Tool Confirmation Service - DDD Application Layer

This service handles tool confirmation requests (bash, edit, write, etc.), coordinating between
MCP tools that need user approval and the WebSocket frontend for user interaction.

DDD Role: Application Service
- Manages confirmation request lifecycle with timeouts
- Coordinates between MCP tools and WebSocket presentation layer
- Provides async interface for tools to request and await confirmations
"""
import asyncio
import logging
from dataclasses import dataclass
from typing import Literal, Optional, Dict
from backend.infrastructure.websocket.connection_manager import ConnectionManager
from backend.presentation.websocket.message_types import MessageType, create_message

logger = logging.getLogger(__name__)


# Confirmation outcome types
ConfirmationOutcome = Literal["approve", "reject", "reject_and_tell"]


@dataclass
class ConfirmationResult:
    """Result of a tool confirmation request."""
    outcome: ConfirmationOutcome
    user_message: Optional[str] = None

    @property
    def approved(self) -> bool:
        """Legacy property for backward compatibility."""
        return self.outcome == "approve"

    @property
    def should_continue(self) -> bool:
        """Whether the agent should continue execution (approve or reject_and_tell)."""
        return self.outcome in ("approve", "reject_and_tell")


class ToolConfirmationService:
    """
    Application Service for Tool Confirmations.

    Manages the lifecycle of tool confirmation requests (bash, edit, write, etc.):
    - Sends confirmation requests to frontend via WebSocket
    - Tracks pending confirmations with timeout handling
    - Provides async interface for MCP tools to await user approval
    - Handles confirmation responses from frontend
    """

    def __init__(self, connection_manager: ConnectionManager):
        """
        Initialize tool confirmation service.

        Args:
            connection_manager: WebSocket connection manager instance
        """
        self.connection_manager = connection_manager
        self.active_confirmations: Dict[str, asyncio.Future[ConfirmationResult]] = {}  # tool_call_id -> Future

    async def request_confirmation(
        self,
        session_id: str,
        message_id: str,
        tool_call_id: str,
        tool_name: str,
        command: str,
        description: Optional[str] = None,
        timeout_seconds: Optional[int] = None,
        # New parameters for edit confirmation with diff display
        confirmation_type: Optional[str] = None,
        file_name: Optional[str] = None,
        file_path: Optional[str] = None,
        file_diff: Optional[str] = None,
        original_content: Optional[str] = None,
        new_content: Optional[str] = None
    ) -> ConfirmationResult:
        """
        Request user confirmation for a tool execution.

        Sends confirmation request to frontend and waits for response.

        Args:
            session_id: WebSocket session ID for the user
            message_id: ID of the message containing this tool call (for unique identification)
            tool_call_id: ID of the tool call (combined with message_id for matching)
            tool_name: Name of the tool requiring confirmation (bash, edit, write)
            command: The command/operation to execute
            description: Optional description of what the command does
            timeout_seconds: Timeout for waiting for confirmation (default None = infinite wait)
            confirmation_type: Type of confirmation ('edit', 'exec', 'info')
            file_name: For edit type - name of the file being modified
            file_path: For edit type - full path to the file
            file_diff: For edit type - unified diff content showing changes
            original_content: For edit type - original file content (empty for new files)
            new_content: For edit type - new content to be written

        Returns:
            ConfirmationResult with outcome (approve/reject/reject_and_tell) and optional user_message
        """

        # Create Future for this confirmation request (keyed by tool_call_id)
        confirmation_future: asyncio.Future[ConfirmationResult] = asyncio.Future()
        self.active_confirmations[tool_call_id] = confirmation_future

        try:
            # Build message kwargs (only include non-None values)
            msg_kwargs = {
                "message_id": message_id,
                "tool_call_id": tool_call_id,
                "tool_name": tool_name,
                "command": command,
                "session_id": session_id,
            }
            if description is not None:
                msg_kwargs["description"] = description
            if confirmation_type is not None:
                msg_kwargs["confirmation_type"] = confirmation_type
            if file_name is not None:
                msg_kwargs["file_name"] = file_name
            if file_path is not None:
                msg_kwargs["file_path"] = file_path
            if file_diff is not None:
                msg_kwargs["file_diff"] = file_diff
            if original_content is not None:
                msg_kwargs["original_content"] = original_content
            if new_content is not None:
                msg_kwargs["new_content"] = new_content

            # Send confirmation request to frontend (include message_id for unique identification)
            request_msg = create_message(
                MessageType.TOOL_CONFIRMATION_REQUEST,
                **msg_kwargs
            ).model_dump(mode="json", exclude_none=True)

            # Check if session is connected
            if await self.connection_manager.is_connected(session_id):
                await self.connection_manager.send_json(session_id, request_msg)
                logger.info(f"Sent tool confirmation request {tool_call_id} for session {session_id}, tool: {tool_name}, command: {command}")
            else:
                logger.warning(f"Session {session_id} not connected, auto-rejecting tool: {tool_name}")
                return ConfirmationResult(outcome="reject", user_message="Session not connected")

            # Wait for response (infinite wait if timeout_seconds is None)
            try:
                result = await asyncio.wait_for(
                    confirmation_future,
                    timeout=timeout_seconds
                )
                logger.info(f"Tool call {tool_call_id} confirmation result: {result.outcome}")
                if result.user_message:
                    logger.info(f"User message: {result.user_message}")
                return result
            except asyncio.TimeoutError:
                timeout_str = f"{timeout_seconds}s" if timeout_seconds else "unknown"
                logger.warning(f"Tool call {tool_call_id} confirmation timed out after {timeout_str}")
                return ConfirmationResult(outcome="reject", user_message="Confirmation timed out")

        finally:
            # Clean up the Future
            if tool_call_id in self.active_confirmations:
                del self.active_confirmations[tool_call_id]

    def handle_confirmation_response(
        self,
        tool_call_id: str,
        outcome: Optional[ConfirmationOutcome] = None,
        user_message: Optional[str] = None,
        approved: Optional[bool] = None,  # Legacy parameter for backward compatibility
    ) -> bool:
        """
        Handle confirmation response from frontend.

        Called by the WebSocket message handler when a TOOL_CONFIRMATION_RESPONSE is received.

        Args:
            tool_call_id: The tool call ID from the response
            outcome: The user's decision (approve/reject/reject_and_tell)
            user_message: Optional message from user
            approved: (Deprecated) Legacy parameter, use outcome instead

        Returns:
            bool: True if confirmation was found and processed, False otherwise
        """
        confirmation_future = self.active_confirmations.get(tool_call_id)

        if confirmation_future is None:
            logger.warning(f"Received response for unknown tool call: {tool_call_id}")
            return False

        if confirmation_future.done():
            logger.warning(f"Received duplicate response for tool call: {tool_call_id}")
            return False

        # Determine outcome (support both new outcome field and legacy approved field)
        if outcome is not None:
            final_outcome = outcome
        elif approved is not None:
            # Legacy fallback: convert approved bool to outcome
            final_outcome = "approve" if approved else "reject"
        else:
            # Default to reject if neither is provided
            final_outcome = "reject"

        # Create result and set it
        result = ConfirmationResult(outcome=final_outcome, user_message=user_message)
        confirmation_future.set_result(result)
        logger.info(f"Processed tool call {tool_call_id} confirmation: {final_outcome}")
        if user_message:
            logger.info(f"With user message: {user_message}")
        return True

def get_tool_confirmation_service() -> Optional[ToolConfirmationService]:
    """
    Get tool confirmation service from WebSocketHandler.

    Returns:
        ToolConfirmationService instance or None if not initialized

    Note:
        The service is initialized and managed by WebSocketHandler,
        avoiding global state and ensuring proper lifecycle management.
    """
    try:
        from backend.shared.utils.app_context import get_app

        app = get_app()
        if not app:
            logger.warning("FastAPI app not initialized")
            return None

        if not hasattr(app.state, 'websocket_handler'):
            logger.warning("WebSocket handler not found in app state")
            return None

        handler = app.state.websocket_handler
        if not hasattr(handler, 'tool_confirmation_service'):
            logger.warning("Tool confirmation service not found in WebSocket handler")
            return None

        return handler.tool_confirmation_service

    except Exception as e:
        logger.warning(f"Could not get tool confirmation service: {e}")
        return None
