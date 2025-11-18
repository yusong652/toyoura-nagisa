"""
Session Management Module

Provides functionality for creating, reading, updating, and deleting chat sessions.
Responsible for persistent storage of session history and metadata management.
"""

import os
import json
import uuid
import shutil
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from backend.domain.models.message_factory import message_factory
from backend.domain.models.messages import BaseMessage


# Chat history related tools
HISTORY_BASE_DIR = "chat/data"
BACKUP_DIR = "chat/data/backups"


def _get_session_dir(session_id: str) -> str:
    """Get session directory path"""
    return os.path.join(HISTORY_BASE_DIR, session_id)


def _get_session_file(session_id: str) -> str:
    """Get session file path"""
    return os.path.join(_get_session_dir(session_id), "history.json")


def _get_runtime_state_file(session_id: str) -> str:
    """Get runtime state file path"""
    return os.path.join(_get_session_dir(session_id), "runtime_state.json")


# ========== Session CRUD Operations ==========

def create_new_history(name: Optional[str] = None) -> str:
    """
    Create a new chat history record
    Args:
        name: Name of the history record, uses current time as name if None
    Returns:
        Newly created session ID
    """
    session_id = str(uuid.uuid4())
    if not name:
        name = f"New Chat {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    elif not name.startswith("New Chat"):
        name = f"New Chat - {name}"

    print(f"[DEBUG] Creating new session, ID: {session_id}, name: '{name}'")

    session_metadata = {
        "id": session_id,
        "name": name,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat()
    }

    # Save metadata
    metadata_file = os.path.join(HISTORY_BASE_DIR, "sessions_metadata.json")
    metadata = {}
    if os.path.exists(metadata_file):
        try:
            with open(metadata_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
        except json.JSONDecodeError:
            metadata = {}
    metadata[session_id] = session_metadata
    with open(metadata_file, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=4, ensure_ascii=False)

    # Create session directory and empty chat history file
    session_dir = _get_session_dir(session_id)
    os.makedirs(session_dir, exist_ok=True)
    session_file = _get_session_file(session_id)
    with open(session_file, 'w', encoding='utf-8') as f:
        json.dump([], f, indent=4, ensure_ascii=False)

    return session_id


def get_all_sessions() -> List[Dict[str, Any]]:
    """
    Get all available chat sessions
    
    Returns:
        List of session metadata, sorted by update time in descending order
    """
    metadata_file = os.path.join(HISTORY_BASE_DIR, "sessions_metadata.json")
    if not os.path.exists(metadata_file):
        return []
    
    try:
        with open(metadata_file, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
            # Convert dictionary to list and sort by update time
            sessions = list(metadata.values())
            sessions.sort(key=lambda x: x.get('updated_at', ''), reverse=True)
            return sessions
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def delete_session_data(session_id: str) -> bool:
    """Delete chat history for specified session ID"""
    try:
        # Clean up background processes for this session
        try:
            from backend.infrastructure.mcp.tools.coding.utils.background_process_manager import cleanup_session_processes
            cleanup_session_processes(session_id)
        except Exception as e:
            print(f"[WARNING] Failed to cleanup background processes for session {session_id}: {e}")

        session_dir = _get_session_dir(session_id)
        if os.path.exists(session_dir):
            shutil.rmtree(session_dir)
        # Update metadata
        metadata_file = os.path.join(HISTORY_BASE_DIR, "sessions_metadata.json")
        if os.path.exists(metadata_file):
            try:
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                if session_id in metadata:
                    del metadata[session_id]
                    with open(metadata_file, 'w', encoding='utf-8') as f:
                        json.dump(metadata, f, indent=4, ensure_ascii=False)
            except (FileNotFoundError, json.JSONDecodeError) as e:
                pass
        return True
    except Exception as e:
        return False


def update_session_title(session_id: str, new_title: str) -> bool:
    """
    Update session title
    
    Args:
        session_id: Session ID to update
        new_title: New session title
        
    Returns:
        Whether update was successful
    """
    try:
        # Load session metadata
        metadata_file = os.path.join(HISTORY_BASE_DIR, "sessions_metadata.json")
        if not os.path.exists(metadata_file):
            return False
            
        with open(metadata_file, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        # Check if session exists
        if session_id not in metadata:
            return False
            
        # Update title and update time
        metadata[session_id]["name"] = new_title
        metadata[session_id]["updated_at"] = datetime.now().isoformat()
        
        # Save updated metadata
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=4, ensure_ascii=False)
            
        return True
    except Exception as e:
        print(f"[ERROR] Failed to update session title: {str(e)}")
        return False


# ========== Message History Operations ==========

def save_history(session_id: str, current_history: List[Any]) -> None:
    """Save chat history for specified session ID"""
    session_dir = _get_session_dir(session_id)
    session_file = _get_session_file(session_id)
    os.makedirs(session_dir, exist_ok=True)
    processed_history = []
    for msg in current_history:
        # If it's a Pydantic model, convert to dict
        if hasattr(msg, 'model_dump'):
            msg_copy = msg.model_dump()
        else:
            msg_copy = dict(msg)
        if 'timestamp' not in msg_copy or not msg_copy['timestamp']:
            msg_copy['timestamp'] = datetime.now().isoformat()
        elif isinstance(msg_copy['timestamp'], datetime):
            msg_copy['timestamp'] = msg_copy['timestamp'].isoformat()
        if msg_copy.get('role') == 'tool':
            if 'tool_call_id' not in msg_copy:
                print(f"[WARNING] Tool message missing tool_call_id: {msg_copy}")
            if 'name' not in msg_copy:
                print(f"[WARNING] Tool message missing name: {msg_copy}")
        processed_history.append(msg_copy)
    with open(session_file, 'w', encoding='utf-8') as f:
        json.dump(processed_history, f, indent=4, ensure_ascii=False)
    # Update the update time in metadata
    _update_session_metadata_timestamp(session_id)


def load_history(session_id: str) -> List[Dict[str, Any]]:
    """load history without image and video"""
    session_file = _get_session_file(session_id)
    if not os.path.exists(session_file):
        return []
    try:
        with open(session_file, 'r', encoding='utf-8') as f:
            history = json.load(f)
            # After reading, filter out image and video types
            history = [msg for msg in history if msg.get('role') not in ['image', 'video']]
            for msg in history:
                if 'timestamp' not in msg or not msg['timestamp']:
                    msg['timestamp'] = datetime.now().isoformat()
                if msg.get('role') == 'tool':
                    if 'tool_call_id' not in msg:
                        print(f"[WARNING] Tool message missing tool_call_id: {msg}")
                    if 'name' not in msg:
                        print(f"[WARNING] Tool message missing name: {msg}")
            return history
    except Exception as e:
        print(f"[ERROR] Failed to load history for session {session_id}: {str(e)}")
        return []


def load_all_message_history(session_id: str) -> List[Dict[str, Any]]:
    """Load complete message history for session, including image messages"""
    session_file = _get_session_file(session_id)
    if not os.path.exists(session_file):
        return []
    try:
        with open(session_file, 'r', encoding='utf-8') as f:
            history = json.load(f)
            for msg in history:
                if 'timestamp' not in msg or not msg['timestamp']:
                    msg['timestamp'] = datetime.now().isoformat()
                if msg.get('role') == 'tool':
                    if 'tool_call_id' not in msg:
                        print(f"[WARNING] Tool message missing tool_call_id: {msg}")
                    if 'name' not in msg:
                        print(f"[WARNING] Tool message missing name: {msg}")
            return history
    except Exception as e:
        print(f"[ERROR] Failed to load all message history for session {session_id}: {str(e)}")
        return []


def load_and_restore_history(session_id: str) -> List[BaseMessage]:
    """
    Load and restore chat history for specified session ID, return list of message objects
    """

    history = load_all_message_history(session_id)
    # Ensure all messages are BaseMessage objects
    return [message_factory(msg) for msg in history]


def delete_message(session_id: str, message_id: str) -> bool:
    """
    Delete message with specific ID from specified session and clean up related files
    Args:
        session_id: Session ID
        message_id: Message ID to delete
    Returns:
        bool: Whether deletion was successful
    """
    try:
        session_history = load_all_message_history(session_id)
        if not session_history:
            return False
        
        # Find the message to delete and check if files need to be cleaned up
        message_to_delete = None
        for msg in session_history:
            if msg.get('id') == message_id:
                message_to_delete = msg
                break
        
        if not message_to_delete:
            return False  # Message to delete not found
        
        # If it's a video or image message, delete related files
        _cleanup_message_files(session_id, message_to_delete)
        
        # Delete message
        new_history = [msg for msg in session_history if msg.get('id') != message_id]
        
        # Save updated history
        save_history(session_id, new_history)
        return True
    except Exception as e:
        print(f"[ERROR] Failed to delete message: {e}")
        return False


def _cleanup_message_files(session_id: str, message: dict) -> None:
    """
    Clean up message-related files (videos, images, etc.)
    
    Args:
        session_id: Session ID
        message: Message object to clean up
    """
    try:
        message_type = message.get('role', message.get('type', '')).lower()
        
        if message_type == 'video' and message.get('video_path'):
            # Clean up video file
            video_path = message.get('video_path')
            if video_path and not os.path.isabs(video_path):
                # If it's a relative path, build full path
                full_path = os.path.join(HISTORY_BASE_DIR, video_path)
            elif video_path:
                full_path = video_path
            else:
                return  # No valid video path
            
            if os.path.exists(full_path):
                os.remove(full_path)
                print(f"[DEBUG] Deleted video file: {full_path}")
            else:
                print(f"[DEBUG] Video file not found: {full_path}")
        
        elif message_type == 'image' and message.get('image_path'):
            # Clean up image file
            image_path = message.get('image_path')
            if image_path and not os.path.isabs(image_path):
                # If it's a relative path, build full path
                full_path = os.path.join(HISTORY_BASE_DIR, image_path)
            elif image_path:
                full_path = image_path
            else:
                return  # No valid image path
            
            if os.path.exists(full_path):
                os.remove(full_path)
                print(f"[DEBUG] Deleted image file: {full_path}")
            else:
                print(f"[DEBUG] Image file not found: {full_path}")
        
        # Other file type cleanup logic can be added here
        
    except Exception as e:
        print(f"[WARNING] Failed to cleanup files for message {message.get('id')}: {e}")


def get_latest_n_messages(session_id: str, n: int = 2) -> Tuple[BaseMessage, ...]:
    """
    Get latest n messages from specified session (returns message objects instead of dict)
    Only returns pure conversational user/assistant messages, filters out:
    - Image/video messages
    - Tool use messages (assistant messages with tool_use blocks)
    - Tool result messages (user messages with tool_result blocks)

    This ensures only actual conversation content is returned for:
    - Title generation
    - Memory saving
    - Image/video prompt generation context

    Args:
        session_id: Session ID
        n: Number of messages to get, defaults to 2

    Returns:
        Tuple: Tuple containing BaseMessage objects, returns all actual messages if less than n messages exist
    """

    history = load_history(session_id)  # Only returns non-image and non-video messages
    # Ensure all messages are BaseMessage objects
    history_msgs: List[BaseMessage] = [message_factory(msg) for msg in history]
    if not history_msgs:
        return tuple()

    latest_messages: List[BaseMessage] = []
    for msg in reversed(history_msgs):
        # Check if message is pure conversation (not tool-related)
        if msg.role in ['user', 'assistant']:
            # Filter out tool messages by checking content structure
            is_tool_message = _is_tool_message(msg)
            if not is_tool_message:
                latest_messages.append(msg)
                if len(latest_messages) == n:
                    break

    latest_messages.reverse()
    return tuple(latest_messages)


def get_latest_two_messages(session_id: str) -> Tuple[BaseMessage, ...]:
    """
    Get latest two messages from specified session (returns message objects instead of dict)
    Only returns user/assistant messages, filters out image/tool and other types
    
    Deprecated: Use get_latest_n_messages(session_id, 2) instead
    """
    return get_latest_n_messages(session_id, 2)


def get_latest_user_text(session_id: str) -> Optional[str]:
    """
    Get latest user text message content from session.
    
    Specifically for scenarios requiring user input text like memory search.
    Skips non-text user messages like image, video, etc.
    
    Args:
        session_id: Session ID
        
    Returns:
        Optional[str]: Latest user text content, returns None if not found
    """
    from backend.domain.models.message_factory import extract_text_from_message
    
    history = load_and_restore_history(session_id)
    if not history:
        return None
    
    # Search for user text messages starting from the latest
    for msg in reversed(history):
        if msg.role == 'user':
            text = extract_text_from_message(msg)
            if text and text.strip():
                return text
    
    return None


def get_latest_user_message(session_id: str) -> Optional[BaseMessage]:
    """
    Get latest user message object from session.

    Returns the most recent user message as a complete BaseMessage object,
    useful for memory saving and other operations requiring full message context.

    Args:
        session_id: Session ID

    Returns:
        Optional[BaseMessage]: Latest user message object, returns None if not found
    """
    history = load_history(session_id)
    if not history:
        return None

    # Search for user messages starting from the latest
    for msg in reversed(history):
        msg_obj = message_factory(msg) if isinstance(msg, dict) else msg
        if msg_obj.role == 'user':
            return msg_obj

    return None


# ========== Internal Helper Functions ==========

def _is_tool_message(msg: BaseMessage) -> bool:
    """
    Check if a message contains tool-related content (tool_use or tool_result).

    Tool messages are identified by their content structure:
    - Assistant messages with 'tool_use' blocks
    - User messages with 'tool_result' blocks

    Args:
        msg: Message object to check

    Returns:
        bool: True if message contains tool content, False otherwise
    """
    content = msg.content

    # Handle structured content (list of content blocks)
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict):
                block_type = block.get('type')
                # Check for tool_use (in assistant messages) or tool_result (in user messages)
                if block_type in ['tool_use', 'tool_result']:
                    return True

    return False


def _update_session_metadata_timestamp(session_id: str) -> None:
    """Update timestamp in session metadata"""
    metadata_file = os.path.join(HISTORY_BASE_DIR, "sessions_metadata.json")
    if os.path.exists(metadata_file):
        try:
            with open(metadata_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
                if session_id in metadata:
                    metadata[session_id]['updated_at'] = datetime.now().isoformat()
                    with open(metadata_file, 'w', encoding='utf-8') as f:
                        json.dump(metadata, f, indent=4, ensure_ascii=False)
        except (FileNotFoundError, json.JSONDecodeError):
            pass


# ========== Session Runtime State Management ==========

def save_runtime_state(session_id: str, state: Dict[str, Any]) -> None:
    """
    Save runtime state for a session.

    Runtime state includes temporary flags like:
    - last_response_interrupted: Whether the last response was interrupted by user
    - Other runtime flags as needed

    Args:
        session_id: Session identifier
        state: Dictionary containing runtime state
    """
    runtime_file = _get_runtime_state_file(session_id)

    # Ensure session directory exists
    session_dir = _get_session_dir(session_id)
    os.makedirs(session_dir, exist_ok=True)

    try:
        with open(runtime_file, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=4, ensure_ascii=False)
        print(f"[DEBUG] Saved runtime state for session {session_id}: {state}")
    except Exception as e:
        print(f"[ERROR] Failed to save runtime state for session {session_id}: {e}")


def load_runtime_state(session_id: str) -> Dict[str, Any]:
    """
    Load runtime state for a session.

    Args:
        session_id: Session identifier

    Returns:
        Dictionary containing runtime state, empty dict if file doesn't exist
    """
    runtime_file = _get_runtime_state_file(session_id)

    if not os.path.exists(runtime_file):
        return {}

    try:
        with open(runtime_file, 'r', encoding='utf-8') as f:
            state = json.load(f)
        print(f"[DEBUG] Loaded runtime state for session {session_id}: {state}")
        return state
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"[WARNING] Failed to load runtime state for session {session_id}: {e}")
        return {}


def update_runtime_state(session_id: str, key: str, value: Any) -> None:
    """
    Update a single key in runtime state.

    Args:
        session_id: Session identifier
        key: State key to update
        value: New value for the key
    """
    state = load_runtime_state(session_id)
    state[key] = value
    save_runtime_state(session_id, state)


def clear_runtime_state(session_id: str) -> None:
    """
    Clear runtime state for a session.

    Args:
        session_id: Session identifier
    """
    runtime_file = _get_runtime_state_file(session_id)

    if os.path.exists(runtime_file):
        try:
            os.remove(runtime_file)
            print(f"[DEBUG] Cleared runtime state for session {session_id}")
        except Exception as e:
            print(f"[ERROR] Failed to clear runtime state for session {session_id}: {e}")


# ========== Token Usage Management ==========

def save_token_usage(session_id: str, usage: Dict[str, int]) -> None:
    """
    Save token usage information to runtime state.

    Token usage is stored in runtime_state.json and includes:
    - prompt_tokens: Input tokens (context window usage)
    - completion_tokens: Output tokens (AI response)
    - total_tokens: Total tokens used in this turn
    - tokens_left: Remaining tokens in context window

    Args:
        session_id: Session identifier
        usage: Dictionary containing token usage statistics
    """
    update_runtime_state(session_id, 'token_usage', usage)
    print(f"[DEBUG] Saved token usage for session {session_id}: {usage}")


def load_token_usage(session_id: str) -> Optional[Dict[str, int]]:
    """
    Load token usage information from runtime state.

    Args:
        session_id: Session identifier

    Returns:
        Optional[Dict[str, int]]: Token usage statistics or None if not available
    """
    state = load_runtime_state(session_id)
    usage = state.get('token_usage')
    if usage:
        print(f"[DEBUG] Loaded token usage for session {session_id}: {usage}")
    return usage