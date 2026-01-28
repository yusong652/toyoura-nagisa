"""
Title Service - Business logic for session title generation.

This service handles automatic title generation for chat sessions
based on conversation context.
"""
from typing import Dict, Any, Optional, List
from backend.infrastructure.storage.session_manager import (
    get_all_sessions,
    update_session_title,
    get_latest_n_messages,
)
from backend.domain.models.messages import BaseMessage, UserMessage
from backend.domain.models.message_factory import extract_text_from_message
from backend.infrastructure.llm.shared.constants import (
    DEFAULT_TITLE_GENERATION_SYSTEM_PROMPT,
    DEFAULT_TITLE_MAX_LENGTH,
)
from backend.infrastructure.llm.shared.utils.text_processing import parse_title_response


def _format_conversation_context(messages: List[BaseMessage]) -> str:
    conversation_parts = []
    for msg in messages:
        text = extract_text_from_message(msg)
        if not text or not text.strip():
            continue
        role_label = "User" if msg.role == "user" else "Assistant"
        conversation_parts.append(f"{role_label}: {text.strip()}")
    return "\n".join(conversation_parts)


def _build_title_user_message(conversation_context: str) -> UserMessage:
    return UserMessage(
        role="user",
        content=(
            "Please generate a concise title based on the following conversation:\n\n"
            f"{conversation_context}"
        ),
    )


async def _generate_title(llm_client: Any, latest_messages: List[BaseMessage]) -> Optional[str]:
    conversation_context = _format_conversation_context(latest_messages)
    if not conversation_context:
        return None

    user_message = _build_title_user_message(conversation_context)
    context_contents = llm_client.format_messages([user_message])
    api_config = llm_client.build_api_config(DEFAULT_TITLE_GENERATION_SYSTEM_PROMPT)

    response = await llm_client.call_api_with_context(
        context_contents=context_contents,
        api_config=api_config,
        thinking_level="default",  # No thinking for title generation
    )

    title_response_text = llm_client.extract_text(response)
    return parse_title_response(title_response_text, max_length=DEFAULT_TITLE_MAX_LENGTH)


class TitleService:
    """
    Service layer for session title generation operations.

    Provides intelligent title generation based on conversation history,
    identifying key topics and generating concise, descriptive titles.
    """

    def should_generate_title(self, session_id: str) -> bool:
        """
        Determine if title generation is needed.

        Title generation is triggered only if:
        1. Current session has a default title (starts with 'New Chat' or contains 'New Conversation')
        2. Latest two messages are valid conversational turns (non-tool)

        Args:
            session_id: Session UUID to check

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
        latest_messages = list(get_latest_n_messages(session_id, 2))
        return has_default_title and len(latest_messages) == 2


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
            if self.should_generate_title(session_id):
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
            # Generate title from latest conversation
            latest_messages = list(get_latest_n_messages(session_id, 2))
            if len(latest_messages) < 2:
                return {
                    "error": "Not enough recent messages for title generation",
                    "success": False
                }

            new_title = await _generate_title(llm_client, latest_messages)

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
