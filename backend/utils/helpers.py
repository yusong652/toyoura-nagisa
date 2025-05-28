import json
import base64
import asyncio
import uuid
from datetime import datetime
from backend.chat import Message
from backend.chat.utils import get_all_sessions, update_session_title, save_history, load_history
from backend.tts.base import BaseTTS
from backend.chat.title_generator import generate_conversation_title
from backend.config import get_llm_config
from backend.chat.models import message_factory


def parse_message_data(data: dict) -> tuple:
    """解析消息数据，返回消息内容和会话ID"""
    message_data = data.get('messageData')
    if not message_data:
        return None, data.get('session_id', "default_session")
    msg_obj = json.loads(message_data)
    text = msg_obj.get('text', '')
    files = msg_obj.get('files', [])
    message_id = msg_obj.get('id')
    timestamp = msg_obj.get('timestamp')
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
        'message_id': message_id,
        'timestamp': timestamp
    }, data.get('session_id', "default_session")

def create_user_message(parsed_data: dict) -> Message:
    """创建用户消息对象"""
    timestamp = parsed_data.get('timestamp')
    return Message(
        role="user",
        content=parsed_data['content'],
        timestamp=datetime.fromtimestamp(timestamp / 1000) if timestamp else datetime.now()
    )

def process_llm_response(response_text: str, keyword: str, history_msgs: list, session_id: str) -> str:
    """处理LLM响应，保存历史记录并返回AI消息ID"""
    ai_msg_id = str(uuid.uuid4())
    # 将关键词添加到响应文本中
    content = f"{response_text}[[{keyword}]]" if keyword else response_text
    # 直接创建带ID的消息对象
    ai_msg = Message(
        role="assistant",
        content=content,
        id=ai_msg_id
    )
    print(f"ai_msg: {ai_msg}")
    history_msgs.append(ai_msg)
    save_history(session_id, [msg.model_dump() for msg in history_msgs])
    return ai_msg_id

async def process_tts_sentence(sentence: str, tts_engine: BaseTTS) -> dict:
    """处理单个句子的TTS合成"""
    if sentence is None or sentence == '':
        return None
    if sentence.strip() == '':
        return {'text': sentence, 'audio': None}
    try:
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
    工具函数：根据session_id自动查找第一条user和第一条纯文本assistant消息并生成标题。
    """
    history = load_history(session_id)
    history_msgs = [message_factory(msg) if isinstance(msg, dict) else msg for msg in history]
    user_msg = next((msg for msg in history_msgs if getattr(msg, 'role', None) == 'user'), None)
    assistant_msg = next((msg for msg in history_msgs if is_pure_text_assistant(msg)), None)
    if not user_msg or not assistant_msg:
        return None
    title = await generate_conversation_title(user_msg, assistant_msg, llm_client)
    return title
