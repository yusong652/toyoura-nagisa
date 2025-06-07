import os
import json
import re
import uuid
import shutil
from typing import List, Dict, Any, AsyncGenerator, Tuple
import asyncio
from datetime import datetime
from backend.config import get_prompt_config

# 聊天历史相关工具
HISTORY_DIR = "chat/data"
BACKUP_DIR = "chat/data/backups"

def _get_session_file(session_id: str) -> str:
    # 文件名格式: YYYYMMDD_sessionid.json
    date_str = datetime.now().strftime('%Y%m%d')
    return os.path.join(HISTORY_DIR, f"{date_str}_{session_id}.json")

# 备份单个 session 聊天记录

def backup_history(session_id: str) -> str:
    session_file = _get_session_file(session_id)
    if not os.path.exists(session_file):
        return ""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = os.path.join(BACKUP_DIR, f"{session_id}_{timestamp}.json")
    shutil.copy2(session_file, backup_file)
    return backup_file

# 保存指定会话ID的聊天历史

def save_history(session_id: str, current_history: List[Dict[str, Any]]) -> None:
    session_file = _get_session_file(session_id)
    os.makedirs(HISTORY_DIR, exist_ok=True)
    processed_history = []
    for msg in current_history:
        msg_copy = msg.copy()
        if 'timestamp' not in msg_copy or not msg_copy['timestamp']:
            msg_copy['timestamp'] = datetime.now().isoformat()
        elif isinstance(msg_copy['timestamp'], datetime):
            msg_copy['timestamp'] = msg_copy['timestamp'].isoformat()
        if 'role' not in msg_copy and hasattr(msg, 'role'):
            msg_copy['role'] = msg.role
        if msg_copy.get('role') == 'tool':
            if 'tool_call_id' not in msg_copy:
                print(f"[WARNING] Tool message missing tool_call_id: {msg_copy}")
            if 'name' not in msg_copy:
                print(f"[WARNING] Tool message missing name: {msg_copy}")
        processed_history.append(msg_copy)
    with open(session_file, 'w', encoding='utf-8') as f:
        json.dump(processed_history, f, indent=4, ensure_ascii=False)
    # 更新元数据中的更新时间
    metadata_file = os.path.join(HISTORY_DIR, "sessions_metadata.json")
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
        session_file = _get_session_file(session_id)
        if os.path.exists(session_file):
            os.remove(session_file)
        # 更新元数据
        metadata_file = os.path.join(HISTORY_DIR, "sessions_metadata.json")
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
    metadata_file = os.path.join(HISTORY_DIR, "sessions_metadata.json")
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

    # 创建空的聊天记录文件
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
    metadata_file = os.path.join(HISTORY_DIR, "sessions_metadata.json")
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
        if not os.path.exists(HISTORY_FILE):
            return False
            
        # 备份当前历史记录
        backup_file = backup_history()
        if backup_file:
            print(f"删除消息前已备份历史记录到: {backup_file}")
            
        # 加载所有历史记录
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            all_history = json.load(f)
            
        # 如果会话不存在
        if session_id not in all_history:
            return False
            
        # 获取会话历史
        session_history = all_history[session_id]
        
        # 找到并删除消息
        message_found = False
        new_history = []
        for msg in session_history:
            if 'id' in msg and msg['id'] == message_id:
                message_found = True
                continue  # 跳过此消息，相当于删除
            new_history.append(msg)
            
        # 如果找不到消息
        if not message_found:
            return False
            
        # 更新历史记录
        all_history[session_id] = new_history
        
        # 保存更新后的历史记录
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(all_history, f, indent=4, ensure_ascii=False)
            
        # 更新元数据中的更新时间
        metadata_file = os.path.join(HISTORY_DIR, "sessions_metadata.json")
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
    except (FileNotFoundError, json.JSONDecodeError, IOError) as e:
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
        metadata_file = os.path.join(HISTORY_DIR, "sessions_metadata.json")
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
    from backend.chat.models import message_factory
    history = load_history(session_id)
    return [message_factory(msg) if isinstance(msg, dict) else msg for msg in history] 