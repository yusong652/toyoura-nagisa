"""
Content Processing Service - Application layer use case for LLM response handling.

This service orchestrates the complete content processing pipeline for LLM responses:
- Content extraction from structured messages
- Message persistence to conversation history
- Keyword extraction for emotional expressions

As an application service, it coordinates multiple infrastructure components
(MessageService, NotificationService) to implement the content processing
use case. WebSocket communication is delegated to presentation layer for proper
separation of concerns.
"""

from typing import Dict, Any, Optional, List
from backend.domain.models.messages import BaseMessage
from backend.application.session.message_service import MessageService
from backend.presentation.websocket.message_sender import send_message_create


async def process_content_pipeline(
    final_message: BaseMessage,  # AssistantMessage with List content
    session_id: str,
    message_id: Optional[str] = None  # Optional: use existing message ID from streaming
) -> None:
    """
    Content processing pipeline for final LLM responses.

    This pipeline handles:
    1. Content extraction from structured messages
    2. Message persistence to conversation history
    3. Keyword extraction for emotional expressions

    Args:
        final_message: Final LLM response message
        session_id: Current session ID
        message_id: Optional existing message ID (from streaming), if None creates new message

    Returns:
        None: All processing is handled via WebSocket communication
    """
    # Type assertion: AssistantMessage always has List content at this point
    # after being formatted by response processor
    content = final_message.content

    # Ensure content is List[Dict[str, Any]] for type safety
    if not isinstance(content, list):
        raise TypeError(f"Expected List content, got {type(content)}")

    content_list: List[Dict[str, Any]] = content  # Type-safe assignment

    # Extract text content for keyword parsing (excluding thinking blocks)
    text_content = ""
    for item in content_list:
        if isinstance(item, dict) and item.get('type') == 'text':
            text_content += item.get('text', '')

    # Extract emotional keywords from text content
    from backend.shared.utils.text_parser import parse_llm_output
    parsed_result = parse_llm_output(text_content)
    extracted_keyword = parsed_result['keyword']

    # Save or update message in conversation history
    if message_id:
        # Update existing message (created during streaming)
        MessageService.update_assistant_message(message_id, content_list, session_id)
        ai_msg_id = message_id
    else:
        # Create new message (non-streaming path)
        ai_msg_id = MessageService.save_assistant_message(
            content_list,  # Content is guaranteed to be List[Dict[str, Any]]
            session_id
        )
    
    # Send emotional keywords via WebSocket if available
    if extracted_keyword:
        from backend.application.notifications import get_emotion_notification_service
        emotion_service = get_emotion_notification_service()
        if emotion_service:
            await emotion_service.notify_emotion_keyword(session_id, extracted_keyword, ai_msg_id)
    
    # Send MESSAGE_CREATE only if message was not created during streaming
    if not message_id:
        await send_message_create(session_id, ai_msg_id)
