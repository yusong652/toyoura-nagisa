"""
Video storage module

Provides video saving and management functionality.
Supports saving videos from base64 data and automatically creates video message records.
"""

import os
import uuid
import base64
from datetime import datetime
from typing import Optional
from backend.domain.models.messages import VideoMessage
from backend.infrastructure.storage.session_manager import load_all_message_history, save_history


def save_video_from_base64(video_base64: str, session_id: str, output_dir_base: str = "chat/data", format: str = "mp4") -> str:
    """
    Save base64 encoded video to the specified session directory, create video message and save to history
    Args:
        video_base64 (str): base64 encoded video data
        session_id (str): session ID
        output_dir_base (str): base output directory
        format (str): video format (mp4, gif, webm)
    Returns:
        str: saved video path
    """
    print(f"[DEBUG] save_video_from_base64 called with session_id: {session_id}")
    print(f"[DEBUG] video base64 data length: {len(video_base64)}")
    print(f"[DEBUG] video format: {format}")
    
    session_dir = os.path.join(output_dir_base, session_id)
    os.makedirs(session_dir, exist_ok=True)
    print(f"[DEBUG] Session directory created/exists: {session_dir}")
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"generated_video_{timestamp}.{format}"
    filepath = os.path.join(session_dir, filename)
    print(f"[DEBUG] Target filepath: {filepath}")
    
    # Decode base64 and save video
    try:
        # If base64 string contains data URL prefix, remove it
        if video_base64.startswith('data:video') or video_base64.startswith('data:image/gif'):
            print("[DEBUG] Removing data URL prefix from base64 string")
            video_base64 = video_base64.split(',')[1]
            print(f"[DEBUG] After removing prefix, length: {len(video_base64)}")
        
        print("[DEBUG] Attempting to decode base64 data")
        video_data = base64.b64decode(video_base64)
        print(f"[DEBUG] Decoded video data size: {len(video_data)} bytes")
        
        print(f"[DEBUG] Writing video data to file: {filepath}")
        with open(filepath, "wb") as f:
            f.write(video_data)
        print(f"[DEBUG] Successfully wrote video file: {filepath}")
        
        # Verify if file exists
        if os.path.exists(filepath):
            file_size = os.path.getsize(filepath)
            print(f"[DEBUG] File exists and size is: {file_size} bytes")
        else:
            print(f"[ERROR] File does not exist after writing: {filepath}")
            
    except Exception as e:
        print(f"[ERROR] Failed to decode and save base64 video: {e}")
        import traceback
        print(f"[ERROR] Traceback: {traceback.format_exc()}")
        raise e
    
    # Create video message and add to history
    _create_and_save_video_message(session_id, filename, format)
    
    return filepath


def _create_and_save_video_message(session_id: str, filename: str, format: str = "mp4") -> None:
    """
    Create video message and add to session history
    
    Args:
        session_id: session ID
        filename: video filename
        format: video format
    """
    # Create video message
    relative_path = os.path.join(session_id, filename)
    print(f"[DEBUG] Creating video message with relative_path: {relative_path}")
    video_message = VideoMessage(
        role="video",
        content="",  # Empty content, only display video
        video_path=relative_path,
        id=str(uuid.uuid4()),
        timestamp=datetime.now()
    )
    
    # Add video message to history
    print("[DEBUG] Loading current history to append video message")
    history = load_all_message_history(session_id)
    history.append(video_message)
    print(f"[DEBUG] Saving history with {len(history)} messages")
    save_history(session_id, history)
    print("[DEBUG] Video message successfully saved to history")