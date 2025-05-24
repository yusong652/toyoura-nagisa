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
from backend.utils.helpers import (
    parse_message_data,
    create_user_message,
    process_llm_response,
    process_tts_sentence,
    should_generate_title
)
from backend.chat.models import Message, ResponseType, LLMResponse
from fastmcp import FastMCP, Client
from backend.nagisa_mcp.common_tools import register_common_tools
import threading


# 加载环境变量
load_dotenv()

# Initialize MCP server and register tools
mcp = FastMCP("Nagisa MCP Server", instructions="You can call get_weather, get_current_time, etc.")
register_common_tools(mcp)
mcp_client = Client(mcp)

# 应用生命周期管理器
@asynccontextmanager
async def lifespan(app: FastAPI):
    tts_engine = get_tts_engine()
    await tts_engine.initialize()
    app.state.tts_engine = tts_engine
    print("TTS Engine Initialized.")
    # 初始化 LLM Client，传递 mcp_client 实例
    llm_client = get_client(mcp_client=mcp_client)
    app.state.llm_client = llm_client
    app.state.mcp = mcp
    app.state.mcp_client = mcp_client
    # 启动 MCP SSE server（如需对外暴露）
    mcp_thread = threading.Thread(target=lambda: mcp.run(transport="sse", port=9000), daemon=True)
    mcp_thread.start()
    print("MCP Server Initialized and running on SSE port 9000.")
    yield
    print("Shutting down TTS Engine...")
    await app.state.tts_engine.shutdown()
    print("TTS Engine Shutdown.")
    # MCP server will exit with main process

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
    
    # 1. 解析消息数据
    parsed_data, session_id = parse_message_data(data)
    if not parsed_data:
        return ErrorResponse(detail="无效的消息数据")
        
    # 2. 加载历史记录
    loaded_history = load_history(session_id)
    history_msgs = [Message(**msg) if isinstance(msg, dict) else msg for msg in loaded_history]
    
    # 3. 创建并添加用户消息
    user_msg = create_user_message(parsed_data)
    if parsed_data.get('message_id'):
        user_msg_dict = user_msg.model_dump()
        user_msg_dict["id"] = parsed_data['message_id']
        history_msgs.append(Message(**user_msg_dict))
    else:
        history_msgs.append(user_msg)
    
    # 4. 获取最近的对话历史
    recent_messages_length = get_llm_config().get("recent_messages_length", 20)
    recent_msgs = history_msgs[-recent_messages_length:] if len(history_msgs) > recent_messages_length else history_msgs

    llm_client: LLMClientBase = request.app.state.llm_client
    tts_engine: BaseTTS = request.app.state.tts_engine
    
    try:
        async def generate():
            # 发送"已发送"的状态确认
            yield f"data: {json.dumps({'status': 'sent'})}\n\n"
            
            try:
                # 发送"已读"状态
                yield f"data: {json.dumps({'status': 'read'})}\n\n"
                
                # 调用LLM获取响应
                llm_response = await llm_client.get_response(recent_msgs)
                
                # 处理不同类型的响应
                print(f"[DEBUG] llm_response type: {llm_response.response_type}")
                if llm_response.response_type == ResponseType.FUNCTION_CALL:
                    # 处理函数调用结果
                    tool_call = {
                        'name': llm_response.function_name,
                        'arguments': llm_response.function_args,
                        'id': getattr(llm_response, 'function_call_id', 'tool_call_id')
                    }
                    # 这里要主动调用工具
                    tool_result = await llm_client.handle_function_call(tool_call)
                    # 闭环
                    final_llm_response = await llm_client.handle_function_call_closed_loop(
                        history_msgs,
                        tool_call,
                        tool_result
                    )
                    ai_msg_id = process_llm_response(
                        final_llm_response.content,
                        final_llm_response.keyword,
                        history_msgs,
                        session_id
                    )
                    # 流式输出闭环回复
                    sentences = split_text_by_punctuations(final_llm_response.content)
                    for sentence in sentences:
                        if sentence.strip():
                            # 1. 文本 chunk
                            text_data = {
                                'type': 'text',
                                'content': sentence,
                                'keyword': final_llm_response.keyword,
                                'message_id': ai_msg_id
                            }
                            yield f"data: {json.dumps(text_data)}\n\n"
                            # 2. TTS 音频 chunk
                            tts_result = await process_tts_sentence(sentence, tts_engine)
                            if tts_result:
                                yield f"data: {json.dumps(tts_result)}\n\n"
                    
                elif llm_response.response_type == ResponseType.TEXT:
                    # 处理普通文本响应
                    ai_msg_id = process_llm_response(
                        llm_response.content,
                        llm_response.keyword,
                        history_msgs,
                        session_id
                    )
                    
                    # 发送文本响应
                    text_data = {
                        'type': 'text',
                        'content': llm_response.content,
                        'keyword': llm_response.keyword,
                        'message_id': ai_msg_id
                    }
                    yield f"data: {json.dumps(text_data)}\n\n"
                    
                    # 处理TTS合成
                    cleaned_response_text = clean_text_for_tts(llm_response.content)
                    sentences = split_text_by_punctuations(cleaned_response_text)
                    
                    for sentence in sentences:
                        tts_result = await process_tts_sentence(sentence, tts_engine)
                        if tts_result:
                            yield f"data: {json.dumps(tts_result)}\n\n"
                    
                elif llm_response.response_type == ResponseType.ERROR:
                    error_data = {
                        'type': 'error',
                        'error': llm_response.content
                    }
                    yield f"data: {json.dumps(error_data)}\n\n"
                
                # 处理标题生成
                if should_generate_title(session_id, history_msgs):
                    first_user_msg = history_msgs[0]
                    first_assistant_msg = history_msgs[1]
                    new_title = await generate_conversation_title(
                        first_user_msg,
                        first_assistant_msg,
                        llm_client
                    )
                    
                    if new_title:
                        update_success = update_session_title(session_id, new_title)
                        if update_success:
                            title_update_data = {
                                'type': 'TITLE_UPDATE',
                                'payload': {
                                    'session_id': session_id,
                                    'title': new_title
                                }
                            }
                            yield f"data: {json.dumps(title_update_data)}\n\n"
                
            except Exception as e:
                error_data = {
                    'type': 'error',
                    'error': str(e)
                }
                yield f"data: {json.dumps(error_data)}\n\n"
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
        
        # 转换为 Message 对象
        if isinstance(last_user_msg, dict):
            last_user_msg = Message(**last_user_msg)
        if isinstance(last_assistant_msg, dict):
            last_assistant_msg = Message(**last_assistant_msg)

        # 生成标题 - 从app state中获取llm_client
        llm_client: LLMClientBase = request.app.state.llm_client
        new_title = await generate_conversation_title(
            last_user_msg,
            last_assistant_msg,
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