import os
import json
import re
import uuid
import shutil
from typing import List, Dict, Any, AsyncGenerator, Tuple, Optional
import asyncio
from datetime import datetime
from backend.config import get_prompt_config
import requests
from backend.chat.models import ImageMessage, BaseMessage
from backend.chat.models import message_factory

# 聊天历史相关工具
HISTORY_BASE_DIR = "chat/data"
BACKUP_DIR = "chat/data/backups"

def _get_session_dir(session_id: str) -> str:
    return os.path.join(HISTORY_BASE_DIR, session_id)

def _get_session_file(session_id: str) -> str:
    # 文件名固定为 history.json
    return os.path.join(_get_session_dir(session_id), "history.json")

# 保存指定会话ID的聊天历史

def save_history(session_id: str, current_history: List[BaseMessage]) -> None:
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

# 读取指定会话ID的聊天历史

def load_history(session_id: str) -> List[Dict[str, Any]]:
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

# 删除指定会话ID的聊天历史

def delete_session_data(session_id: str) -> bool:
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

async def stream_response(response_text: str, chunk_size: int = 3) -> AsyncGenerator[str, None]:
    """
    将响应文本流式输出
    
    Args:
        response_text: 完整的响应文本
        chunk_size: 每次输出的字符数
        
    Yields:
        文本片段
    """
    for i in range(0, len(response_text), chunk_size):
        chunk = response_text[i:i + chunk_size]
        yield chunk
        await asyncio.sleep(0.1)  # 控制输出速度 

def parse_llm_output(llm_full_response: str) -> Tuple[str, str]:
    """
    解析 LLM 的输出，提取回复文本和关键词。
    Args:
        llm_full_response: LLM 的完整响应文本
    Returns:
        (response_text, keyword) 元组
    """
    config = get_prompt_config()
    allowed_keywords = config["allowed_keywords"]
    
    keyword = "neutral"  # Default keyword
    response_text = llm_full_response.strip()

    match = re.search(r'\[\[(\w+)\]\]\s*$', llm_full_response.strip())
    if match:
        extracted_keyword = match.group(1).lower()
        if extracted_keyword in allowed_keywords:
            keyword = extracted_keyword
            response_text = llm_full_response[:match.start()].strip()
        else:
            print(f"警告: LLM 返回了未定义的关键词 '{extracted_keyword}'")
            response_text = llm_full_response[:match.start()].strip()

    return response_text, keyword 

def delete_message(session_id: str, message_id: str) -> bool:
    """
    从指定会话中删除特定ID的消息
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
        # 删除消息
        new_history = [msg for msg in session_history if msg.get('id') != message_id]
        if len(new_history) == len(session_history):
            return False  # 没找到要删的
        # 保存
        save_history(session_id, new_history)
        # 更新元数据中的更新时间
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
        return True
    except Exception as e:
        print(f"删除消息时出错: {e}")
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

def load_and_restore_history(session_id: str):
    """
    加载并还原指定会话ID的聊天历史，返回消息对象列表
    """
    history = load_all_message_history(session_id)
    return [message_factory(msg) if isinstance(msg, dict) else msg for msg in history] 

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
    
    # 创建图片消息
    relative_path = os.path.join(session_id, filename)
    image_message = ImageMessage(
        content="",
        image_path=relative_path,
        id=str(uuid.uuid4()),
        timestamp=datetime.now()
    )
    
    # 将图片消息添加到历史记录
    history = load_all_message_history(session_id)
    history.append(image_message)
    save_history(session_id, history)
    
    return filepath

def get_latest_two_messages(session_id: str) -> Tuple[Optional[Any], Optional[Any]]:
    """
    获取指定会话中最新的两条消息（返回消息对象而非dict）
    只返回 user/assistant 消息，过滤掉 image/tool 等其它类型
    """
    history = load_history(session_id)  # 只返回非 image 消息
    history_msgs = [message_factory(msg) if isinstance(msg, dict) else msg for msg in history]
    if not history_msgs:
        return None, None
    latest_messages = []
    for msg in reversed(history_msgs):
        if hasattr(msg, 'role') and msg.role in ['user', 'assistant']:
            latest_messages.append(msg)
            if len(latest_messages) == 2:
                break
    while len(latest_messages) < 2:
        latest_messages.append(None)
    latest_messages.reverse()
    return tuple(latest_messages)

def load_all_message_history(session_id: str) -> List[Dict[str, Any]]:
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