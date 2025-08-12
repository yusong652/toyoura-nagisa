"""
Content processing pipeline for LLM responses.

This module handles the processing of final LLM responses,
including message saving, keyword extraction, and TTS preparation.
"""

import json
from typing import Dict, Any, AsyncGenerator, Optional
from backend.domain.models.messages import BaseMessage
from backend.domain.models.message_factory import message_factory
from backend.infrastructure.storage.session_manager import load_all_message_history
from backend.shared.utils.helpers import process_ai_text_message
# Import will be resolved at runtime - avoid circular import
# from backend.presentation.streaming.tts_processor import process_tts_pipeline


async def process_content_pipeline(
    final_message: BaseMessage,
    session_id: str,
    tts_engine,
    request_id: str,
    execution_metadata: Optional[Dict[str, Any]] = None
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Content processing pipeline for final LLM responses.
    
    This pipeline handles:
    1. Content extraction from structured messages
    2. Message persistence to conversation history
    3. Keyword extraction for emotional expressions
    4. TTS processing coordination
    
    Args:
        final_message: Final LLM response message
        session_id: Current session ID
        tts_engine: TTS engine instance
        request_id: Request ID for debugging
        execution_metadata: Optional execution metadata with keywords
    
    Yields:
        Content processing results including message IDs, keywords, and TTS chunks
    """
    if not hasattr(final_message, 'content'):
        return
    
    content = final_message.content
    
    # Extract text content for TTS (excluding thinking blocks)
    text_content = ""
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict) and item.get('type') == 'text':
                text_content += item.get('text', '')
            # thinking content is saved to history but not used for TTS
    else:
        text_content = str(content)
    
    # Load conversation history for message processing
    loaded_history = load_all_message_history(session_id)
    history_msgs = [message_factory(msg) if isinstance(msg, dict) else msg for msg in loaded_history]
    
    # Extract keywords from metadata or parse from text
    extracted_keyword = None
    if execution_metadata and 'keyword' in execution_metadata:
        extracted_keyword = execution_metadata['keyword']
    else:
        # Fallback: parse emotional keywords from text content
        from backend.shared.utils.text_parser import parse_llm_output
        _, extracted_keyword = parse_llm_output(text_content)
    
    # Save complete content including thinking blocks to conversation history
    ai_msg_id, processed_content = process_ai_text_message(
        content,  # Save complete content including thinking
        extracted_keyword,  # Use extracted keywords
        history_msgs,
        session_id
    )
    
    # Send message ID for client tracking
    yield f"data: {json.dumps({'message_id': ai_msg_id})}\n\n"
    
    # Send emotional keywords if available
    if extracted_keyword:
        yield f"data: {json.dumps({'keyword': extracted_keyword})}\n\n"
    
    # Process TTS pipeline if text content is available
    if text_content.strip():
        # Dynamic import to avoid circular dependency
        from backend.presentation.streaming.tts_processor import process_tts_pipeline
        async for chunk in process_tts_pipeline(text_content, tts_engine):
            yield chunk
    else:
        # Send empty text chunk for consistency when only keywords are present
        yield f"data: {json.dumps({'text': '', 'audio': None, 'index': 0})}\n\n"