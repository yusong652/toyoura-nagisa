"""
Text-to-image utility functions shared across LLM providers.

Common text-to-image operations including history management and prompt processing.
"""

import os
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from ..constants.defaults import DEFAULT_MAX_HISTORY_LENGTH, TEXT_TO_IMAGE_HISTORY_FILENAME


def get_text_to_image_history_file(session_id: str) -> str:
    """Get the path to the text-to-image history file for a session."""
    from backend.infrastructure.storage.session_manager import HISTORY_BASE_DIR
    session_dir = os.path.join(HISTORY_BASE_DIR, session_id)
    return os.path.join(session_dir, TEXT_TO_IMAGE_HISTORY_FILENAME)


def load_text_to_image_history(session_id: str) -> List[Dict[str, Any]]:
    """
    Load text-to-image prompt generation history for a session.
    
    Args:
        session_id: Session ID to load history for
        
    Returns:
        List of previous prompt generation records, each containing:
        - user_message: The original request
        - assistant_message: The generated prompt response
        - timestamp: When the generation occurred
    """
    history_file = get_text_to_image_history_file(session_id)
    
    if not os.path.exists(history_file):
        return []
    
    try:
        with open(history_file, 'r', encoding='utf-8') as f:
            history = json.load(f)
            return history
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"[WARNING] Failed to load text-to-image history for session {session_id}: {e}")
        return []


def save_text_to_image_generation(
    session_id: str, 
    user_request: str, 
    assistant_response: str,
    max_history_length: int = DEFAULT_MAX_HISTORY_LENGTH
) -> None:
    """
    Save a text-to-image prompt generation record to history.
    
    Args:
        session_id: Session ID to save to
        user_request: The original user request text
        assistant_response: Complete assistant response content
        max_history_length: Maximum number of records to keep (default: 10)
    """
    history_file = get_text_to_image_history_file(session_id)
    
    # Ensure session directory exists
    session_dir = os.path.dirname(history_file)
    os.makedirs(session_dir, exist_ok=True)
    
    # Load existing history
    history = load_text_to_image_history(session_id)
    
    # Create new record
    new_record = {
        "user_message": {
            "role": "user",
            "content": user_request
        },
        "assistant_message": {
            "role": "assistant", 
            "content": assistant_response  # Save complete assistant response without formatting
        },
        "timestamp": datetime.now().isoformat()
    }
    
    # Add new record and maintain history length
    history.append(new_record)
    if len(history) > max_history_length:
        history = history[-max_history_length:]  # Keep only the latest records
    
    # Save updated history
    try:
        with open(history_file, 'w', encoding='utf-8') as f:
            json.dump(history, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[ERROR] Failed to save text-to-image history for session {session_id}: {e}")