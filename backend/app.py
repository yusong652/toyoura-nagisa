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
from backend.chat.utils import load_history, save_history, create_new_history, get_all_sessions, delete_history_session, delete_message, update_session_title
from backend.chat.title_generator import generate_conversation_title
import asyncio
from backend.chat.llm_factory import get_client
from backend.tts.tts_factory import get_tts_engine
from backend.config import get_llm_config
import uuid
from backend.tts.utils import split_text_by_punctuations, clean_text_for_tts


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

class DeleteMessageRequest(BaseModel):
    session_id: str
    message_id: str

# 添加新的请求模型用于标题生成
class GenerateTitleRequest(BaseModel):
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
        # 获取前端生成的消息ID和时间戳
        message_id = msg_obj.get('id')
        timestamp = msg_obj.get('timestamp')
        
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
    
    # 创建用户消息，使用前端提供的ID和时间戳
    user_msg = Message(
        role="user", 
        content=content,
        timestamp=datetime.fromtimestamp(timestamp / 1000) if timestamp else datetime.now()
    )
    # 在保存到历史记录时使用前端提供的ID (如果有)
    if message_id:
        user_msg_dict = user_msg.model_dump()
        user_msg_dict["id"] = message_id
        history_msgs.append(Message(**user_msg_dict))
    else:
        history_msgs.append(user_msg)
    
    # 使用配置中的recent_messages_length
    recent_messages_length = get_llm_config().get("recent_messages_length", 20)
    recent_msgs = history_msgs[-recent_messages_length:] if len(history_msgs) > recent_messages_length else history_msgs

    llm_client: LLMClientBase = request.app.state.llm_client
    tts_engine: BaseTTS = request.app.state.tts_engine
    
    try:
        # 首先发送"已发送"状态
        async def generate():
            # 发送"已发送"的状态确认
            yield f"data: {json.dumps({'status': 'sent'})}\n\n"
            
            try:
                # 在调用LLM之前发送"已读"状态
                yield f"data: {json.dumps({'status': 'read'})}\n\n"
                
                # 调用LLM
                response_text, keyword = await llm_client.get_response(recent_msgs)
                
                # 保存历史
                ai_msg_id = str(uuid.uuid4())  # 为AI回复生成唯一ID
                ai_msg = Message(role="assistant", content=response_text)
                ai_msg_dict = ai_msg.dict()
                ai_msg_dict["id"] = ai_msg_id  # 为AI回复添加ID
                history_msgs.append(Message(**ai_msg_dict))
                save_history(session_id, [msg.dict() for msg in history_msgs])
                
                # 首先发送关键词和AI消息ID（仅发送一次，在整个响应的开头）
                yield f"data: {json.dumps({'keyword': keyword, 'message_id': ai_msg_id})}\n\n"
                
                # 按句子分割文本之前先清理文本
                cleaned_response_text = clean_text_for_tts(response_text)
                sentences = split_text_by_punctuations(cleaned_response_text)
                
                # 逐句处理 - 注意: 我们先合成音频，再一起发送文本和音频，确保它们同步
                for sentence in sentences:
                    # 保留空行，只跳过None或空字符串
                    if sentence is None or sentence == '':
                        continue
                        
                    # 处理空行的情况，发送没有音频的行
                    if sentence.strip() == '':
                        response_data = {
                            'text': sentence,
                            'audio': None
                        }
                        yield f"data: {json.dumps(response_data)}\n\n"
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
                    
                    # 将文本和音频一起发送
                    response_data = {
                        'text': sentence,
                        'audio': audio_b64
                    }
                    
                    if audio_error:
                        response_data['error'] = audio_error
                        
                    yield f"data: {json.dumps(response_data)}\n\n"
                
                # 检查是否需要生成标题：
                # 1. 获取会话信息
                sessions = get_all_sessions()
                current_session = next((s for s in sessions if s['id'] == session_id), None)
                
                # 2. 判断是否需要生成标题
                # 仅当会话存在且恰好有2条消息（一条用户消息和一条AI回复）时生成标题
                is_first_round = len(history_msgs) == 2  # 限制为恰好2条消息
                has_default_title = current_session is not None  # 只要会话存在
                
                should_generate_title = is_first_round and has_default_title
                
                # 只在第一轮对话后生成标题
                if should_generate_title:
                    # 提取用户第一条消息的文本
                    first_user_msg = history_msgs[0]
                    first_user_text = ""
                    
                    # 解析用户消息内容
                    if isinstance(first_user_msg.content, str):
                        first_user_text = first_user_msg.content
                    elif isinstance(first_user_msg.content, list):
                        # 如果content是列表，查找text类型的内容
                        for item in first_user_msg.content:
                            if isinstance(item, dict) and "text" in item:
                                first_user_text = item["text"]
                                break
                    
                    # 生成标题
                    new_title = await generate_conversation_title(
                        first_user_text,
                        response_text,
                        llm_client
                    )
                    
                    if new_title:
                        # 更新会话标题
                        update_success = update_session_title(session_id, new_title)
                        
                        if update_success:
                            # 通过SSE流发送标题更新通知
                            title_update_data = {
                                'type': 'TITLE_UPDATE', 
                                'payload': {
                                    'session_id': session_id, 
                                    'title': new_title
                                }
                            }
                            yield f"data: {json.dumps(title_update_data)}\n\n"
                
            except Exception as e:
                # 如果在处理过程中出错，返回错误状态
                yield f"data: {json.dumps({'status': 'error', 'error': str(e)})}\n\n"
                raise e
        
        return StreamingResponse(
            generate(),
            media_type="text/event-stream"
        )
    except Exception as e:
        return ErrorResponse(detail=str(e))

