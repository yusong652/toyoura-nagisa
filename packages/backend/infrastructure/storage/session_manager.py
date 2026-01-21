"""
Session Management Module

Provides functionality for creating, reading, updating, and deleting chat sessions.
Responsible for persistent storage of session history and metadata management.
"""

import os
import json
import uuid
import shutil
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


def _get_metadata_file() -> str:
    return os.path.join(HISTORY_BASE_DIR, "sessions_metadata.json")


def _load_sessions_metadata() -> Dict[str, Any]:
    metadata_file = _get_metadata_file()
    if not os.path.exists(metadata_file):
        return {}
    try:
        with open(metadata_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_sessions_metadata(metadata: Dict[str, Any]) -> None:
    metadata_file = _get_metadata_file()
    with open(metadata_file, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=4, ensure_ascii=False)


def _get_env_provider_override() -> Optional[str]:
    from backend.config import get_llm_settings

    provider = get_llm_settings().env_provider_override
    if not provider:
        return None

    return provider.lower()


def _get_provider_secondary_model(provider: str) -> Optional[str]:
    from backend.config import get_llm_settings

    llm_settings = get_llm_settings()
    if provider == "google":
        return llm_settings.get_google_config().secondary_model
    if provider == "anthropic":
        return llm_settings.get_anthropic_config().secondary_model
    if provider in ("openai", "gpt"):
        return llm_settings.get_openai_config().secondary_model
    if provider == "moonshot":
        return llm_settings.get_moonshot_config().secondary_model
    if provider == "zhipu":
        return llm_settings.get_zhipu_config().secondary_model
    if provider == "openrouter":
        return llm_settings.get_openrouter_config().secondary_model

    return None


def _build_default_session_llm_config() -> Optional[Dict[str, Any]]:
    from backend.infrastructure.storage.llm_config_manager import get_default_llm_config
    from backend.infrastructure.llm.shared.models_registry import (
        get_all_providers,
        get_provider_models,
        is_model_valid_for_provider,
        is_provider_supported,
    )

    default_config = get_default_llm_config()
    if isinstance(default_config, dict):
        provider = default_config.get("provider")
        model = default_config.get("model")
        secondary_model = default_config.get("secondary_model")
        if provider and model and is_provider_supported(provider):
            if is_model_valid_for_provider(provider, model):
                if secondary_model and not is_model_valid_for_provider(provider, secondary_model):
                    secondary_model = None

                if not secondary_model:
                    secondary_model = _get_provider_secondary_model(provider) or model

                return {
                    "provider": provider,
                    "model": model,
                    "secondary_model": secondary_model,
                }

    env_provider = _get_env_provider_override()
    provider = env_provider
    if provider and not is_provider_supported(provider):
        provider = None

    if not provider:
        providers = get_all_providers()
        provider = providers[0].provider if providers else None

    if not provider:
        return None

    models = get_provider_models(provider)
    if not models:
        return None

    model = models[0].id
    secondary_model = _get_provider_secondary_model(provider) or model
    if secondary_model and not is_model_valid_for_provider(provider, secondary_model):
        secondary_model = model

    return {
        "provider": provider,
        "model": model,
        "secondary_model": secondary_model,
    }


def _normalize_session_metadata_entry(session_metadata: Dict[str, Any]) -> bool:
    updated = False
    if "mode" not in session_metadata:
        session_metadata["mode"] = DEFAULT_SESSION_MODE
        updated = True

    from backend.infrastructure.llm.shared.models_registry import (
        is_model_valid_for_provider,
        is_provider_supported,
    )

    llm_config = session_metadata.get("llm_config")
    if not isinstance(llm_config, dict):
        llm_config = None

    if llm_config:
        provider = llm_config.get("provider")
        model = llm_config.get("model")
        secondary_model = llm_config.get("secondary_model")
        if provider and model and is_provider_supported(provider):
            if is_model_valid_for_provider(provider, model):
                if secondary_model and not is_model_valid_for_provider(provider, secondary_model):
                    secondary_model = None
                    updated = True
                if not secondary_model:
                    secondary_model = _get_provider_secondary_model(provider) or model
                    updated = True
                if secondary_model:
                    llm_config["secondary_model"] = secondary_model
                    session_metadata["llm_config"] = llm_config
                    return updated

    default_llm_config = _build_default_session_llm_config()
    if default_llm_config:
        session_metadata["llm_config"] = cast(Any, default_llm_config)
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

    default_llm_config = _build_default_session_llm_config()
    if default_llm_config:
        session_metadata["llm_config"] = cast(Any, default_llm_config)

    # Ensure base directory exists
    os.makedirs(HISTORY_BASE_DIR, exist_ok=True)

    # Save metadata
    metadata: Dict[str, Any] = _load_sessions_metadata()
    metadata[session_id] = session_metadata
    _save_sessions_metadata(metadata)

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
    """Delete chat history for specified session ID"""
    try:
        # Clean up background processes for this session
        try:
            from backend.infrastructure.shell.background_process_manager import cleanup_session_processes
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


def get_session_metadata(session_id: str) -> Optional[Dict[str, Any]]:
    """Get session metadata by session ID."""
    metadata = _load_sessions_metadata()
    session_metadata = metadata.get(session_id)
    if not session_metadata:
        return None

    if _normalize_session_metadata_entry(session_metadata):
        _save_sessions_metadata(metadata)

    return session_metadata


def update_session_metadata(session_id: str, updates: Dict[str, Any]) -> bool:
    """Update session metadata fields and refresh updated_at timestamp."""
    metadata = _load_sessions_metadata()
    if session_id not in metadata:
        return False

    metadata[session_id].update(updates)
    metadata[session_id]["updated_at"] = datetime.now().isoformat()
    _save_sessions_metadata(metadata)
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
    metadata = _load_sessions_metadata()
    if session_id not in metadata:
        return False

    llm_config: Dict[str, Any] = {
        "provider": provider,
        "model": model,
    }
    if secondary_model:
        llm_config["secondary_model"] = secondary_model

    metadata[session_id]["llm_config"] = llm_config
    metadata[session_id]["updated_at"] = datetime.now().isoformat()
    _save_sessions_metadata(metadata)
    return True


def clear_session_llm_config(session_id: str) -> bool:
    """Clear session-level LLM configuration from metadata."""
    metadata = _load_sessions_metadata()
    if session_id not in metadata:
        return False

    if "llm_config" in metadata[session_id]:
        del metadata[session_id]["llm_config"]

    metadata[session_id]["updated_at"] = datetime.now().isoformat()
    _save_sessions_metadata(metadata)
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
