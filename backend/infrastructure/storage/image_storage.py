"""
图片存储模块

提供图片的下载、保存和管理功能。
支持从URL和base64数据保存图片，并自动创建图片消息记录。
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
    下载图片并保存到指定session目录，同时创建图片消息并保存到历史记录
    Args:
        image_url (str): 图片链接
        session_id (str): 会话ID
        output_dir_base (str): 基础输出目录
    Returns:
        str: 保存的图片路径
    """
    session_dir = os.path.join(output_dir_base, session_id)
    os.makedirs(session_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"generated_image_{timestamp}.png"
    filepath = os.path.join(session_dir, filename)
    
    # 下载并保存图片
    image_data = requests.get(image_url).content
    with open(filepath, "wb") as f:
        f.write(image_data)
    
    # 创建图片消息并添加到历史记录
    _create_and_save_image_message(session_id, filename)
    
    return filepath


def save_image_from_base64(image_base64: str, session_id: str, output_dir_base: str = "chat/data") -> str:
    """
    将base64编码的图片保存到指定session目录，同时创建图片消息并保存到历史记录
    Args:
        image_base64 (str): base64编码的图片数据
        session_id (str): 会话ID
        output_dir_base (str): 基础输出目录
    Returns:
        str: 保存的图片路径
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
    
    # 解码base64并保存图片
    try:
        original_length = len(image_base64)
        # 如果base64字符串包含数据URL前缀，去掉它
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
        
        # 验证文件是否存在
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
    
    # 创建图片消息并添加到历史记录
    _create_and_save_image_message(session_id, filename)
    
    return filepath


def _create_and_save_image_message(session_id: str, filename: str) -> None:
    """
    创建图片消息并添加到会话历史记录
    
    Args:
        session_id: 会话ID
        filename: 图片文件名
    """
    # 创建图片消息
    relative_path = os.path.join(session_id, filename)
    print(f"[DEBUG] Creating image message with relative_path: {relative_path}")
    image_message = ImageMessage(
        content="",
        image_path=relative_path,
        id=str(uuid.uuid4()),
        timestamp=datetime.now()
    )
    
    # 将图片消息添加到历史记录
    print("[DEBUG] Loading current history to append image message")
    history = load_all_message_history(session_id)
    history.append(image_message)
    print(f"[DEBUG] Saving history with {len(history)} messages")
    save_history(session_id, history)
    print("[DEBUG] Image message successfully saved to history")