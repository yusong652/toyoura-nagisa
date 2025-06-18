import json
import base64
import asyncio
import uuid
from datetime import datetime
from backend.chat.utils import get_all_sessions, update_session_title, save_history, load_history
from backend.tts.base import BaseTTS
from backend.chat.title_generator import generate_conversation_title
from backend.config import get_llm_config
from backend.chat.models import message_factory, AssistantMessage, UserToolMessage, UserMessage, AssistantToolMessage, BaseMessage
from backend.memory import MemoryManager
from typing import Any
import re
from backend.utils.text_clean import extract_response_without_think

# 初始化MemoryManager
memory_manager = MemoryManager()

def parse_message_data(data: dict) -> tuple:
    """解析消息数据，返回消息内容和会话ID"""
    message_data = data.get('messageData')
    if not message_data:
        return None, data.get('session_id', "default_session")
    msg_obj = json.loads(message_data)
    text = msg_obj.get('text', '')
    files = msg_obj.get('files', [])
    timestamp = msg_obj.get('timestamp')
    msg_id = msg_obj.get('id')  # 修复：解析id字段
    content = []
    if text:
        content.append({"text": text})
    for file in files:
        if file['type'].startswith('image/'):
            b64 = file['data'].split(',', 1)[1]
            content.append({
                "inline_data": {
                    "mime_type": file['type'],
                    "data": b64
                }
            })
    return {
        'content': content,
        'timestamp': timestamp,
        'id': msg_id  # 修复：返回id字段
    }, data.get('session_id', "default_session")

def process_user_message(parsed_data: dict, session_id: str, history_msgs: list) -> UserMessage:
    """处理用户消息，创建并返回消息对象，同时保存到历史记录和向量数据库"""
    timestamp = parsed_data.get('timestamp')
    user_msg = UserMessage(
        content=parsed_data['content'],
        timestamp=datetime.fromtimestamp(timestamp / 1000) if timestamp else datetime.now(),
        id=parsed_data.get('id')  # 使用前端传来的ID
    )
    # 保存到历史记录
    history_msgs.append(user_msg)
    save_history(session_id, history_msgs)
    
    # 保存到向量数据库
    # 只提取纯文本内容
    text_content = ""
    if isinstance(user_msg.content, list):
        for item in user_msg.content:
            if isinstance(item, dict) and "text" in item:
                text_content += item["text"] + " "
    elif isinstance(user_msg.content, str):
        text_content = user_msg.content
    
    # 只有当有纯文本内容时才保存到向量数据库
    if text_content.strip():
        memory_manager.add_conversation_memory(
            user_id="default",
            conversation_id=session_id,
            content=text_content.strip(),
            additional_metadata={
                "message_id": user_msg.id,
                "timestamp": user_msg.timestamp.isoformat(),
                "type": "user_message"
            }
        )
    
    return user_msg

def process_ai_text_message(response_text: str, keyword: str, history_msgs: list, session_id: str) -> tuple[str, str]:
    """处理AI文本消息，保存历史记录和向量数据库，并返回消息ID和处理后的消息内容"""
    ai_msg_id = str(uuid.uuid4())
    # 确保 response_text 不为 None
    response_text = response_text or ""
    content = f"{response_text}[[{keyword}]]" if keyword else response_text
    ai_msg = AssistantMessage(
        content=content,
        id=ai_msg_id
    )
    history_msgs.append(ai_msg)
    save_history(session_id, history_msgs)

    # 用 extract_response_without_think 处理 response_text
    processed_content = extract_response_without_think(ai_msg.content)
    # 保存到向量数据库时也只存储去除<thinking>标签后的内容
    memory_manager.add_conversation_memory(
        user_id="default",
        conversation_id=session_id,
        content=processed_content.strip(),
        additional_metadata={
            "message_id": ai_msg_id,
            "timestamp": datetime.now().isoformat(),
            "type": "ai_message",
            "keyword": keyword
        }
    )

    return ai_msg_id, processed_content

