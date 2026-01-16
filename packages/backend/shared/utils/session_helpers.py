"""
Session-related utility functions.

Contains helper functions for working with session data, messages, and content.
"""
import os
import base64
from typing import Optional


def find_latest_image_in_session(session_id: str) -> str:
    """
    Find the most recent image in a session.
    
    Searches through session messages in reverse chronological order to find
    the latest image message with a valid image_path.
    
    Args:
        session_id: Session ID to search in
        
    Returns:
        Base64 encoded image data
        
    Raises:
        ValueError: If no recent image is found in the conversation
        
    Example:
        try:
            image_data = find_latest_image_in_session("session-123")
            # Use image data for processing
        except ValueError as e:
            print(f"No image found: {e}")
    """
    try:
        from backend.infrastructure.storage.session_manager import load_all_message_history
        
        all_messages = load_all_message_history(session_id)
        
        for msg in reversed(all_messages):
            # Convert Pydantic model to dict if needed
            if hasattr(msg, 'model_dump'):
                msg_dict = msg.model_dump()
            elif hasattr(msg, 'dict'):
                msg_dict = msg.dict()
            else:
                msg_dict = msg
            
            # Look for image messages
            if msg_dict.get("role") == "image" and msg_dict.get("image_path"):
                image_path = msg_dict.get("image_path")
                try:
                    full_path = os.path.join("chat/data", image_path)
                    
                    if os.path.exists(full_path):
                        with open(full_path, "rb") as f:
                            return base64.b64encode(f.read()).decode('utf-8')
                except Exception:
                    continue
        
        # No image found
        raise ValueError("No recent image found in conversation. Please send an image first.")
        
    except Exception as e:
        if isinstance(e, ValueError):
            raise
        raise ValueError("Failed to search for images in session") from e


 
