import os
import json
import re
import uuid
import shutil
from typing import List, Dict, Any, AsyncGenerator, Tuple, Optional
import asyncio
from datetime import datetime
import requests
from backend.infrastructure.llm.models import ImageMessage, BaseMessage
from backend.infrastructure.llm.models import message_factory
import base64

# 聊天历史相关工具
HISTORY_BASE_DIR = "chat/data"
BACKUP_DIR = "chat/data/backups"

_allowed_keywords_cache: Optional[List[str]] = None

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
    """ load history without image """
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

def get_allowed_keywords_from_prompt_file() -> List[str]:
    """
    从 prompt 文件中解析允许的关键词列表。
    结果会被缓存。
    """
    global _allowed_keywords_cache
    if _allowed_keywords_cache is not None:
        return _allowed_keywords_cache

    # Use the new location in config/prompts
    from pathlib import Path
    project_root = Path(__file__).parent.parent.parent
    file_path = project_root / "config" / "prompts" / "expression_prompt.md"
    keywords = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        matches = re.findall(r'\[\[(\w+)\]\]', content)
        if matches:
            keywords = [keyword.lower() for keyword in matches]
        else:
            print(f"警告: 在 {file_path} 中没有找到关键词。")
    except FileNotFoundError:
        print(f"错误: 关键词文件 '{file_path}' 未找到。")
    
    _allowed_keywords_cache = keywords
    return _allowed_keywords_cache

def parse_llm_output(llm_full_response: str) -> Tuple[str, str]:
    """
    解析 LLM 的输出，提取回复文本和关键词。
    Args:
        llm_full_response: LLM 的完整响应文本
    Returns:
        (response_text, keyword) 元组
    """
    allowed_keywords = get_allowed_keywords_from_prompt_file()
    
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
    
    return filepath

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