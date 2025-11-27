"""
Image Storage Module

Provides image download, save and management functionality.
Supports saving images from URLs and base64 data, automatically creating image message records.
"""

import os
import uuid
import base64
import requests
from datetime import datetime
from typing import Optional
from backend.domain.models.messages import ImageMessage
from backend.infrastructure.storage.session_manager import load_all_message_history, save_history
    


def save_image_from_url(image_url: str, session_id: str, output_dir_base: str = "chat/data") -> str:
    """
    Download image and save to specified session directory, create image message and save to history
    Args:
        image_url (str): Image URL
        session_id (str): Session ID
        output_dir_base (str): Base output directory
    Returns:
        str: Saved image path
    """
    session_dir = os.path.join(output_dir_base, session_id)
    os.makedirs(session_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"generated_image_{timestamp}.png"
    filepath = os.path.join(session_dir, filename)
    
    # Download and save image
    image_data = requests.get(image_url).content
    with open(filepath, "wb") as f:
        f.write(image_data)
    
    # Create image message and add to history
    _create_and_save_image_message(session_id, filename)
    
    return filepath


def save_image_from_base64(image_base64: str, session_id: str, output_dir_base: str = "chat/data") -> str:
    """
    Save base64 encoded image to specified session directory, create image message and save to history
    Args:
        image_base64 (str): Base64 encoded image data
        session_id (str): Session ID
        output_dir_base (str): Base output directory
    Returns:
        str: Saved image path
    """
    print(f"[DEBUG] save_image_from_base64 called with session_id: {session_id}")
    print(f"[DEBUG] base64 data length: {len(image_base64)}")
    print(f"[DEBUG] base64 data starts with: {image_base64[:50]}...")
    
    session_dir = os.path.join(output_dir_base, session_id)
    os.makedirs(session_dir, exist_ok=True)
    print(f"[DEBUG] Session directory created/exists: {session_dir}")
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"generated_image_{timestamp}.png"
    filepath = os.path.join(session_dir, filename)
    print(f"[DEBUG] Target filepath: {filepath}")
    
    # Decode base64 and save image
    try:
        original_length = len(image_base64)
        # If base64 string contains data URL prefix, remove it
        if image_base64.startswith('data:image'):
            print("[DEBUG] Removing data URL prefix from base64 string")
            image_base64 = image_base64.split(',')[1]
            print(f"[DEBUG] After removing prefix, length: {len(image_base64)}")
        
        print("[DEBUG] Attempting to decode base64 data")
        image_data = base64.b64decode(image_base64)
        print(f"[DEBUG] Decoded image data size: {len(image_data)} bytes")
        
        print(f"[DEBUG] Writing image data to file: {filepath}")
        with open(filepath, "wb") as f:
            f.write(image_data)
        print(f"[DEBUG] Successfully wrote image file: {filepath}")
        
        # Verify file exists
        if os.path.exists(filepath):
            file_size = os.path.getsize(filepath)
            print(f"[DEBUG] File exists and size is: {file_size} bytes")
        else:
            print(f"[ERROR] File does not exist after writing: {filepath}")
            
    except Exception as e:
        print(f"[ERROR] Failed to decode and save base64 image: {e}")
        import traceback
        print(f"[ERROR] Traceback: {traceback.format_exc()}")
        raise e
    
    # Create image message and add to history
    _create_and_save_image_message(session_id, filename)
    
    return filepath


def _create_and_save_image_message(session_id: str, filename: str) -> None:
    """
    Create image message and add to session history
    
    Args:
        session_id: Session ID
        filename: Image filename
    """
    # Create image message
    relative_path = os.path.join(session_id, filename)
    print(f"[DEBUG] Creating image message with relative_path: {relative_path}")
    image_message = ImageMessage(
        role="image",
        content="",
        image_path=relative_path,
        id=str(uuid.uuid4()),
        timestamp=datetime.now()
    )

    # Add image message to history
    print("[DEBUG] Loading current history to append image message")
    from backend.domain.models.message_factory import message_factory
    history = load_all_message_history(session_id)
    history_msgs = [message_factory(msg) if isinstance(msg, dict) else msg for msg in history]
    history_msgs.append(image_message)
    print(f"[DEBUG] Saving history with {len(history_msgs)} messages")
    save_history(session_id, history_msgs)
    print("[DEBUG] Image message successfully saved to history")