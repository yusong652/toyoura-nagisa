"""
Message Service - Business logic for message management.

This service handles message-related operations within chat sessions,
focusing on CRUD operations and message history management.
"""
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List
from backend.infrastructure.storage.session_manager import (
    get_all_sessions,
    delete_message as delete_message_from_storage,
    load_all_message_history,
    save_history
)
from backend.domain.models.message_factory import message_factory
from backend.domain.models.messages import AssistantMessage, UserMessage


class MessageService:
    """
    Service layer for message management operations.

    Provides high-level operations for managing individual messages
    within chat sessions, including creation, update, and deletion.
    """

    @staticmethod
    def save_user_message(
        content: List[Dict[str, Any]],
        session_id: str,
        timestamp: Optional[int] = None,
        message_id: Optional[str] = None
    ) -> UserMessage:
        """
        Save user message to history and return message object.

        Args:
            content: Structured content list from user input
            session_id: Session ID
            timestamp: Optional timestamp in milliseconds (Unix epoch)
            message_id: Optional message ID (use frontend-provided ID if available)

        Returns:
            UserMessage: Created user message object

        Example:
            >>> user_msg = MessageService.save_user_message(
            ...     content=[{"type": "text", "text": "Hello"}],
            ...     session_id="session-123",
            ...     timestamp=1699999999000,
            ...     message_id="msg-456"
            ... )
        """
        if not content:
            raise ValueError("Invalid message content")

        # Create user message object
        user_msg = UserMessage(
            role="user",
            content=content,
            timestamp=datetime.fromtimestamp(timestamp / 1000) if timestamp else datetime.now(),
            id=message_id or str(uuid.uuid4())
        )

        # Load history and append message
        history = load_all_message_history(session_id)
        history_msgs = [message_factory(msg) if isinstance(msg, dict) else msg for msg in history]
        history_msgs.append(user_msg)

        # Save updated history
        save_history(session_id, history_msgs)

        return user_msg

    @staticmethod
    def save_assistant_message(content: List[Dict[str, Any]], session_id: str) -> str:
        """
        Save AI assistant message to history and return message ID.

        Args:
            content: Structured content list from LLM response
            session_id: Session ID

        Returns:
            str: Generated message ID

        Example:
            >>> message_id = MessageService.save_assistant_message(
            ...     content=[{"type": "text", "text": "Hello"}],
            ...     session_id="session-123"
            ... )
        """
        message_id = str(uuid.uuid4())

        # Load complete history including images and other content
        history = load_all_message_history(session_id)
        history_msgs = [message_factory(msg) if isinstance(msg, dict) else msg for msg in history]

        # Create assistant message object - save content as-is
        assistant_message = AssistantMessage(
            role="assistant",
            content=content,
            id=message_id
        )

        # Add to history and save
        history_msgs.append(assistant_message)
        save_history(session_id, history_msgs)

        return message_id

    @staticmethod
    def update_assistant_message(message_id: str, content: List[Dict[str, Any]], session_id: str) -> None:
        """
        Update existing assistant message content in history.

        Used for updating streaming message placeholders with complete content
        after streaming finishes.

        Args:
            message_id: ID of the message to update
            content: New structured content list
            session_id: Session ID

        Example:
            >>> # After streaming completes, update the placeholder message
            >>> MessageService.update_assistant_message(
            ...     message_id="msg-123",
            ...     content=[
            ...         {"type": "thinking", "thinking": "Complete thinking..."},
            ...         {"type": "text", "text": "Complete response..."}
            ...     ],
            ...     session_id="session-456"
            ... )
        """
        # Load complete history
        history = load_all_message_history(session_id)
        history_msgs = [message_factory(msg) if isinstance(msg, dict) else msg for msg in history]

        # Find and update the message
        for msg in history_msgs:
            if hasattr(msg, 'id') and msg.id == message_id:
                # Update content (AssistantMessage has content attribute)
                if hasattr(msg, 'content'):
                    msg.content = content
                break

        # Save updated history
        save_history(session_id, history_msgs)

    @staticmethod
    def save_tool_result_message(
        tool_call_id: str,
        tool_name: str,
        tool_result: Dict[str, Any],
        session_id: str
    ) -> str:
        """
        Save tool execution result as a user message.

        Tool results are stored as UserMessage with tool_result content type,
        allowing LLM to understand tool execution context after server restart.

        Args:
            tool_call_id: ID of the tool call this result corresponds to
            tool_name: Name of the executed tool
            tool_result: Tool execution result (ToolResult format with llm_content)
            session_id: Current session ID

        Returns:
            str: Generated message ID

        Example:
            >>> tool_result = {
            ...     "status": "success",
            ...     "message": "File read successfully",
            ...     "llm_content": {"parts": [{"type": "text", "text": "content..."}]},
            ...     "data": {"file_path": "example.py"}
            ... }
            >>> MessageService.save_tool_result_message("call_1", "read_file", tool_result, session_id)
            'msg_uuid_123'
        """
        # Extract content from tool result
        llm_content = tool_result.get("llm_content", {})

        # Build tool_result content block
        tool_result_content = {
            "type": "tool_result",
            "tool_use_id": tool_call_id,
            "tool_name": tool_name,
            "content": llm_content,  # Use llm_content from ToolResult
            "is_error": tool_result.get("status") == "error",
            "data": tool_result.get("data"),  # Include data field for diff display
        }

        # Generate message ID
        message_id = str(uuid.uuid4())

        # Load history
        history = load_all_message_history(session_id)
        history_msgs = [message_factory(msg) if isinstance(msg, dict) else msg for msg in history]

        # Create user message with tool result
        message = UserMessage(
            role="user",
            content=[tool_result_content],
            id=message_id,
            timestamp=datetime.now()
        )

        # Add to history and save
        history_msgs.append(message)
        save_history(session_id, history_msgs)

        return message_id

    async def delete_message_async(
        self,
        session_id: str,
        message_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Delete a specific message from a chat session (async API endpoint version).

        This operation:
        1. Validates the session exists
        2. Deletes the message from storage
        3. Refreshes context manager to maintain consistency
        4. Returns operation status

        Args:
            session_id: Session UUID containing the message
            message_id: Unique identifier of the message to delete

        Returns:
            Optional[Dict[str, Any]]: Deletion result or None if not found:
                - session_id: str - Session containing the message
                - message_id: str - ID of deleted message
                - success: bool - Always True if successful
                - message: str - User-friendly status message
        """
        # Validate session exists
        sessions = get_all_sessions()
        session = next((s for s in sessions if s['id'] == session_id), None)

        if not session:
            return None

        # Delete the message from storage
        success = delete_message_from_storage(session_id, message_id)

        if not success:
            return None

        # Refresh context manager if it exists for this session
        # This ensures in-memory state (working_contents) stays synchronized with database
        try:
            from backend.infrastructure.llm.session_client import get_session_llm_client
            
            try:
                llm_client = get_session_llm_client(session_id)

                if llm_client and hasattr(llm_client, '_session_context_managers'):
                    # Check if context manager exists for this session (avoid creating new one)
                    if session_id in llm_client._session_context_managers:
                        context_manager = llm_client._session_context_managers[session_id]

                        # Reload history from storage and reinitialize context
                        from backend.infrastructure.storage.session_manager import load_history
                        history = load_history(session_id)
                        messages = [message_factory(msg) for msg in history]
                        context_manager.initialize_from_messages(messages)

                        print(f"[DEBUG] Refreshed context manager for session {session_id} after deleting message {message_id}")
            except Exception as e:
                print(f"[WARNING] Could not get LLM client for session {session_id}: {e}")

        except Exception as e:
            # Context refresh failure should not fail the delete operation
            # Just log the error - message is already deleted from storage
            print(f"[WARNING] Failed to refresh context manager after delete: {e}")

        return {
            "session_id": session_id,
            "message_id": message_id,
            "success": True,
            "message": "Message successfully deleted"
        }
