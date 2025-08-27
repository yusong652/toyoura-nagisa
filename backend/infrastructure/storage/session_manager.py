"""
会话管理模块

提供聊天会话的创建、读取、更新、删除等功能。
负责会话历史记录的持久化存储和元数据管理。
"""

import os
import json
import uuid
import shutil
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from backend.domain.models.message_factory import message_factory
from backend.domain.models.message_factory import message_factory
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from backend.domain.models.messages import BaseMessage





# 聊天历史相关工具
HISTORY_BASE_DIR = "chat/data"
BACKUP_DIR = "chat/data/backups"


def _get_session_dir(session_id: str) -> str:
    """获取会话目录路径"""
    return os.path.join(HISTORY_BASE_DIR, session_id)


def _get_session_file(session_id: str) -> str:
    """获取会话文件路径"""
    return os.path.join(_get_session_dir(session_id), "history.json")


# ========== 会话CRUD操作 ==========

def create_new_history(name: str = None) -> str:
    """
    创建一个新的聊天历史记录
    Args:
        name: 历史记录的名称，如果为None则使用当前时间作为名称
    Returns:
        新创建的会话ID
    """
    session_id = str(uuid.uuid4())
    if not name:
        name = f"New Chat {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    elif not name.startswith("New Chat") and "新对话" not in name:
        name = f"New Chat - {name}"

    print(f"创建新会话，ID: {session_id}, 名称: '{name}'")

    session_metadata = {
        "id": session_id,
        "name": name,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat()
    }

    # 保存元数据
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

    # 创建会话目录和空的聊天记录文件
    session_dir = _get_session_dir(session_id)
    os.makedirs(session_dir, exist_ok=True)
    session_file = _get_session_file(session_id)
    with open(session_file, 'w', encoding='utf-8') as f:
        json.dump([], f, indent=4, ensure_ascii=False)

    return session_id


