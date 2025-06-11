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
from typing import Optional, Union, List, Dict, Any, AsyncGenerator
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from contextlib import asynccontextmanager
from backend.tts.remote.fish_audio import FishAudioTTS
from backend.tts.base import BaseTTS, TTSRequest
from backend.chat import LLMClientBase, GPTClient, ChatRequest, ChatResponse, ErrorResponse
from backend.chat.utils import load_history, save_history, create_new_history, get_all_sessions, delete_session_data, delete_message, update_session_title, save_image_from_url, load_all_message_history
from backend.chat.title_generator import generate_conversation_title
import asyncio
from backend.chat.llm_factory import get_client
from backend.tts.tts_factory import get_tts_engine
from backend.config import get_llm_config
import uuid
from backend.tts.utils import split_text_by_punctuations, clean_text_for_tts, extract_and_replace_emoticons, restore_emoticons
from backend.utils.helpers import (
    parse_message_data,
    process_user_message,
    process_ai_text_message,
    process_tool_call_message,
    process_tool_response_message,
    process_tts_sentence,
    should_generate_title,
    is_pure_text_assistant,
    generate_title_for_session,
)
from backend.chat.models import Message, ResponseType, LLMResponse, UserMessage, AssistantMessage, message_factory, UserToolMessage, BaseMessage
from backend.nagisa_mcp.fast_mcp_server import mcp
from fastmcp import Client, Context
import threading
from backend.nagisa_mcp.tools.text_to_image import generate_image_from_description
from backend.routes import images


# 加载环境变量
load_dotenv()

# 使用已初始化的 MCP 实例
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

app.include_router(images.router)

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

class UpdateToolsEnabledRequest(BaseModel):
    enabled: bool