def process_tool_call_message(tool_call: dict) -> AssistantToolMessage:
    """处理工具调用消息，创建并返回工具调用消息对象（不再追加到 history_msgs）"""
    function_call_msg = AssistantToolMessage(
        content="",
        id=tool_call['id'],
        tool_calls=[{
            "id": tool_call['id'],
            "type": "function",
            "function": {
                "name": tool_call['name'],
                "arguments": json.dumps(tool_call['arguments'], ensure_ascii=False) if not isinstance(tool_call['arguments'], str) else tool_call['arguments']
            }
        }]
    )
    return function_call_msg

def process_tool_response_message(tool_call: dict, tool_result: Any) -> UserToolMessage:
    """处理工具响应消息，创建并返回工具响应消息对象（不再追加到 history_msgs）"""
    tool_msg = UserToolMessage(
        tool_request=tool_call,
        content=str(tool_result),
        id=tool_call['id']
    )
    return tool_msg

async def process_tts_sentence(sentence: str, tts_engine: BaseTTS) -> dict:
    """处理单个句子的TTS合成"""
    if sentence is None or sentence == '':
        return None
    if sentence.strip() == '':
        return {'text': sentence, 'audio': None}
    try:
        # 如果TTS引擎被禁用，只返回文本
        if not tts_engine.enabled:
            return {'text': sentence, 'audio': None}
            
        audio_bytes = await tts_engine.synthesize(sentence)
        audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')
        return {'text': sentence, 'audio': audio_b64}
    except Exception as e:
        print(f"TTS合成失败: {e}")
        return {'text': sentence, 'audio': None, 'error': str(e)}

def should_generate_title(session_id: str, history_msgs: list) -> bool:
    """判断是否需要生成标题：只要当前为默认标题且有一条纯文本assistant消息即可。"""
    sessions = get_all_sessions()
    current_session = next((s for s in sessions if s['id'] == session_id), None)
    has_default_title = (
        current_session is not None and
        (
            current_session.get('name', '').startswith('New Chat')
            or '新对话' in current_session.get('name', '')
        )
    )
    has_pure_text_assistant = any(is_pure_text_assistant(msg) for msg in history_msgs)
    return has_default_title and has_pure_text_assistant

def is_pure_text_assistant(msg):
    """
    判断 assistant 消息是否为非 tool/function_call（即 tool_calls 字段不存在或为空）。
    """
    return (
        getattr(msg, "role", None) == "assistant" and not (getattr(msg, "tool_calls", None) or [])
    )

async def generate_title_for_session(session_id: str, llm_client) -> str:
    """
    工具函数：根据session_id查找最新的user和纯文本assistant消息并生成标题。
    从历史记录末尾开始向前查找，找到最近的一对非tool消息。
    """
    history = load_history(session_id)
    history_msgs = [message_factory(msg) if isinstance(msg, dict) else msg for msg in history]
    
    # 从后向前遍历，找到最近的一对非tool消息
    latest_user_msg = None
    latest_assistant_msg = None
    
    for msg in reversed(history_msgs):
        if not latest_user_msg and getattr(msg, 'role', None) == 'user':
            latest_user_msg = msg
        elif not latest_assistant_msg and is_pure_text_assistant(msg):
            latest_assistant_msg = msg
        
        # 如果找到了最近的一对消息，就停止搜索
        if latest_user_msg and latest_assistant_msg:
            break
    
    if not latest_user_msg or not latest_assistant_msg:
        return None
        
    title = await generate_conversation_title(latest_user_msg, latest_assistant_msg, llm_client)
    return title

def extract_response_without_think(response_text: str) -> str:
    """
    提取 <thinking> 标签外部的内容，只返回 LLM 给用户的最终回复。
    如果没有 <thinking> 标签，则返回原始内容。
    """
    # 移除 <thinking>...</thinking> 及其内容
    return re.sub(r'<thinking>[\s\S]*?</thinking>', '', response_text, flags=re.IGNORECASE).strip()
