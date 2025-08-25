"""
视频存储模块

提供视频的保存和管理功能。
支持从base64数据保存视频，并自动创建视频消息记录。
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
    将base64编码的视频保存到指定session目录，同时创建视频消息并保存到历史记录
    Args:
        video_base64 (str): base64编码的视频数据
        session_id (str): 会话ID
        output_dir_base (str): 基础输出目录
        format (str): 视频格式 (mp4, gif, webm)
    Returns:
        str: 保存的视频路径
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
    
    # 解码base64并保存视频
    try:
        # 如果base64字符串包含数据URL前缀，去掉它
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
        
        # 验证文件是否存在
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
    
    # 创建视频消息并添加到历史记录
    _create_and_save_video_message(session_id, filename, format)
    
    return filepath


def _create_and_save_video_message(session_id: str, filename: str, format: str = "mp4") -> None:
    """
    创建视频消息并添加到会话历史记录
    
    Args:
        session_id: 会话ID
        filename: 视频文件名
        format: 视频格式
    """
    # 创建视频消息
    relative_path = os.path.join(session_id, filename)
    print(f"[DEBUG] Creating video message with relative_path: {relative_path}")
    video_message = VideoMessage(
        content="🎬 视频已生成完成",
        video_path=relative_path,
        id=str(uuid.uuid4()),
        timestamp=datetime.now()
    )
    
    # 将视频消息添加到历史记录
    print("[DEBUG] Loading current history to append video message")
    history = load_all_message_history(session_id)
    history.append(video_message)
    print(f"[DEBUG] Saving history with {len(history)} messages")
    save_history(session_id, history)
    print("[DEBUG] Video message successfully saved to history")