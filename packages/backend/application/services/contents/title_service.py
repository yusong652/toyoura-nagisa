"""
Title Service - Business logic for session title generation.

This service handles automatic title generation for chat sessions
based on conversation context.
"""
import asyncio
from typing import Dict, Any, Optional, List
from backend.infrastructure.storage.session_manager import (
    get_all_sessions,
    update_session_title,
    load_history,
    load_all_message_history
)
from backend.domain.models.message_factory import message_factory
from backend.infrastructure.llm.content_generators.factory import ContentGeneratorFactory


def trigger_title_generation(session_id: str, llm_client: Any) -> None:
    """
    Trigger background title generation for a session.

    This is a fire-and-forget convenience function that schedules
    title generation as a background task. Safe to call from any
    async context without awaiting.

    Args:
        session_id: Session ID to generate title for
        llm_client: LLM client instance for title generation
    """
    title_service = TitleService()
    asyncio.create_task(
        title_service.try_generate_title_if_needed_async(session_id, llm_client)
    )


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
        has_text_assistant = any(self._is_assistant_with_text_content(msg) for msg in history_msgs)
        return has_default_title and has_text_assistant

    def _is_assistant_with_text_content(self, msg) -> bool:
        """
        Check if message is an assistant message with text content.

        This method filters for assistant messages (ignoring user messages)
        and checks if they contain at least one text block with actual content.
        Messages with tool_use blocks are accepted if they also have text.

        This allows title generation to happen immediately after the first
        meaningful response, even if it also includes tool calls.

        Args:
            msg: Message object to check (can be user or assistant)

        Returns:
            bool: True if message is assistant with text content, False otherwise
        """
        # Only check assistant messages, skip user messages
        if getattr(msg, "role", None) != "assistant":
            return False

        # Check if content has at least one text block with actual text
        content = getattr(msg, "content", None)

        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    # Accept if has text block with non-empty content
                    if block.get('type') == 'text' and block.get('text', '').strip():
                        return True
        elif isinstance(content, str) and content.strip():
            # Handle string content (legacy format)
            return True

        return False

    def _is_pure_text_user(self, msg) -> bool:
        """
        Determine if user message is pure text (non-tool result message).

        A pure text user message does not contain tool_result blocks in its content.
        Tool result blocks are system-generated responses from tool execution.

        Args:
            msg: Message object to check

        Returns:
            bool: True if message is pure text user message, False otherwise
        """
        if getattr(msg, "role", None) != "user":
            return False

        # Check content for tool_result blocks
        content = getattr(msg, "content", None)
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get('type') == 'tool_result':
                    return False

        return True

    async def _generate_title_from_history(self, session_id: str, llm_client) -> Optional[str]:
        """
        Core logic: Find latest user and pure text assistant messages and generate title.

        Searches backward from end of history to find most recent pair of non-tool messages,
        then uses LLM to generate an appropriate session title.

        Filters out both:
        - Assistant messages with tool_use blocks (tool calls)
        - User messages with tool_result blocks (tool execution results)

        Args:
            session_id: Session UUID to generate title for
            llm_client: LLM client with generate_title_from_messages method

        Returns:
            Optional[str]: Generated title, or None if no suitable message pair found
        """
        history = load_history(session_id)
        history_msgs = [message_factory(msg) if isinstance(msg, dict) else msg for msg in history]

        # Traverse backward to find most recent pair of pure conversation messages
        latest_user_msg = None
        latest_assistant_msg = None

        for msg in reversed(history_msgs):
            role = getattr(msg, 'role', None)

            # Find latest pure text user message (not tool result)
            if not latest_user_msg and role == 'user':
                if self._is_pure_text_user(msg):
                    latest_user_msg = msg

            # Find latest assistant message with text content (can have tool calls)
            # Changed from elif to if - both checks should be independent
            if not latest_assistant_msg and role == 'assistant':
                if self._is_assistant_with_text_content(msg):
                    latest_assistant_msg = msg

            # Stop searching if found most recent pair of messages
            if latest_user_msg and latest_assistant_msg:
                break

        if not latest_user_msg or not latest_assistant_msg:
            return None

        # Create a list of latest messages for title generation
        latest_messages = [latest_user_msg, latest_assistant_msg]

        # Use ContentGeneratorFactory for title generation
        title = await ContentGeneratorFactory.generate_title_from_messages(
            llm_client,
            latest_messages
        )
        return title

    async def try_generate_title_if_needed_async(
        self,
        session_id: str,
        llm_client
    ) -> None:
        """
        Asynchronously attempt to generate title when needed.

        This method checks if title generation is needed and triggers it if appropriate.
        Should be called after message completion in the presentation layer.

        Args:
            session_id: Session ID to generate title for
            llm_client: LLM client instance for title generation
        """
        try:
            # Load history and check if title generation is needed
            loaded_history = load_all_message_history(session_id)
            history_msgs = [message_factory(msg) if isinstance(msg, dict) else msg for msg in loaded_history]

            if self.should_generate_title(session_id, history_msgs):
                # Generate title
                result = await self.generate_title_for_session(session_id, llm_client)

                if result and result.get("success") and result.get("title"):
                    # Send title update via WebSocket
                    from backend.infrastructure.websocket.notification_service import WebSocketNotificationService
                    await WebSocketNotificationService.send_title_update(session_id, result["title"])
                    print(f"[INFO] Title auto-generated for session {session_id}: {result['title']}")

        except Exception as e:
            # Title generation failure should not affect main flow
            print(f"[WARNING] Background title generation failed for session {session_id}: {e}")

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
            import traceback
            print(f"[ERROR] Title generation error: {e}")
            print(f"[ERROR] Traceback:")
            traceback.print_exc()
            return {
                "error": str(e),
                "success": False
            }
