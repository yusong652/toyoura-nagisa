import os
import traceback
import json
import base64
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path
from pydantic import BaseModel
import uvicorn
from typing import Optional, Union
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from contextlib import asynccontextmanager
from .tts.remote import FishSpeechTTS
from .tts.base import BaseTTS, TTSRequest
from .prompts.prompts import get_system_prompt
from .chat import ChatGPTClient, Message, ChatRequest, ChatResponse, ErrorResponse


# 加载环境变量
load_dotenv()

SYSTEM_PROMPT_CONTENT = get_system_prompt()

# 聊天历史相关工具
HISTORY_FILE = "backend/data/chat_history.json"
MAX_HISTORY_MESSAGES = 20

def load_history(session_id: str) -> list:
    try:
        if not os.path.exists(HISTORY_FILE):
            return []
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            all_history = json.load(f)
            return all_history.get(session_id, [])
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def save_history(session_id: str, current_history: list):
    os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
    try:
        all_history = {}
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                try:
                    all_history = json.load(f)
                except json.JSONDecodeError:
                    all_history = {}
        all_history[session_id] = current_history
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(all_history, f, indent=4, ensure_ascii=False)
    except IOError as e:
        print(f"Error saving history: {e}")

# 应用生命周期管理器
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Initializing TTS Engine...")
    tts_engine = FishSpeechTTS()
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
    llm_client: ChatGPTClient = request.app.state.llm_client
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

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)