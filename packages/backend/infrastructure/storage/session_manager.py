"""
Session Management Module

Provides functionality for creating, reading, updating, and deleting chat sessions.
Responsible for persistent storage of session history and metadata management.
"""

import os
import json
import uuid
import shutil
import tempfile
from typing import List, Dict, Any, Optional, Tuple, cast
from datetime import datetime
from backend.domain.models.message_factory import message_factory
from backend.domain.models.messages import BaseMessage


# Chat history related tools
HISTORY_BASE_DIR = "chat/data"
BACKUP_DIR = "chat/data/backups"
DEFAULT_SESSION_MODE = "build"
VALID_SESSION_MODES = {"build", "plan"}


def _get_session_dir(session_id: str) -> str:
    """Get session directory path"""
    return os.path.join(HISTORY_BASE_DIR, session_id)


def _get_session_file(session_id: str) -> str:
    """Get session file path"""
    return os.path.join(_get_session_dir(session_id), "history.json")


def _get_runtime_state_file(session_id: str) -> str:
    """Get runtime state file path"""
    return os.path.join(_get_session_dir(session_id), "runtime_state.json")


def _get_session_metadata_file(session_id: str) -> str:
    """Get per-session metadata file path"""
    return os.path.join(_get_session_dir(session_id), "metadata.json")


def _atomic_json_write(file_path: str, data: Any) -> None:
    """
    Write JSON data atomically using temp file + rename pattern.

    This ensures that:
    1. Either the old file or new file exists (never empty)
    2. Interruption during write leaves the original file intact
    3. The write is atomic on POSIX systems (rename is atomic)

    Args:
        file_path: Target file path
        data: Data to write (must be JSON serializable)
    """
    dir_path = os.path.dirname(file_path)
    os.makedirs(dir_path, exist_ok=True)

    # Write to temp file in the same directory (ensures same filesystem for atomic rename)
    fd, temp_path = tempfile.mkstemp(suffix='.tmp', dir=dir_path)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())  # Ensure data is written to disk

        # Atomic rename (on POSIX systems)
        os.replace(temp_path, file_path)
    except Exception:
        # Clean up temp file if rename failed
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass
        raise


def _load_session_metadata(session_id: str) -> Optional[Dict[str, Any]]:
    """
    Load metadata for a single session from per-session file.

    Args:
        session_id: Session identifier

    Returns:
        Session metadata dict or None if not found
    """
    session_metadata_file = _get_session_metadata_file(session_id)
    if not os.path.exists(session_metadata_file):
        return None

    try:
        with open(session_metadata_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"[WARNING] Failed to load metadata for session {session_id}: {e}")
        return None


def _save_session_metadata(session_id: str, metadata: Dict[str, Any]) -> None:
    """
    Save metadata for a single session to per-session file atomically.

    Args:
        session_id: Session identifier
        metadata: Session metadata to save
    """
    session_metadata_file = _get_session_metadata_file(session_id)
    _atomic_json_write(session_metadata_file, metadata)


def _load_sessions_metadata() -> Dict[str, Any]:
    """
    Load all sessions metadata by scanning per-session metadata files.

    Scans chat/data/{session_id}/metadata.json for each session directory.

    Returns:
        Dict mapping session_id to metadata
    """
    all_metadata: Dict[str, Any] = {}

    if not os.path.exists(HISTORY_BASE_DIR):
        return all_metadata

    for entry in os.listdir(HISTORY_BASE_DIR):
        session_dir = os.path.join(HISTORY_BASE_DIR, entry)
        if os.path.isdir(session_dir) and entry != "backups":
            session_metadata_file = os.path.join(session_dir, "metadata.json")
            if os.path.exists(session_metadata_file):
                try:
                    with open(session_metadata_file, 'r', encoding='utf-8') as f:
                        metadata = json.load(f)
                        all_metadata[entry] = metadata
                except (FileNotFoundError, json.JSONDecodeError) as e:
                    print(f"[WARNING] Failed to load metadata for session {entry}: {e}")

    return all_metadata


