import os
import traceback
import json
import base64
from datetime import datetime
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from pathlib import Path
from pydantic import BaseModel
import uvicorn
from typing import Optional, Union
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from contextlib import asynccontextmanager
from .tts.remote import FishAudioTTS
from .tts.base import BaseTTS, TTSRequest
from .prompts.prompts import get_system_prompt
from .chat import LLMClientBase, ChatGPTClient, Message, ChatRequest, ChatResponse, ErrorResponse
from .chat.utils import load_history, save_history, MAX_HISTORY_MESSAGES, split_text_by_punctuations
import asyncio


# 加载环境变量
load_dotenv()

SYSTEM_PROMPT_CONTENT = get_system_prompt()

# 应用生命周期管理器
@asynccontextmanager
async def lifespan(app: FastAPI):
    tts_engine = FishAudioTTS()
    await tts_engine.initialize()
    app.state.tts_engine = tts_engine
    print("TTS Engine Initialized.")
    # 初始化 LLM Client
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OpenAI API key not found in environment variables")
    llm_client = ChatGPTClient(api_key=api_key, system_prompt=SYSTEM_PROMPT_CONTENT)
    app.state.llm_client = llm_client
    yield
    print("Shutting down TTS Engine...")
    await app.state.tts_engine.shutdown()
    print("TTS Engine Shutdown.")

app = FastAPI(lifespan=lifespan)

origins = [
    "http://localhost",
    "http://localhost:8080",
    "http://127.0.0.1",
    "http://127.0.0.1:8000",
    "null"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/api/chat", response_model=Union[ChatResponse, ErrorResponse])
async def chat_endpoint(request: Request, chat_req: ChatRequest):
    session_id = chat_req.session_id or "default_session"
    loaded_history = load_history(session_id)
    # 构建 Message 对象历史
    history_msgs = [Message(**msg) if isinstance(msg, dict) else msg for msg in loaded_history]
    # 加入本次用户消息
    user_msg = Message(role="user", content=chat_req.messageText)
    history_msgs.append(user_msg)
    # 裁剪历史
    recent_msgs = history_msgs[-MAX_HISTORY_MESSAGES:] if len(history_msgs) > MAX_HISTORY_MESSAGES else history_msgs
    # 获取 llm client
    llm_client: LLMClientBase = request.app.state.llm_client
    tts_engine: BaseTTS = request.app.state.tts_engine
    try:
        response_text, keyword = await llm_client.get_response(recent_msgs)
        # 保存历史（含本次 AI 回复）
        ai_msg = Message(role="assistant", content=response_text)
        history_msgs.append(ai_msg)
        save_history(session_id, [msg.dict() for msg in history_msgs])
        # 合成 TTS 音频
        audio_bytes = await tts_engine.synthesize(response_text)
        audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')
        return ChatResponse(response=response_text, keyword=keyword, audio_data=audio_b64)
    except Exception as e:
        return ErrorResponse(detail=str(e))

@app.post("/api/chat/stream")
async def chat_stream_endpoint(request: Request):
    data = await request.json()
    # 1. 解析 messageData
    message_data = data.get('messageData')
    if message_data:
        # 2. 反序列化
        msg_obj = json.loads(message_data)
        text = msg_obj.get('text', '')
        files = msg_obj.get('files', [])
        # 3. 处理每个文件
        for file in files:
            name = file['name']
            filetype = file['type']
            b64data = file['data']
            # 去掉前缀
            if ',' in b64data:
                b64data = b64data.split(',', 1)[1]
            file_bytes = base64.b64decode(b64data)
            # 你可以在这里做更多处理
        # 4. 继续处理text和files
        print('收到文本:', text)
        print('收到文件:', [f['name'] for f in files])
    # 构造多模态 content
    content = []
    if text:
        content.append({"type": "text", "text": text})
    for file in files:
        if file['type'].startswith('image/'):
            b64 = file['data'].split(',')[-1]
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:{file['type']};base64,{b64}"
                }
            })
    session_id = "default_session"
    loaded_history = load_history(session_id)
    history_msgs = [Message(**msg) if isinstance(msg, dict) else msg for msg in loaded_history]
    user_msg = Message(role="user", content=content)
    history_msgs.append(user_msg)
    recent_msgs = history_msgs[-MAX_HISTORY_MESSAGES:] if len(history_msgs) > MAX_HISTORY_MESSAGES else history_msgs
    
    llm_client: LLMClientBase = request.app.state.llm_client
    tts_engine: BaseTTS = request.app.state.tts_engine
    
    try:
        response_text, keyword = await llm_client.get_response(recent_msgs, model="gpt-4o")
        # 保存历史
        ai_msg = Message(role="assistant", content=response_text)
        history_msgs.append(ai_msg)
        save_history(session_id, [msg.dict() for msg in history_msgs])
        
        # 流式返回文本和音频
        async def generate():
            # 首先发送关键词
            yield f"data: {json.dumps({'keyword': keyword})}\n\n"
            
            # 按句子分割文本
            sentences = split_text_by_punctuations(response_text)
            
            # 逐句处理
            for sentence in sentences:
                # 发送文本
                yield f"data: {json.dumps({'text': sentence})}\n\n"
                
                # 合成并发送音频
                try:
                    audio_bytes = await tts_engine.synthesize(sentence)
                    audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')
                    yield f"data: {json.dumps({'audio': audio_b64})}\n\n"
                except Exception as e:
                    print(f"TTS合成失败: {e}")
                    yield f"data: {json.dumps({'audio': None, 'error': str(e)})}\n\n"
        
        return StreamingResponse(
            generate(),
            media_type="text/event-stream"
        )
    except Exception as e:
        return ErrorResponse(detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)