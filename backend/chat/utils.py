import os
import json
import re
from typing import List, Dict, Any, AsyncGenerator, Tuple
import asyncio
from datetime import datetime
from ..config import get_prompt_config

# 聊天历史相关工具
HISTORY_FILE = "backend/chat/data/chat_history.json"
MAX_HISTORY_MESSAGES = 20

# 默认的分割句读点
DEFAULT_SPLIT_PUNCTUATIONS = ['。', '！', '？', '!', '?', '.', '，', ',', '~', '、', '…', '—']
# 默认的标点符号数量限制
DEFAULT_PUNCTUATION_LIMIT = 4

def split_text_by_punctuations(text: str, punctuations: List[str] = DEFAULT_SPLIT_PUNCTUATIONS, punctuation_limit: int = DEFAULT_PUNCTUATION_LIMIT) -> List[str]:
    """
    按标点符号分割文本，每N个标点符号为一组
    
    Args:
        text: 要分割的文本
        punctuations: 用于分割的标点符号列表
        punctuation_limit: 每组包含的标点符号数量限制
        
    Returns:
        分割后的文本列表
    """
    if not text:
        return []
        
    sentences = []
    current_sentence = ""
    punctuation_count = 0
    
    for char in text:
        current_sentence += char
        if char in punctuations:
            punctuation_count += 1
            if punctuation_count >= punctuation_limit:
                sentences.append(current_sentence)
                current_sentence = ""
                punctuation_count = 0
            
    # 添加最后一个句子（如果有）
    if current_sentence:
        sentences.append(current_sentence)
        
    return sentences

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
        # 为每条消息添加/修正时间戳为字符串
        for msg in current_history:
            if 'timestamp' not in msg or not msg['timestamp']:
                msg['timestamp'] = datetime.now().isoformat()
            elif isinstance(msg['timestamp'], datetime):
                msg['timestamp'] = msg['timestamp'].isoformat()
        all_history[session_id] = current_history
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