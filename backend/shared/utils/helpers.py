import json
import base64
import asyncio
import uuid
from datetime import datetime
from backend.infrastructure.storage.session_manager import save_history
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
    message: str  # Add text message field
    request_id: str  # Add request ID field
    enable_memory: bool  # Add memory setting field

def parse_message_data(data: dict) -> MessageParseResult:
    """Parse WebSocket message data in unified format"""
    session_id = data.get('session_id', "default_session")
    agent_profile = data.get('agent_profile', "general")
    text = data.get('message', '')
    files = data.get('files', [])
    msg_id = data.get('message_id')
    enable_memory = data.get('enable_memory', True)  # Default to True, simplified

    # Convert ISO timestamp to milliseconds if present
    timestamp = None
    if data.get('timestamp'):
        try:
            dt = datetime.fromisoformat(data['timestamp'].replace('Z', '+00:00'))
            timestamp = int(dt.timestamp() * 1000)
        except:
            timestamp = None

    # Build content array - use standard ContentBlock format
    content = []
    if text:
        content.append({"type": "text", "text": text})

    for file in files:
        if file['type'].startswith('image/'):
            b64_data = file['data']
            if ',' in b64_data:
                b64_data = b64_data.split(',', 1)[1]
            content.append({
                "inline_data": {
                    "mime_type": file['type'],
                    "data": b64_data
                }
            })

    return {
        'content': content,
        'timestamp': timestamp,
        'id': msg_id,
        'session_id': session_id,
        'agent_profile': agent_profile,
        'message': text,  # Add text message for streaming handler
        'request_id': str(uuid.uuid4()),  # Generate unique request ID
        'enable_memory': enable_memory  # Add memory setting
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

def save_assistant_message(content: List[Dict[str, Any]], session_id: str) -> str:
    """
    Save AI assistant message to history and return message ID.

    Args:
        content: Structured content list from LLM response
        session_id: Session ID

    Returns:
        str: Generated message ID
    """
    message_id = str(uuid.uuid4())

    # Load complete history including images and other content
    from backend.infrastructure.storage.session_manager import load_all_message_history
    history = load_all_message_history(session_id)
    history_msgs = [message_factory(msg) if isinstance(msg, dict) else msg for msg in history]

    # Create assistant message object - save content as-is
    assistant_message = AssistantMessage(
        content=content,
        id=message_id
    )

    # Add to history and save
    history_msgs.append(assistant_message)
    save_history(session_id, history_msgs)

    return message_id


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
        >>> update_assistant_message(
        ...     message_id="msg-123",
        ...     content=[
        ...         {"type": "thinking", "thinking": "Complete thinking..."},
        ...         {"type": "text", "text": "Complete response..."}
        ...     ],
        ...     session_id="session-456"
        ... )
    """
    # Load complete history
    from backend.infrastructure.storage.session_manager import load_all_message_history
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
        >>> save_tool_result_message("call_1", "read_file", tool_result, session_id)
        'msg_uuid_123'
    """
    from backend.infrastructure.storage.session_manager import load_all_message_history

    # Extract content from tool result
    llm_content = tool_result.get("llm_content", {})

    # Build tool_result content block
    tool_result_content = {
        "type": "tool_result",
        "tool_use_id": tool_call_id,
        "tool_name": tool_name,
        "content": llm_content,  # Use llm_content from ToolResult
        "is_error": tool_result.get("status") == "error"
    }

    # Generate message ID
    message_id = str(uuid.uuid4())

    # Load history
    history = load_all_message_history(session_id)
    history_msgs = [message_factory(msg) if isinstance(msg, dict) else msg for msg in history]

    # Create user message with tool result
    message = UserMessage(
        content=[tool_result_content],
        id=message_id,
        timestamp=datetime.now()
    )

    # Add to history and save
    history_msgs.append(message)
    save_history(session_id, history_msgs)

    return message_id


async def process_tts_sentence(sentence: str, tts_engine: BaseTTS) -> Optional[dict]:
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

def extract_response_without_think(response_text: str) -> str:
    """
    Extract content outside <thinking> tags, return only final LLM response to user.
    If no <thinking> tags, return original content.
    """
    # Remove <thinking>...</thinking> and its content
    return re.sub(r'<thinking>[\s\S]*?</thinking>', '', response_text, flags=re.IGNORECASE).strip()
