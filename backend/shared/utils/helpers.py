import json
import base64
import asyncio
import uuid
from datetime import datetime
from backend.infrastructure.storage.session_manager import get_all_sessions, update_session_title, save_history, load_history
from backend.infrastructure.tts.base import BaseTTS
# Removed legacy title_generator import - now using LLM client methods directly
from backend.config import get_llm_settings
from backend.domain.models.message_factory import message_factory
from backend.domain.models.messages import AssistantMessage, UserMessage, BaseMessage
# Memory imports removed - preparing for memory system refactoring
from typing import Any, List, Dict, Optional, TypedDict
import re
from backend.shared.utils.text_clean import extract_response_without_think

# Memory manager initialization removed - preparing for memory system refactoring
# memory_manager = MemoryManager()

class MessageParseResult(TypedDict):
    """Type definition for message parsing result"""
    content: Optional[List[Dict[str, Any]]]
    timestamp: Optional[int]
    id: Optional[str]
    session_id: str
    agent_profile: str

def parse_message_data(data: dict) -> MessageParseResult:
    """Parse message data, return content, session ID and agent profile in unified format"""
    message_data = data.get('messageData')
    session_id = data.get('session_id', "default_session")
    agent_profile = data.get('agent_profile', "general")  # Default to general

    if not message_data:
        return {
            'content': None,
            'timestamp': None,
            'id': None,
            'session_id': session_id,
            'agent_profile': agent_profile
        }

    msg_obj = json.loads(message_data)
    text = msg_obj.get('text', '')
    files = msg_obj.get('files', [])
    timestamp = msg_obj.get('timestamp')
    msg_id = msg_obj.get('id')  # Fix: parse id field
    content = []
    if text:
        content.append({"text": text})
    for file in files:
        if file['type'].startswith('image/'):
            b64 = file['data'].split(',', 1)[1]
            content.append({
                "inline_data": {
                    "mime_type": file['type'],
                    "data": b64
                }
            })

    return {
        'content': content,
        'timestamp': timestamp,
        'id': msg_id,
        'session_id': session_id,
        'agent_profile': agent_profile
    }

def process_user_message(result: MessageParseResult, history_msgs: list) -> UserMessage:
    """Process user message, create and return message object, save to history and vector database"""
    if not result['content']:
        raise ValueError("Invalid message content")

    timestamp = result.get('timestamp')
    user_msg = UserMessage(
        content=result['content'],
        timestamp=datetime.fromtimestamp(timestamp / 1000) if timestamp else datetime.now(),
        id=result.get('id')  # Use ID from frontend
    )
    # Save to history
    history_msgs.append(user_msg)
    save_history(result['session_id'], history_msgs)

    return user_msg

def process_assistant_text_message(content: List[Dict[str, Any]], keyword: str, history_msgs: list, session_id: str) -> tuple[str, str]:
    """
    Process AI assistant text message, save to history and vector database, return message ID and processed content.
    
    Args:
        content: Structured content list, each element is a dict with type field
        keyword: Keyword
        history_msgs: History message list
        session_id: Session ID
        
    Returns:
        tuple[str, str]: (Message ID, processed message content)
    """
    message_id = str(uuid.uuid4())
    
    # Extract current text content for checking
    extracted_text = ""
    for content_item in content:
        if isinstance(content_item, dict) and content_item.get("type") == "text":
            extracted_text += content_item.get("text", "") + " "
    
    # Handle keyword-only cases: ensure keyword info is saved to history
    processed_content = content.copy() if isinstance(content, list) else content
    if keyword and not extracted_text.strip():
        # Add keyword marker to content, ensure keyword info is preserved in history
        if isinstance(processed_content, list):
            # Try to find existing text item and update
            text_item_found = False
            for content_item in processed_content:
                if isinstance(content_item, dict) and content_item.get('type') == 'text':
                    # Keep keyword marker in text, frontend can parse
                    content_item['text'] = f"[[{keyword}]]"
                    text_item_found = True
                    break
            
            if not text_item_found:
                processed_content.append({
                    "type": "text",
                    "text": f"[[{keyword}]]"
                })
    
    # Create assistant message object
    assistant_message = AssistantMessage(
        content=processed_content,
        id=message_id
    )
    history_msgs.append(assistant_message)
    save_history(session_id, history_msgs)

    processed_text = ""
    for content_item in processed_content:
        if isinstance(content_item, dict) and content_item.get("type") == "text":
            processed_text += content_item.get("text", "") + " "

    return message_id, processed_text.strip()


async def process_tts_sentence(sentence: str, tts_engine: BaseTTS) -> dict:
    """Process TTS synthesis for single sentence"""
    if sentence is None or sentence == '':
        return None
    if sentence.strip() == '':
        return {'text': sentence, 'audio': None}
    try:
        # If TTS engine is disabled, return text only
        if not tts_engine.enabled:
            return {'text': sentence, 'audio': None}
            
        audio_bytes = await tts_engine.synthesize(sentence)
        
        # Validate audio data
        if not audio_bytes or len(audio_bytes) == 0:
            return {'text': sentence, 'audio': None, 'error': 'Empty audio data from TTS engine'}
        
        # Validate if audio data is valid byte stream
        if not isinstance(audio_bytes, bytes):
            return {'text': sentence, 'audio': None, 'error': f'Invalid audio data type: {type(audio_bytes)}'}
        
        try:
            audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')
            return {'text': sentence, 'audio': audio_b64}
        except Exception as b64_error:
            print(f"Base64 encoding failed: {b64_error}")
            return {'text': sentence, 'audio': None, 'error': f'Base64 encoding failed: {str(b64_error)}'}
    except Exception as e:
        print(f"TTS synthesis failed: {e}")
        return {'text': sentence, 'audio': None, 'error': str(e)}

def should_generate_title(session_id: str, history_msgs: list) -> bool:
    """Determine if title generation is needed: only if current is default title and has one pure text assistant message."""
    sessions = get_all_sessions()
    current_session = next((s for s in sessions if s['id'] == session_id), None)
    has_default_title = (
        current_session is not None and
        (
            current_session.get('name', '').startswith('New Chat')
            or 'New Conversation' in current_session.get('name', '')
        )
    )
    has_pure_text_assistant = any(is_pure_text_assistant(msg) for msg in history_msgs)
    return has_default_title and has_pure_text_assistant

def is_pure_text_assistant(msg):
    """
    Determine if assistant message is non-tool/function_call (tool_calls field doesn't exist or is empty).
    """
    return (
        getattr(msg, "role", None) == "assistant" and not (getattr(msg, "tool_calls", None) or [])
    )

async def generate_title_for_session(session_id: str, llm_client) -> str:
    """
    Utility function: find latest user and pure text assistant messages by session_id and generate title.
    Search backward from end of history to find most recent pair of non-tool messages.
    """
    history = load_history(session_id)
    history_msgs = [message_factory(msg) if isinstance(msg, dict) else msg for msg in history]
    
    # Traverse backward to find most recent pair of non-tool messages
    latest_user_msg = None
    latest_assistant_msg = None
    
    for msg in reversed(history_msgs):
        if not latest_user_msg and getattr(msg, 'role', None) == 'user':
            latest_user_msg = msg
        elif not latest_assistant_msg and is_pure_text_assistant(msg):
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

def extract_response_without_think(response_text: str) -> str:
    """
    Extract content outside <thinking> tags, return only final LLM response to user.
    If no <thinking> tags, return original content.
    """
    # Remove <thinking>...</thinking> and its content
    return re.sub(r'<thinking>[\s\S]*?</thinking>', '', response_text, flags=re.IGNORECASE).strip()
