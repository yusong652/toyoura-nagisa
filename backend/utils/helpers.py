import json
import base64
import asyncio
import uuid
from datetime import datetime
from backend.chat import Message
from backend.chat.utils import get_all_sessions, update_session_title, save_history
from backend.tts.base import BaseTTS
from backend.chat.title_generator import generate_conversation_title
from backend.config import get_llm_config


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
    ai_msg = Message(role="assistant", content=content)
    print(f"ai_msg: {ai_msg}")
    ai_msg_dict = ai_msg.model_dump()
    ai_msg_dict["id"] = ai_msg_id
    history_msgs.append(Message(**ai_msg_dict))
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
    """判断是否需要生成标题"""
    sessions = get_all_sessions()
    current_session = next((s for s in sessions if s['id'] == session_id), None)
    is_first_round = len(history_msgs) == 2
    has_default_title = current_session is not None
    return is_first_round and has_default_title
