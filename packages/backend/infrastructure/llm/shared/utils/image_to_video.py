"""
Image-to-video utility functions shared across LLM providers.

Common image-to-video operations including history management and prompt processing.
"""

import os
import json
from datetime import datetime
from typing import List, Dict, Any, Optional


VIDEO_PROMPT_HISTORY_FILENAME = "video_prompt_history.json"


def get_video_prompt_history_file(session_id: str) -> str:
    """Get the path to the video prompt history file for a session."""
    from backend.infrastructure.storage.session_manager import HISTORY_BASE_DIR
    session_dir = os.path.join(HISTORY_BASE_DIR, session_id)
    return os.path.join(session_dir, VIDEO_PROMPT_HISTORY_FILENAME)


def load_video_prompt_history(session_id: str) -> List[Dict[str, Any]]:
    """
    Load video prompt generation history for a session.
    
    Args:
        session_id: Session ID to load history for
        
    Returns:
        List of previous prompt generation records, each containing:
        - user_message: The original request (image context)
        - assistant_message: The generated video prompt response
        - timestamp: When the generation occurred
        - motion_type: The motion type used
        - original_image_prompt: Original image prompt if available
    """
    history_file = get_video_prompt_history_file(session_id)
    
    if not os.path.exists(history_file):
        return []
    
    try:
        with open(history_file, 'r', encoding='utf-8') as f:
            history = json.load(f)
            return history
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"[WARNING] Failed to load video prompt history for session {session_id}: {e}")
        return []


def save_video_prompt_generation(
    session_id: str, 
    user_request: str,
    assistant_response: str
) -> None:
    """
    Save a video prompt generation record to history.
    
    Args:
        session_id: Session ID to save to
        user_request: The original user request text
        assistant_response: Complete assistant response content
    """
    history_file = get_video_prompt_history_file(session_id)
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(history_file), exist_ok=True)
    
    # Load existing history
    history = load_video_prompt_history(session_id)
    
    # Create new record (same format as text-to-image)
    record = {
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
    
    # Add to history
    history.append(record)
    
    # Save updated history
    try:
        with open(history_file, 'w', encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[ERROR] Failed to save video prompt history for session {session_id}: {e}")


def get_latest_video_prompt_from_history(session_id: str) -> Optional[str]:
    """
    Get the latest generated video prompt from session history.
    
    Args:
        session_id: Session ID to search in
        
    Returns:
        Latest video prompt or None if not found
    """
    import re
    from backend.infrastructure.llm.shared.constants.prompts import VIDEO_PROMPT_PATTERN
    
    history = load_video_prompt_history(session_id)
    if not history:
        return None
    
    # Get the most recent record
    latest_record = history[-1]
    assistant_response = latest_record.get("assistant_message", {})
    content = assistant_response.get("content", "")
    
    # Try to extract using XML tags first
    video_match = re.search(VIDEO_PROMPT_PATTERN, content, re.DOTALL)
    if video_match:
        return video_match.group(1).strip()
    
    # Fallback: parse from old format
    if "VIDEO_PROMPT:" in content:
        lines = content.split("\n")
        for line in lines:
            if line.startswith("VIDEO_PROMPT:"):
                return line.replace("VIDEO_PROMPT:", "").strip()
    
    return None


def clear_video_prompt_history(session_id: str) -> bool:
    """
    Clear video prompt history for a session.
    
    Args:
        session_id: Session ID to clear history for
        
    Returns:
        True if successful, False otherwise
    """
    history_file = get_video_prompt_history_file(session_id)
    
    try:
        if os.path.exists(history_file):
            os.remove(history_file)
        return True
    except Exception as e:
        print(f"[ERROR] Failed to clear video prompt history for session {session_id}: {e}")
        return False