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
HISTORY_FILE = "chat/data/chat_history.json"
HISTORY_DIR = "chat/data"
BACKUP_DIR = "chat/data/backups"

def backup_history() -> str:
    """
    备份当前的历史记录文件
    
    Returns:
        备份文件的路径
    """
    # 确保备份目录存在
    os.makedirs(BACKUP_DIR, exist_ok=True)
    
    # 如果历史记录文件不存在，则不需要备份
    if not os.path.exists(HISTORY_FILE):
        return ""
    
    # 创建带时间戳的备份文件名
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = os.path.join(BACKUP_DIR, f"chat_history_{timestamp}.json")
    
    # 复制文件
    shutil.copy2(HISTORY_FILE, backup_file)
    
    # 同时备份元数据文件
    metadata_file = os.path.join(HISTORY_DIR, "sessions_metadata.json")
    if os.path.exists(metadata_file):
        metadata_backup = os.path.join(BACKUP_DIR, f"sessions_metadata_{timestamp}.json")
        shutil.copy2(metadata_file, metadata_backup)
    
    return backup_file

def delete_history_session(session_id: str) -> bool:
    """
    删除指定的历史记录会话
    
    Args:
        session_id: 要删除的会话ID
        
    Returns:
        是否删除成功
    """
    # 检查历史记录文件是否存在
    if not os.path.exists(HISTORY_FILE):
        return False
    
    # 备份当前历史记录
    backup_file = backup_history()
    if backup_file:
        print(f"删除会话前已备份历史记录到: {backup_file}")
    
    try:
        # 加载所有历史记录
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            all_history = json.load(f)
        
        # 如果会话ID存在，则删除
        if session_id in all_history:
            del all_history[session_id]
            
            # 保存更新后的历史记录
            with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
                json.dump(all_history, f, indent=4, ensure_ascii=False)
            
            # 同时从元数据中删除
            metadata_file = os.path.join(HISTORY_DIR, "sessions_metadata.json")
            if os.path.exists(metadata_file):
                try:
                    with open(metadata_file, 'r', encoding='utf-8') as f:
                        metadata = json.load(f)
                    
                    if session_id in metadata:
                        del metadata[session_id]
                        
                        with open(metadata_file, 'w', encoding='utf-8') as f:
                            json.dump(metadata, f, indent=4, ensure_ascii=False)
                except (FileNotFoundError, json.JSONDecodeError):
                    pass
            
            return True
        else:
            return False
    except (FileNotFoundError, json.JSONDecodeError):
        return False

def create_new_history(name: str = None) -> str:
    """
    创建一个新的聊天历史记录
    
    Args:
        name: 历史记录的名称，如果为None则使用当前时间作为名称
        
    Returns:
        新创建的会话ID
    """
    # 备份当前历史记录
    backup_file = backup_history()
    if backup_file:
        print(f"历史记录已备份到: {backup_file}")
    
    # 确保数据目录存在
    os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
    
    # 生成唯一的会话ID
    session_id = str(uuid.uuid4())
    
    # 如果没有提供名称，则使用标准格式"New Chat"加时间
    if not name:
        name = f"New Chat {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    # 如果提供了名称但不是标准格式，也强制使用标准格式
    elif not name.startswith("New Chat") and "新对话" not in name:
        name = f"New Chat - {name}"
    
    print(f"创建新会话，ID: {session_id}, 名称: '{name}'")
    
    # 创建新的历史记录元数据
    session_metadata = {
        "id": session_id,
        "name": name,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat()
    }
    
    # 加载所有历史记录
    all_history = {}
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                all_history = json.load(f)
        except json.JSONDecodeError:
            all_history = {}
    
    # 初始化新的会话历史和元数据
    all_history[session_id] = []
    
    # 保存元数据到单独的文件
    metadata_file = os.path.join(HISTORY_DIR, "sessions_metadata.json")
    metadata = {}
    if os.path.exists(metadata_file):
        try:
            with open(metadata_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
        except json.JSONDecodeError:
            metadata = {}
    
    metadata[session_id] = session_metadata
    
    # 保存元数据
    with open(metadata_file, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=4, ensure_ascii=False)
    
    # 保存历史记录
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_history, f, indent=4, ensure_ascii=False)
    
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

def load_history(session_id: str) -> List[Dict[str, Any]]:
    """
    加载指定会话ID的聊天历史，自动补全非法或缺失的timestamp
    """
    try:
        if not os.path.exists(HISTORY_FILE):
            return []
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            all_history = json.load(f)
            history = all_history.get(session_id, [])
            # 补全非法或缺失的timestamp
            for msg in history:
                if 'timestamp' not in msg or not msg['timestamp']:
                    msg['timestamp'] = datetime.now().isoformat()
            return history
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def save_history(session_id: str, current_history: List[Dict[str, Any]]) -> None:
    """
    保存指定会话ID的聊天历史，每条消息都包含时间戳，且为字符串
    """
    os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
    try:
        all_history = {}
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                try:
                    all_history = json.load(f)
                except json.JSONDecodeError:
                    all_history = {}
        # 处理所有消息，确保timestamp为字符串
        processed_history = []
        for msg in current_history:
            msg_copy = msg.copy()
            if 'timestamp' not in msg_copy or not msg_copy['timestamp']:
                msg_copy['timestamp'] = datetime.now().isoformat()
            elif isinstance(msg_copy['timestamp'], datetime):
                msg_copy['timestamp'] = msg_copy['timestamp'].isoformat()
            if 'role' not in msg_copy and hasattr(msg, 'role'):
                msg_copy['role'] = msg.role
            processed_history.append(msg_copy)
        all_history[session_id] = processed_history
        
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
        
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(all_history, f, indent=4, ensure_ascii=False)
    except IOError as e:
        print(f"Error saving history: {e}")

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