class GenerateImageRequest(BaseModel):
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
        history = load_all_message_history(session_id)
        history_msgs = [message_factory(msg) if isinstance(msg, dict) else msg for msg in history]
        
        return {
            "session": session,
            "history": [msg.model_dump() | {"role": msg.role} for msg in history_msgs],
            "message_count": len(history_msgs)
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
        success = delete_session_data(session_id)
        
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
        print(f"Delete session error: {e}")
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
        history_msgs = [message_factory(msg) if isinstance(msg, dict) else msg for msg in history]
        
        # 返回会话信息和最近的消息
        recent_messages_length = get_llm_config().get("recent_messages_length", 5)
        recent_messages = history_msgs[-recent_messages_length:] if len(history_msgs) > recent_messages_length else history_msgs
        
        return {
            "session_id": request.session_id,
            "success": True,
            "message_count": len(history_msgs),
            "recent_messages": [msg.model_dump() | {"role": msg.role} for msg in recent_messages]
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"切换会话失败: {str(e)}")

async def handle_llm_response(
    recent_msgs: List[BaseMessage],
    session_id: str,
    llm_client: LLMClientBase,
    tts_engine: BaseTTS
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    处理 LLM 的响应，包括普通文本回复和工具调用。
    对于文生图工具，会先生成提示词，然后再调用文生图工具。
    """
    llm_response = await llm_client.get_response(recent_msgs)
    print(f"[DEBUG] llm_response type: {llm_response.response_type}")
    
    if llm_response.response_type == ResponseType.FUNCTION_CALL:
        # 创建包含所有工具调用的消息
        tool_calls_msg = message_factory({
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": tool_call['id'],
                    "type": "function",
                    "function": {
                        "name": tool_call['name'],
                        "arguments": json.dumps(tool_call['arguments'])
                    }
                }
                for tool_call in llm_response.tool_calls
            ]
        })
        recent_msgs.append(tool_calls_msg)
        
        # 处理所有工具调用
        for tool_call in llm_response.tool_calls:
            # 发送工具使用开始状态
            tool_state = {
                'type': 'NAGISA_IS_USING_TOOL',
                'tool_name': tool_call['name'],
                'action_text': f"I'll use the {tool_call['name']} tool to help you."
            }
            yield f"data: {json.dumps(tool_state)}\n\n"

            # 处理函数调用结果，传入 session_id
            tool_result = await llm_client.handle_function_call(tool_call, session_id)

            # Special handling for generate_image
            if tool_call['name'] == "generate_image":
                if isinstance(tool_result, dict) and tool_result.get("type") == "image_url" and tool_result.get("image_url"):
                    image_url = tool_result["image_url"]
                    local_path = save_image_from_url(image_url, session_id)
                    tool_natural_response = "The image has been generated and saved to your session."
                    # 发送会话刷新信号
                    refresh_signal = {
                        'type': 'SESSION_REFRESH',
                        'payload': {
                            'session_id': session_id,
                            'message': 'Image generated, please refresh session'
                        }
                    }
                    yield f"data: {json.dumps(refresh_signal)}\n\n"
                    # 添加短暂延迟，确保前端有足够时间处理图片消息
                    await asyncio.sleep(0.5)
                else:
                    tool_natural_response = "Image generation failed, please try again."
            else:
                tool_natural_response = str(tool_result)

            # 添加工具响应消息
            tool_response_msg = message_factory({
                "role": "tool",
                "tool_call_id": tool_call['id'],
                "name": tool_call['name'],
                "content": tool_natural_response
            })
            print(f"[DEBUG] tool_response_msg: {tool_response_msg.model_dump()}")
            recent_msgs.append(tool_response_msg)

        # 所有工具调用完成后，获取最终响应
        async for chunk in handle_llm_response(recent_msgs, session_id, llm_client, tts_engine):
            yield chunk
        return
        
    elif llm_response.response_type == ResponseType.TEXT:
        yield f"data: {json.dumps({'type': 'NAGISA_TOOL_USE_CONCLUDED'})}\n\n"
        # 使用新的消息处理器处理AI文本消息，使用原始的history_msgs而不是recent_msgs
        loaded_history = load_all_message_history(session_id)
        history_msgs = [message_factory(msg) if isinstance(msg, dict) else msg for msg in loaded_history]
        ai_msg_id, _ = process_ai_text_message(
            llm_response.content,
            llm_response.keyword,
            history_msgs,
            session_id
        )
        # 发送消息ID
        yield f"data: {json.dumps({'message_id': ai_msg_id})}\n\n"
        # 发送关键词
        if llm_response.keyword:
            yield f"data: {json.dumps({'keyword': llm_response.keyword})}\n\n"
        # 新增：表情/颜文字占位处理
        text_with_placeholders, kaomoji_list, emoji_list = extract_and_replace_emoticons(llm_response.content)
        # 分句用占位符文本
        sentences = split_text_by_punctuations(text_with_placeholders)
        for sentence in sentences:
            tts_text = clean_text_for_tts(sentence)
            tts_result = await process_tts_sentence(tts_text, tts_engine)
            if tts_result:
                tts_result['text'] = restore_emoticons(sentence, kaomoji_list, emoji_list)  # 确保占位符能正确匹配
                yield f"data: {json.dumps(tts_result)}\n\n"
        # ------ 标题生成判断逻辑移动到这里 ------
        try:
            loaded_history = load_history(session_id)
            history_msgs_after = [message_factory(msg) if isinstance(msg, dict) else msg for msg in loaded_history]
            if should_generate_title(session_id, history_msgs_after):
                new_title = await generate_title_for_session(session_id, llm_client)
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
            print(f"Title generation failed: {str(e)}")
            # 在流式响应中，我们只记录错误而不抛出异常
            error_data = {
                'type': 'error',
                'error': f"Title generation failed: {str(e)}"
            }
            yield f"data: {json.dumps(error_data)}\n\n"
    elif llm_response.response_type == ResponseType.ERROR:
        yield f"data: {json.dumps({'type': 'NAGISA_TOOL_USE_CONCLUDED'})}\n\n"
        error_data = {
            'type': 'error',
            'error': llm_response.content
        }
        yield f"data: {json.dumps(error_data)}\n\n"

@app.post("/api/chat/stream")
async def chat_stream_endpoint(request: Request):
    data = await request.json()
    parsed_data, session_id = parse_message_data(data)
    if not parsed_data:
        return ErrorResponse(detail="无效的消息数据")
    loaded_history = load_history(session_id)
    history_msgs = [message_factory(msg) if isinstance(msg, dict) else msg for msg in loaded_history]
    user_msg = process_user_message(parsed_data)
    history_msgs.append(user_msg)
    # 保存用户消息到历史记录
    save_history(session_id, history_msgs)
    llm_client: LLMClientBase = request.app.state.llm_client
    tts_engine: BaseTTS = request.app.state.tts_engine
    try:
        async def generate():
            yield f"data: {json.dumps({'status': 'sent'})}\n\n"
            try:
                yield f"data: {json.dumps({'status': 'read'})}\n\n"
                # 只在这里切片 recent_msgs
                recent_messages_length = get_llm_config().get("recent_messages_length", 20)
                recent_msgs = history_msgs[-recent_messages_length:]
                async for chunk in handle_llm_response(recent_msgs, session_id, llm_client, tts_engine):
                    yield chunk
            except Exception as e:
                yield f"data: {json.dumps({'type': 'NAGISA_TOOL_USE_CONCLUDED'})}\n\n"
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
        data = await request.json()
        session_id = data.get('session_id')
        if not session_id:
            raise HTTPException(status_code=400, detail="请求中未提供会话ID")
        sessions = get_all_sessions()
        session = next((s for s in sessions if s['id'] == session_id), None)
        if not session:
            raise HTTPException(status_code=404, detail=f"会话ID {session_id} 不存在")
        llm_client: LLMClientBase = request.app.state.llm_client
        new_title = await generate_title_for_session(session_id, llm_client)
        if new_title is None:
            raise HTTPException(status_code=400, detail="No valid user message or pure text assistant message found for title generation.")
        if not new_title:
            raise HTTPException(status_code=500, detail="标题生成失败")
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

@app.post("/api/chat/tools-enabled", response_model=dict)
async def update_tools_enabled(request: UpdateToolsEnabledRequest):
    """更新LLM客户端的tools_enabled状态"""
    try:
        print(f"[DEBUG] /api/chat/tools-enabled received enabled: {request.enabled} (type: {type(request.enabled)})")
        llm_client: LLMClientBase = app.state.llm_client
        llm_client.update_config(tools_enabled=request.enabled)
        return {
            "success": True,
            "tools_enabled": request.enabled
        }
    except Exception as e:
        import traceback
        print(traceback.format_exc())  # 打印详细堆栈
        raise HTTPException(status_code=500, detail=f"更新工具状态失败: {str(e)}")

@app.post("/api/generate-image", response_model=dict)
async def generate_image_endpoint(request: GenerateImageRequest):
    """One-click generate image from recent session messages."""
    try:
        session_id = request.session_id
        llm_client: LLMClientBase = app.state.llm_client
        # 1. Generate prompts from LLM client
        prompt_result = await llm_client.generate_text_to_image_prompt(session_id)
        if not prompt_result:
            return {"success": False, "error": "Failed to generate image prompts from conversation."}
        # 2. Generate image from description
        image_result = await generate_image_from_description(
            prompt=prompt_result["text_prompt"],
            negative_prompt=prompt_result["negative_prompt"]
        )
        if not image_result or not image_result.get("image_url"):
            return {"success": False, "error": "Image generation failed."}
        # 3. Save image to session folder
        local_path = save_image_from_url(image_result["image_url"], session_id)
        return {"success": True, "image_path": local_path}
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return {"success": False, "error": str(e)}
