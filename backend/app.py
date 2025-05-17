import os
import traceback
import json
import base64
from datetime import datetime
from fastapi import FastAPI, HTTPException, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from pathlib import Path
from pydantic import BaseModel
import uvicorn
from typing import Optional, Union, List
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from contextlib import asynccontextmanager
from backend.tts.remote.fish_audio import FishAudioTTS
from backend.tts.base import BaseTTS, TTSRequest
from backend.chat import LLMClientBase, GPTClient, Message, ChatRequest, ChatResponse, ErrorResponse
from backend.chat.utils import load_history, save_history, split_text_by_punctuations, create_new_history, get_all_sessions, delete_history_session
import asyncio
from backend.chat.llm_factory import get_client
from backend.tts.tts_factory import get_tts_engine
from backend.config import get_llm_config


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

# 新增历史记录相关模型
class NewHistoryRequest(BaseModel):
    name: Optional[str] = None

class HistorySessionResponse(BaseModel):
    id: str
    name: str
    created_at: str
    updated_at: str

class SwitchSessionRequest(BaseModel):
    session_id: str

class DeleteSessionRequest(BaseModel):
    session_id: str

@app.post("/api/history/create", response_model=dict)
async def create_history_endpoint(request: NewHistoryRequest):
    """创建新的聊天历史记录"""
    try:
        session_id = create_new_history(request.name)
        return {"session_id": session_id, "success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建历史记录失败: {str(e)}")

@app.get("/api/history/sessions", response_model=List[dict])
async def get_history_sessions():
    """获取所有可用的聊天会话"""
    try:
        sessions = get_all_sessions()
        return sessions
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取会话列表失败: {str(e)}")

@app.get("/api/history/{session_id}", response_model=dict)
async def get_session_history(session_id: str):
    """获取指定会话的完整历史记录"""
    try:
        # 验证会话ID是否存在
        sessions = get_all_sessions()
        session = next((s for s in sessions if s['id'] == session_id), None)
        
        if not session:
            raise HTTPException(status_code=404, detail=f"会话ID {session_id} 不存在")
        
        # 加载指定会话的历史记录
        history = load_history(session_id)
        
        return {
            "session": session,
            "history": history,
            "message_count": len(history)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取会话历史记录失败: {str(e)}")

@app.delete("/api/history/{session_id}", response_model=dict)
async def delete_session(session_id: str):
    """删除指定的聊天会话"""
    try:
        # 验证会话ID是否存在
        sessions = get_all_sessions()
        session = next((s for s in sessions if s['id'] == session_id), None)
        
        if not session:
            raise HTTPException(status_code=404, detail=f"会话ID {session_id} 不存在")
        
        # 删除会话
        success = delete_history_session(session_id)
        
        if not success:
            raise HTTPException(status_code=500, detail=f"删除会话 {session_id} 失败")
        
        return {
            "session_id": session_id,
            "success": True,
            "message": f"会话 '{session.get('name', session_id)}' 已成功删除"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除会话失败: {str(e)}")

@app.post("/api/history/switch", response_model=dict)
async def switch_session(request: SwitchSessionRequest):
    """切换到指定的聊天会话"""
    try:
        # 验证会话ID是否存在
        sessions = get_all_sessions()
        session_exists = any(session['id'] == request.session_id for session in sessions)
        
        if not session_exists:
            raise HTTPException(status_code=404, detail=f"会话ID {request.session_id} 不存在")
        
        # 加载指定会话的历史记录
        history = load_history(request.session_id)
        
        # 返回会话信息和最近的消息
        recent_messages_length = get_llm_config().get("recent_messages_length", 5)
        recent_messages = history[-recent_messages_length:] if len(history) > recent_messages_length else history
        
        return {
            "session_id": request.session_id,
            "success": True,
            "message_count": len(history),
            "recent_messages": recent_messages
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"切换会话失败: {str(e)}")

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
    # 获取会话ID，如果没有提供则使用默认会话
    session_id = data.get('session_id', "default_session")
    loaded_history = load_history(session_id)
    history_msgs = [Message(**msg) if isinstance(msg, dict) else msg for msg in loaded_history]
    user_msg = Message(role="user", content=content)
    history_msgs.append(user_msg)
    
    # 使用配置中的recent_messages_length
    recent_messages_length = get_llm_config().get("recent_messages_length", 20)
    recent_msgs = history_msgs[-recent_messages_length:] if len(history_msgs) > recent_messages_length else history_msgs

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
            # 首先发送关键词（仅发送一次，在整个响应的开头）
            yield f"data: {json.dumps({'keyword': keyword})}\n\n"
            
            # 按句子分割文本
            sentences = split_text_by_punctuations(response_text)
            
            # 逐句处理 - 注意: 我们先合成音频，再一起发送文本和音频，确保它们同步
            for sentence in sentences:
                if not sentence.strip():
                    continue
                    
                # 先合成音频
                audio_b64 = None
                audio_error = None
                try:
                    audio_bytes = await tts_engine.synthesize(sentence)
                    audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')
                except Exception as e:
                    print(f"TTS合成失败: {e}")
                    audio_error = str(e)
                
                # 将文本和音频一起发送，不再包含关键词
                response_data = {
                    'text': sentence,
                    'audio': audio_b64
                }
                
                if audio_error:
                    response_data['error'] = audio_error
                    
                yield f"data: {json.dumps(response_data)}\n\n"
        
        return StreamingResponse(
            generate(),
            media_type="text/event-stream"
        )
    except Exception as e:
        return ErrorResponse(detail=str(e))