def _save_sessions_metadata(metadata: Dict[str, Any]) -> None:
    """
    Save sessions metadata to per-session files.

    Args:
        metadata: Dict mapping session_id to metadata
    """
    for session_id, session_metadata in metadata.items():
        try:
            _save_session_metadata(session_id, session_metadata)
        except Exception as e:
            print(f"[ERROR] Failed to save metadata for session {session_id}: {e}")


def _normalize_session_metadata_entry(session_metadata: Dict[str, Any]) -> bool:
    updated = False
    if "mode" not in session_metadata:
        session_metadata["mode"] = DEFAULT_SESSION_MODE
        updated = True

    from backend.infrastructure.storage.llm_config_manager import normalize_llm_config

    llm_config = session_metadata.get("llm_config")
    normalized_config, llm_updated = normalize_llm_config(llm_config)
    
    if llm_updated:
        session_metadata["llm_config"] = normalized_config
        updated = True
        
    return updated


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

    session_metadata: Dict[str, Any] = {
        "id": session_id,
        "name": name,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "mode": DEFAULT_SESSION_MODE,
    }

    from backend.infrastructure.storage.llm_config_manager import build_initial_llm_config
    default_llm_config = build_initial_llm_config()
    if default_llm_config:
        session_metadata["llm_config"] = cast(Any, default_llm_config)

    # Create session directory
    session_dir = _get_session_dir(session_id)
    os.makedirs(session_dir, exist_ok=True)

    # Save metadata to per-session file atomically
    _save_session_metadata(session_id, session_metadata)

    # Create empty chat history file
    session_file = _get_session_file(session_id)
    _atomic_json_write(session_file, [])

    return session_id


def get_all_sessions() -> List[Dict[str, Any]]:
    """
    Get all available chat sessions
    
    Returns:
        List of session metadata, sorted by update time in descending order
    """
    metadata = _load_sessions_metadata()
    if not metadata:
        return []

    updated = False
    sessions = list(metadata.values())
    for session_metadata in sessions:
        if _normalize_session_metadata_entry(session_metadata):
            updated = True

    if updated:
        _save_sessions_metadata(metadata)

    sessions.sort(key=lambda x: x.get('updated_at', ''), reverse=True)
    return sessions


def delete_session_data(session_id: str) -> bool:
    """Delete chat history and metadata for specified session ID"""
    try:
        # Clean up background processes for this session
        try:
            from backend.infrastructure.shell.background_process_manager import cleanup_session_processes
            cleanup_session_processes(session_id)
        except Exception as e:
            print(f"[WARNING] Failed to cleanup background processes for session {session_id}: {e}")

        # Delete session directory (includes metadata.json, history.json, runtime_state.json)
        session_dir = _get_session_dir(session_id)
        if os.path.exists(session_dir):
            shutil.rmtree(session_dir)
            print(f"[DEBUG] Deleted session directory: {session_dir}")

        return True
    except Exception as e:
        print(f"[ERROR] Failed to delete session {session_id}: {e}")
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
    return update_session_metadata(session_id, {"name": new_title})


def get_session_metadata(session_id: str) -> Optional[Dict[str, Any]]:
    """Get session metadata by session ID."""
    session_metadata = _load_session_metadata(session_id)
    if not session_metadata:
        return None

    if _normalize_session_metadata_entry(session_metadata):
        # Save normalized metadata back to per-session file
        _save_session_metadata(session_id, session_metadata)

    return session_metadata


def update_session_metadata(session_id: str, updates: Dict[str, Any]) -> bool:
    """Update session metadata fields and refresh updated_at timestamp."""
    session_metadata = _load_session_metadata(session_id)
    if not session_metadata:
        return False

    session_metadata.update(updates)
    session_metadata["updated_at"] = datetime.now().isoformat()
    _save_session_metadata(session_id, session_metadata)
    return True


def get_session_llm_config(session_id: str) -> Optional[Dict[str, Any]]:
    """Get session-level LLM configuration from metadata."""
    session_metadata = get_session_metadata(session_id)
    if not session_metadata:
        return None

    llm_config = session_metadata.get("llm_config")
    if not isinstance(llm_config, dict):
        return None

    if "provider" not in llm_config or "model" not in llm_config:
        return None

    return llm_config