@app.post("/api/messages/delete", response_model=dict)
async def delete_message_endpoint(request: DeleteMessageRequest):
    """删除指定会话中的特定消息"""
    try:
        # 验证会话ID是否存在
        sessions = get_all_sessions()
        session = next((s for s in sessions if s['id'] == request.session_id), None)
        
        if not session:
            raise HTTPException(status_code=404, detail=f"会话ID {request.session_id} 不存在")
        
        # 删除消息
        success = delete_message(request.session_id, request.message_id)
        
        if not success:
            raise HTTPException(status_code=404, detail=f"未找到消息ID {request.message_id} 或删除失败")
        
        return {
            "session_id": request.session_id,
            "message_id": request.message_id,
            "success": True,
            "message": "消息已成功删除"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除消息失败: {str(e)}")

@app.post("/api/history/generate-title", response_model=dict)
async def generate_title_endpoint(request: Request):
    """根据会话历史生成一个新的标题"""
    try:
        # 从请求体中获取会话ID
        data = await request.json()
        session_id = data.get('session_id')
        
        if not session_id:
            raise HTTPException(status_code=400, detail="请求中未提供会话ID")
            
        # 验证会话ID是否存在
        sessions = get_all_sessions()
        session = next((s for s in sessions if s['id'] == session_id), None)
        
        if not session:
            raise HTTPException(status_code=404, detail=f"会话ID {session_id} 不存在")
        
        # 加载指定会话的历史记录
        history = load_history(session_id)
        
        # 确保有足够的消息来生成标题（至少一个用户消息和一个AI响应）
        if len(history) < 2:
            raise HTTPException(status_code=400, detail="会话中的消息数量不足，无法生成标题")
        
        # 获取最新的用户消息和助手回复
        last_user_msg = None
        last_assistant_msg = None
        
        # 从后向前遍历，找到最新的消息
        for msg in reversed(history):
            if not last_assistant_msg and msg['role'] == 'assistant':
                last_assistant_msg = msg
            elif not last_user_msg and msg['role'] == 'user':
                last_user_msg = msg
            
            # 如果两种消息都找到了，就可以退出循环
            if last_user_msg and last_assistant_msg:
                break
        
        if not last_user_msg or not last_assistant_msg:
            raise HTTPException(status_code=400, detail="无法找到有效的用户消息和助手回复")
        
        # 提取文本内容
        last_user_text = ""
        last_assistant_text = ""
        
        # 处理不同格式的内容
        if isinstance(last_user_msg['content'], str):
            last_user_text = last_user_msg['content']
        elif isinstance(last_user_msg['content'], list):
            for item in last_user_msg['content']:
                if isinstance(item, dict) and "text" in item:
                    last_user_text = item["text"]
                    break
        
        if isinstance(last_assistant_msg['content'], str):
            last_assistant_text = last_assistant_msg['content']
            
        # 生成标题 - 从app state中获取llm_client
        llm_client: LLMClientBase = request.app.state.llm_client
        new_title = await generate_conversation_title(
            last_user_text,
            last_assistant_text,
            llm_client
        )
        
        if not new_title:
            raise HTTPException(status_code=500, detail="标题生成失败")
        
        # 更新会话标题
        update_success = update_session_title(session_id, new_title)
        
        if not update_success:
            raise HTTPException(status_code=500, detail="标题更新失败")
        
        return {
            "session_id": session_id,
            "title": new_title,
            "success": True
        }
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"生成标题失败: {str(e)}")