def get_all_sessions() -> List[Dict[str, Any]]:
    """
    获取所有可用的聊天会话
    
    Returns:
        会话元数据列表，按更新时间倒序排列
    """
    metadata_file = os.path.join(HISTORY_BASE_DIR, "sessions_metadata.json")
    if not os.path.exists(metadata_file):
        return []
    
    try:
        with open(metadata_file, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
            # 将字典转换为列表并按更新时间排序
            sessions = list(metadata.values())
            sessions.sort(key=lambda x: x.get('updated_at', ''), reverse=True)
            return sessions
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def delete_session_data(session_id: str) -> bool:
    """删除指定会话ID的聊天历史"""
    try:
        session_dir = _get_session_dir(session_id)
        if os.path.exists(session_dir):
            shutil.rmtree(session_dir)
        # 更新元数据
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
    更新会话的标题
    
    Args:
        session_id: 要更新的会话ID
        new_title: 新的会话标题
        
    Returns:
        是否更新成功
    """
    try:
        # 加载会话元数据
        metadata_file = os.path.join(HISTORY_BASE_DIR, "sessions_metadata.json")
        if not os.path.exists(metadata_file):
            return False
            
        with open(metadata_file, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        # 检查会话是否存在
        if session_id not in metadata:
            return False
            
        # 更新标题和更新时间
        metadata[session_id]["name"] = new_title
        metadata[session_id]["updated_at"] = datetime.now().isoformat()
        
        # 保存更新后的元数据
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=4, ensure_ascii=False)
            
        return True
    except Exception as e:
        print(f"更新会话标题时出错: {str(e)}")
        return False


# ========== 消息历史记录操作 ==========

def save_history(session_id: str, current_history: List[Any]) -> None:
    """保存指定会话ID的聊天历史"""
    session_dir = _get_session_dir(session_id)
    session_file = _get_session_file(session_id)
    os.makedirs(session_dir, exist_ok=True)
    processed_history = []
    for msg in current_history:
        # 如果是Pydantic模型，转为dict
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
    # 更新元数据中的更新时间
    _update_session_metadata_timestamp(session_id)


def load_history(session_id: str) -> List[Dict[str, Any]]:
    """load history without image"""
    session_file = _get_session_file(session_id)
    if not os.path.exists(session_file):
        return []
    try:
        with open(session_file, 'r', encoding='utf-8') as f:
            history = json.load(f)
            # 读取后，过滤掉 image 类型
            history = [msg for msg in history if msg.get('role') != 'image']
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
    """加载会话的完整消息历史，包括图片消息"""
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


def load_and_restore_history(session_id: str):
    """
    加载并还原指定会话ID的聊天历史，返回消息对象列表
    """
    
    history = load_all_message_history(session_id)
    return [message_factory(msg) if isinstance(msg, dict) else msg for msg in history]


def delete_message(session_id: str, message_id: str) -> bool:
    """
    从指定会话中删除特定ID的消息，并清理相关文件
    Args:
        session_id: 会话ID
        message_id: 要删除的消息ID
    Returns:
        bool: 是否成功删除
    """
    try:
        session_history = load_all_message_history(session_id)
        if not session_history:
            return False
        
        # 找到要删除的消息，检查是否需要清理文件
        message_to_delete = None
        for msg in session_history:
            if msg.get('id') == message_id:
                message_to_delete = msg
                break
        
        if not message_to_delete:
            return False  # 没找到要删的消息
        
        # 如果是视频消息或图片消息，删除相关文件
        _cleanup_message_files(session_id, message_to_delete)
        
        # 删除消息
        new_history = [msg for msg in session_history if msg.get('id') != message_id]
        
        # 保存更新后的历史记录
        save_history(session_id, new_history)
        return True
    except Exception as e:
        print(f"删除消息时出错: {e}")
        return False


def _cleanup_message_files(session_id: str, message: dict) -> None:
    """
    清理消息相关的文件（视频、图片等）
    
    Args:
        session_id: 会话ID
        message: 要清理的消息对象
    """
    try:
        message_type = message.get('type', '').lower()
        
        if message_type == 'video' and message.get('video_path'):
            # 清理视频文件
            video_path = message.get('video_path')
            if not os.path.isabs(video_path):
                # 如果是相对路径，构建完整路径
                full_path = os.path.join(HISTORY_BASE_DIR, video_path)
            else:
                full_path = video_path
            
            if os.path.exists(full_path):
                os.remove(full_path)
                print(f"[DEBUG] Deleted video file: {full_path}")
            else:
                print(f"[DEBUG] Video file not found: {full_path}")
        
        elif message_type == 'image' and message.get('image_path'):
            # 清理图片文件
            image_path = message.get('image_path')
            if not os.path.isabs(image_path):
                # 如果是相对路径，构建完整路径
                full_path = os.path.join(HISTORY_BASE_DIR, image_path)
            else:
                full_path = image_path
            
            if os.path.exists(full_path):
                os.remove(full_path)
                print(f"[DEBUG] Deleted image file: {full_path}")
            else:
                print(f"[DEBUG] Image file not found: {full_path}")
        
        # 可以在这里添加其他类型文件的清理逻辑
        
    except Exception as e:
        print(f"[WARNING] Failed to cleanup files for message {message.get('id')}: {e}")


def get_latest_n_messages(session_id: str, n: int = 2) -> Tuple[Optional[Any], ...]:
    """
    获取指定会话中最新的n条消息（返回消息对象而非dict）
    只返回 user/assistant 消息，过滤掉 image/tool 等其它类型
    
    Args:
        session_id: 会话ID
        n: 要获取的消息数量，默认为2
        
    Returns:
        Tuple: 包含消息对象的元组，如果消息不足n条，返回所有实际消息
    """
    
    history = load_history(session_id)  # 只返回非 image 消息
    history_msgs = [message_factory(msg) if isinstance(msg, dict) else msg for msg in history]
    if not history_msgs:
        return tuple()
    latest_messages = []
    for msg in reversed(history_msgs):
        if hasattr(msg, 'role') and msg.role in ['user', 'assistant']:
            latest_messages.append(msg)
            if len(latest_messages) == n:
                break
    latest_messages.reverse()

    return tuple(latest_messages)


def get_latest_two_messages(session_id: str) -> Tuple[Optional[Any], Optional[Any]]:
    """
    获取指定会话中最新的两条消息（返回消息对象而非dict）
    只返回 user/assistant 消息，过滤掉 image/tool 等其它类型
    
    Deprecated: 使用 get_latest_n_messages(session_id, 2) 替代
    """
    return get_latest_n_messages(session_id, 2)


# ========== 内部辅助函数 ==========

def _update_session_metadata_timestamp(session_id: str) -> None:
    """更新会话元数据中的时间戳"""
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