def update_session_llm_config(
    session_id: str,
    provider: str,
    model: str,
    secondary_model: Optional[str] = None,
) -> bool:
    """Update session-level LLM configuration in metadata."""
    session_metadata = _load_session_metadata(session_id)
    if not session_metadata:
        return False

    llm_config: Dict[str, Any] = {
        "provider": provider,
        "model": model,
    }
    if secondary_model:
        llm_config["secondary_model"] = secondary_model

    session_metadata["llm_config"] = llm_config
    session_metadata["updated_at"] = datetime.now().isoformat()
    _save_session_metadata(session_id, session_metadata)
    return True


def clear_session_llm_config(session_id: str) -> bool:
    """Clear session-level LLM configuration from metadata."""
    session_metadata = _load_session_metadata(session_id)
    if not session_metadata:
        return False

    if "llm_config" in session_metadata:
        del session_metadata["llm_config"]

    session_metadata["updated_at"] = datetime.now().isoformat()
    _save_session_metadata(session_id, session_metadata)
    return True


def get_session_mode(session_id: str) -> str:
    """Get current session mode (build or plan)."""
    session_metadata = get_session_metadata(session_id)
    if not session_metadata:
        return DEFAULT_SESSION_MODE
    return session_metadata.get("mode", DEFAULT_SESSION_MODE)


def update_session_mode(session_id: str, mode: str) -> bool:
    """Update session mode in metadata."""
    normalized_mode = (mode or "").lower()
    if normalized_mode not in VALID_SESSION_MODES:
        raise ValueError(f"Invalid session mode: {mode}")

    return update_session_metadata(session_id, {"mode": normalized_mode})


# ========== Message History Operations ==========

def save_history(session_id: str, current_history: List[Any]) -> None:
    """Save chat history for specified session ID using atomic write"""
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

    # Use atomic write to prevent data loss on interruption
    _atomic_json_write(session_file, processed_history)

    # Update the update time in metadata
    _update_session_metadata_timestamp(session_id)


def load_history(session_id: str) -> List[Dict[str, Any]]:
    """
    Load history without image and video.

    NOTE: This function returns RAW history from disk without any modifications.
    For LLM API calls that require tool_use/tool_result pairing, use
    repair_interrupted_tool_calls() after loading.
    """
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
    """
    Load complete message history for session, including image messages.

    NOTE: This function returns RAW history from disk without any modifications.
    For LLM API calls that require tool_use/tool_result pairing, use
    repair_interrupted_tool_calls() after loading.
    """
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


def _cleanup_message_files(_session_id: str, message: dict) -> None:
    """
    Clean up message-related files (videos, images, etc.)

    Args:
        _session_id: Session ID (reserved for future use)
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

def _detect_interrupted_tool_calls(history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Detect tool_use blocks that don't have corresponding tool_result.

    When a session is interrupted unexpectedly (e.g., process killed during tool execution),
    the assistant message with tool_use may be saved but the tool_result message is missing.
    This function identifies such orphaned tool_use blocks.

    Args:
        history: List of message dictionaries

    Returns:
        List of dictionaries containing message_index and tool_use block for each interrupted call
    """
    # Collect all tool_result's tool_use_id
    completed_tool_ids = set()
    for msg in history:
        if msg.get('role') == 'user':
            content = msg.get('content', [])
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get('type') == 'tool_result':
                        tool_use_id = block.get('tool_use_id')
                        if tool_use_id:
                            completed_tool_ids.add(tool_use_id)

    # Find tool_use blocks without corresponding tool_result
    interrupted = []
    for idx, msg in enumerate(history):
        if msg.get('role') == 'assistant':
            content = msg.get('content', [])
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get('type') == 'tool_use':
                        tool_id = block.get('id')
                        if tool_id and tool_id not in completed_tool_ids:
                            interrupted.append({
                                'message_index': idx,
                                'tool_use': block
                            })

    return interrupted


