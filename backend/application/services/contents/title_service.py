"""
Title Service - Business logic for session title generation.

This service handles automatic title generation for chat sessions
based on conversation context.
"""
from typing import Dict, Any, Optional, List
from backend.infrastructure.storage.session_manager import (
    get_all_sessions,
    update_session_title,
    load_history
)
from backend.domain.models.message_factory import message_factory


class TitleService:
    """
    Service layer for session title generation operations.

    Provides intelligent title generation based on conversation history,
    identifying key topics and generating concise, descriptive titles.
    """

    def should_generate_title(self, session_id: str, history_msgs: List) -> bool:
        """
        Determine if title generation is needed.

        Title generation is triggered only if:
        1. Current session has a default title (starts with 'New Chat' or contains 'New Conversation')
        2. History contains at least one pure text assistant message (non-tool message)

        Args:
            session_id: Session UUID to check
            history_msgs: List of message objects in the session

        Returns:
            bool: True if title should be generated, False otherwise
        """
        sessions = get_all_sessions()
        current_session = next((s for s in sessions if s['id'] == session_id), None)
        has_default_title = (
            current_session is not None and
            (
                current_session.get('name', '').startswith('New Chat')
                or 'New Conversation' in current_session.get('name', '')
            )
        )
        has_pure_text_assistant = any(self._is_pure_text_assistant(msg) for msg in history_msgs)
        return has_default_title and has_pure_text_assistant

    def _is_pure_text_assistant(self, msg) -> bool:
        """
        Determine if assistant message is pure text (non-tool/function_call).

        A pure text assistant message has no tool_calls field or an empty tool_calls list.

        Args:
            msg: Message object to check

        Returns:
            bool: True if message is pure text assistant message, False otherwise
        """
        return (
            getattr(msg, "role", None) == "assistant"
            and not (getattr(msg, "tool_calls", None) or [])
        )

    async def _generate_title_from_history(self, session_id: str, llm_client) -> Optional[str]:
        """
        Core logic: Find latest user and pure text assistant messages and generate title.

        Searches backward from end of history to find most recent pair of non-tool messages,
        then uses LLM to generate an appropriate session title.

        Args:
            session_id: Session UUID to generate title for
            llm_client: LLM client with generate_title_from_messages method

        Returns:
            Optional[str]: Generated title, or None if no suitable message pair found
        """
        history = load_history(session_id)
        history_msgs = [message_factory(msg) if isinstance(msg, dict) else msg for msg in history]

        # Traverse backward to find most recent pair of non-tool messages
        latest_user_msg = None
        latest_assistant_msg = None

        for msg in reversed(history_msgs):
            if not latest_user_msg and getattr(msg, 'role', None) == 'user':
                latest_user_msg = msg
            elif not latest_assistant_msg and self._is_pure_text_assistant(msg):
                latest_assistant_msg = msg

            # Stop searching if found most recent pair of messages
            if latest_user_msg and latest_assistant_msg:
                break

        if not latest_user_msg or not latest_assistant_msg:
            return None

        # Create a list of latest messages for title generation
        latest_messages = [latest_user_msg, latest_assistant_msg]

        # Use LLM client's built-in title generation method directly
        title = await llm_client.generate_title_from_messages(latest_messages)
        return title

    async def generate_title_for_session(
        self,
        session_id: str,
        llm_client: Any
    ) -> Optional[Dict[str, Any]]:
        """
        Generate a descriptive title for a chat session.

        This operation:
        1. Validates the session exists
        2. Analyzes conversation history
        3. Uses LLM to generate appropriate title
        4. Updates session metadata

        Args:
            session_id: Session UUID to generate title for
            llm_client: LLM client for title generation

        Returns:
            Optional[Dict[str, Any]]: Title generation result or None if session not found:
                - session_id: str - Session that received new title
                - title: str - Generated title text
                - success: bool - Always True if successful
                - error: str - Error message if generation failed
        """
        # Validate session exists
        sessions = get_all_sessions()
        session = next((s for s in sessions if s['id'] == session_id), None)

        if not session:
            return None

        try:
            # Generate title using core logic
            new_title = await self._generate_title_from_history(session_id, llm_client)

            if new_title is None:
                return {
                    "error": "No valid user message or pure text assistant message found for title generation",
                    "success": False
                }

            if not new_title:
                return {
                    "error": "Title generation failed",
                    "success": False
                }

            # Update session title
            update_success = update_session_title(session_id, new_title)

            if not update_success:
                return {
                    "error": "Failed to update session title",
                    "success": False
                }

            return {
                "session_id": session_id,
                "title": new_title,
                "success": True
            }
        except Exception as e:
            print(f"[ERROR] Title generation error: {e}")
            return {
                "error": str(e),
                "success": False
            }
