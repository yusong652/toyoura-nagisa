import os
import traceback
import json
import base64
from datetime import datetime
from fastapi import FastAPI, HTTPException, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from pathlib import Path
from pydantic import BaseModel
import uvicorn
from typing import Optional, Union
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from contextlib import asynccontextmanager
from .tts.remote.fish_audio import FishAudioTTS
from .tts.base import BaseTTS, TTSRequest
from .chat import LLMClientBase, GPTClient, Message, ChatRequest, ChatResponse, ErrorResponse
from .chat.utils import load_history, save_history, MAX_HISTORY_MESSAGES, split_text_by_punctuations
import asyncio
from .chat.llm_factory import get_client
from .tts.tts_factory import get_tts_engine


# 加载环境变量
load_dotenv()

# 应用生命周期管理器
@asynccontextmanager
async def lifespan(app: FastAPI):
    tts_engine = get_tts_engine()
    await tts_engine.initialize()
    app.state.tts_engine = tts_engine
    print("TTS Engine Initialized.")
    # 初始化 LLM Client
    llm_client = get_client()
    app.state.llm_client = llm_client
    yield
    print("Shutting down TTS Engine...")
    await app.state.tts_engine.shutdown()
    print("TTS Engine Shutdown.")

app = FastAPI(lifespan=lifespan)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
        # # 3. 处理每个文件
        # for file in files:
        #     name = file['name']
        #     filetype = file['type']
        #     b64data = file['data']
        #     # 去掉前缀
        #     if ',' in b64data:
        #         b64data = b64data.split(',', 1)[1]
        #     file_bytes = base64.b64decode(b64data)
        #     # 可以在这里做更多处理
        # 4. 继续处理text和files
        print('收到文本:', text)
        print('收到文件:', [f['name'] for f in files])
    # 构造多模态 content
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
    session_id = "default_session"
    loaded_history = load_history(session_id)
    history_msgs = [Message(**msg) if isinstance(msg, dict) else msg for msg in loaded_history]
    user_msg = Message(role="user", content=content)
    history_msgs.append(user_msg)
    recent_msgs = history_msgs[-MAX_HISTORY_MESSAGES:] if len(history_msgs) > MAX_HISTORY_MESSAGES else history_msgs

    llm_client: LLMClientBase = request.app.state.llm_client
    tts_engine: BaseTTS = request.app.state.tts_engine
    
    try:
        response_text, keyword = await llm_client.get_response(recent_msgs)
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