def repair_interrupted_tool_calls(history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Repair history by adding placeholder tool_result for interrupted tool_use blocks.

    This ensures that the message history maintains proper tool_use/tool_result pairing,
    which is required by LLM APIs. The placeholder tool_result indicates that the
    operation was interrupted.

    IMPORTANT: This function creates IN-MEMORY placeholders only. The returned history
    should NOT be persisted to disk. Use this only for preparing history for LLM API calls.

    Args:
        history: List of message dictionaries (will not be modified)

    Returns:
        New list with placeholder tool_results added (original list unchanged)
    """
    interrupted = _detect_interrupted_tool_calls(history)

    if not interrupted:
        return history

    # Group interrupted tool calls by message index
    tool_uses_by_msg_idx: Dict[int, List[Dict]] = {}
    for item in interrupted:
        idx = item['message_index']
        if idx not in tool_uses_by_msg_idx:
            tool_uses_by_msg_idx[idx] = []
        tool_uses_by_msg_idx[idx].append(item['tool_use'])

    # Build repaired history
    repaired_history = []
    for idx, msg in enumerate(history):
        repaired_history.append(msg)

        # If this assistant message has interrupted tool_use, add placeholder tool_result
        if idx in tool_uses_by_msg_idx:
            tool_uses = tool_uses_by_msg_idx[idx]

            # Create placeholder tool_result blocks for each interrupted tool_use
            tool_result_blocks = []
            for tool_use in tool_uses:
                tool_result_block = {
                    "type": "tool_result",
                    "tool_use_id": tool_use.get('id'),
                    "tool_name": tool_use.get('name', 'unknown'),
                    "content": {
                        "parts": [
                            {
                                "type": "text",
                                "text": "Operation interrupted: session terminated unexpectedly before tool execution completed."
                            }
                        ]
                    },
                    "is_error": True,
                    "data": {
                        "interrupted": True,
                        "original_input": tool_use.get('input', {})
                    }
                }
                tool_result_blocks.append(tool_result_block)

            # Create a user message containing all tool_result blocks
            placeholder_message = {
                "role": "user",
                "content": tool_result_blocks,
                "id": str(uuid.uuid4()),
                "timestamp": datetime.now().isoformat()
            }
            repaired_history.append(placeholder_message)

    # NOTE: Do NOT persist the repaired history to disk.
    # Placeholders are only for in-memory LLM API calls to maintain tool_use/tool_result pairing.
    # If the tool execution completes later, save_tool_result_message will add the real result.
    # If the session was truly interrupted, placeholders will be regenerated on next load.

    return repaired_history


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
    session_metadata = _load_session_metadata(session_id)
    if session_metadata:
        session_metadata['updated_at'] = datetime.now().isoformat()
        _save_session_metadata(session_id, session_metadata)


# ========== Session Runtime State Management ==========

def save_runtime_state(session_id: str, state: Dict[str, Any]) -> None:
    """
    Save runtime state for a session using atomic write.

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
        _atomic_json_write(runtime_file, state)
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


def load_token_usage(session_id: str) -> Optional[Dict[str, int]]:
    """
    Load token usage information from runtime state.

    Args:
        session_id: Session identifier

    Returns:
        Optional[Dict[str, int]]: Token usage statistics or None if not available
    """
    state = load_runtime_state(session_id)
    return state.get('token_usage')


# ========== Thinking Mode Configuration ==========

# Valid thinking levels (same for all providers that support thinking)
VALID_THINKING_LEVELS = {"default", "low", "high"}


def get_session_thinking_level(session_id: str) -> str:
    """
    Get thinking_level setting from session metadata.

    Thinking level controls the reasoning effort of LLM providers:
    - "default": Don't pass thinking params, use API's default behavior
    - "low": Use low reasoning effort
    - "high": Use high reasoning effort

    Args:
        session_id: Session identifier

    Returns:
        str: Thinking level. Default: "default"
    """
    session_metadata = get_session_metadata(session_id)
    if not session_metadata:
        return "default"

    level = session_metadata.get("thinking_level", "default")
    return level if level in VALID_THINKING_LEVELS else "default"


def update_session_thinking_level(session_id: str, thinking_level: str) -> bool:
    """
    Update thinking_level setting in session metadata.

    Args:
        session_id: Session identifier
        thinking_level: Thinking level ("default", "low", or "high")

    Returns:
        bool: True if update was successful, False otherwise

    Raises:
        ValueError: If thinking_level is not valid
    """
    if thinking_level not in VALID_THINKING_LEVELS:
        raise ValueError(f"Invalid thinking level: {thinking_level}. Must be one of {VALID_THINKING_LEVELS}")

    return update_session_metadata(session_id, {"thinking_level": thinking_level})
