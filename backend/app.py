import os
import traceback
import json
import base64
from datetime import datetime
from fastapi import FastAPI, HTTPException, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from pathlib import Path
import uvicorn
from typing import Optional, Union, List, Dict, Any, AsyncGenerator
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from contextlib import asynccontextmanager
from backend.tts.remote.fish_audio import FishAudioTTS
from backend.tts.base import BaseTTS, TTSRequest
from backend.chat import LLMClientBase, GPTClient, ErrorResponse
from backend.chat.utils import load_history, save_history, create_new_history, get_all_sessions, delete_session_data, delete_message, update_session_title, save_image_from_url, save_image_from_base64, load_all_message_history
from backend.chat.title_generator import generate_conversation_title
import asyncio
from backend.chat.llm_factory import get_client
from backend.tts.tts_factory import get_tts_engine
from backend.config import get_llm_config, LOCATION_DB_PATH
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
from backend.chat.models import Message, ResponseType, LLMResponse, UserMessage, AssistantMessage, message_factory, UserToolMessage, BaseMessage, message_factory_no_thinking
from backend.chat.models import (
    NewHistoryRequest,
    HistorySessionResponse,
    SwitchSessionRequest,
    DeleteSessionRequest,
    DeleteMessageRequest,
    GenerateTitleRequest,
    UpdateToolsEnabledRequest,
    UpdateTTSEnabledRequest,
    GenerateImageRequest
)
from backend.nagisa_mcp.smart_mcp_server import mcp
from fastmcp import Client, Context
import threading
from backend.nagisa_mcp.tools.text_to_image import generate_image_from_description
from backend.routes import images
from backend.memory.memory_manager import MemoryManager
from backend.nagisa_mcp.location_manager import get_location_manager


# 加载环境变量
load_dotenv()

# 全局防重复机制
ACTIVE_REQUESTS: Dict[str, str] = {}  # session_id -> request_id
ACTIVE_REQUESTS_LOCK = asyncio.Lock()

# WebSocket 连接管理器
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        self.active_connections[session_id] = websocket
        print(f"WebSocket connected for session: {session_id}")

    def disconnect(self, session_id: str):
        if session_id in self.active_connections:
            del self.active_connections[session_id]
            print(f"WebSocket disconnected for session: {session_id}")

    async def send_json(self, session_id: str, data: dict):
        if session_id in self.active_connections:
            try:
                await self.active_connections[session_id].send_json(data)
                print(f"Sent message to session {session_id}: {data}")
            except Exception as e:
                print(f"Failed to send message to session {session_id}: {e}")
                self.disconnect(session_id)
        else:
            print(f"No active WebSocket connection for session: {session_id}")

# 使用已初始化的 MCP 实例
mcp_client = Client(mcp)

# 应用生命周期管理器
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 初始化 WebSocket 连接管理器
    connection_manager = ConnectionManager()
    app.state.connection_manager = connection_manager

    tts_engine = get_tts_engine()
    await tts_engine.initialize()
    app.state.tts_engine = tts_engine
    print("TTS Engine Initialized.")
    # 初始化 LLM Client，传递 mcp_client 实例
    llm_client = get_client()
    app.state.llm_client = llm_client
    app.state.mcp = mcp
    # 将 FastAPI app 实例附加到 mcp 服务器实例上，以便在工具的 context 中访问
    mcp.app = app
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
        
        # 删除会话历史和元数据
        success = delete_session_data(session_id)
        
        # 清除对应session的工具缓存
        llm_client: LLMClientBase = app.state.llm_client
        if hasattr(llm_client, '_clear_session_tool_cache'):
            llm_client._clear_session_tool_cache(session_id)
            print(f"[DEBUG] Cleared tool cache for deleted session: {session_id}")
        
        # 删除向量数据库中的相关记忆
        memory_manager = MemoryManager()
        memory_manager.delete_conversation_memories(session_id)
        
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
        
        # 清除对应session的工具缓存
        llm_client: LLMClientBase = app.state.llm_client
        if hasattr(llm_client, '_clear_session_tool_cache'):
            llm_client._clear_session_tool_cache(request.session_id)
            print(f"[DEBUG] Cleared tool cache for session: {request.session_id}")
        
        # 加载指定会话的历史记录
        history = load_all_message_history(request.session_id)
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
    SOTA Enhanced LLM Response Handler - Zero Duplication for Gemini API
    
    专为Gemini API设计的响应处理器，确保：
    1. 单一控制流，零重复调用
    2. 原子性操作，完整状态管理
    3. 强力防重复机制
    4. 最优化的前端通信
    """
    # 生成唯一请求ID
    import uuid
    request_id = f"REQ_{str(uuid.uuid4())[:8]}"
    
    print(f"[REQUEST {request_id}] Starting LLM response handling")
    print(f"[REQUEST {request_id}] Session: {session_id}, Messages: {len(recent_msgs)}")
    
    # 防重复机制 - 检查是否有同会话的活跃请求
    async with ACTIVE_REQUESTS_LOCK:
        if session_id in ACTIVE_REQUESTS:
            existing_request = ACTIVE_REQUESTS[session_id]
            error_msg = f"Duplicate request detected. Session {session_id} already has active request {existing_request}"
            print(f"[REQUEST {request_id}] BLOCKED: {error_msg}")
            yield f"data: {json.dumps({'type': 'error', 'error': error_msg})}\n\n"
            return
        
        # 注册当前请求
        ACTIVE_REQUESTS[session_id] = request_id
        print(f"[REQUEST {request_id}] Registered as active request for session {session_id}")
    
    try:
        # 验证LLM客户端类型 - 只支持GeminiClient
        if type(llm_client).__name__ != 'GeminiClient':
            error_msg = f"Unsupported LLM client: {type(llm_client).__name__}. Only GeminiClient supported."
            print(f"[REQUEST {request_id}] ERROR: {error_msg}")
            yield f"data: {json.dumps({'type': 'error', 'error': error_msg})}\n\n"
            return
        
        if not hasattr(llm_client, 'execute_tool_calling_sequence'):
            error_msg = "GeminiClient missing execute_tool_calling_sequence method"
            print(f"[REQUEST {request_id}] ERROR: {error_msg}")
            yield f"data: {json.dumps({'type': 'error', 'error': error_msg})}\n\n"
            return
        
        print(f"[REQUEST {request_id}] Executing Gemini tool calling sequence")
        
        # 执行SOTA工具调用序列 - 保证零重复
        final_message, execution_metadata = await llm_client.execute_tool_calling_sequence(
            recent_msgs, 
            session_id=session_id,
            max_iterations=10
        )
        
        execution_id = execution_metadata.get('execution_id', 'unknown')
        print(f"[REQUEST {request_id}] Sequence completed. Execution ID: {execution_id}")
        
        # 处理工具调用通知
        tool_calls_executed = execution_metadata.get('tool_calls_executed', 0)
        if tool_calls_executed > 0:
            # 发送工具使用通知
            tool_notification = {
                'type': 'NAGISA_IS_USING_TOOL',
                'tool_name': 'gemini_tools',
                'action_text': f"I used {tool_calls_executed} tools to help you."
            }
            yield f"data: {json.dumps(tool_notification)}\n\n"
            
            # 短暂延迟以便前端处理
            await asyncio.sleep(0.3)
        
        # 发送工具使用结束信号
        yield f"data: {json.dumps({'type': 'NAGISA_TOOL_USE_CONCLUDED'})}\n\n"
        
        # 处理最终响应内容
        async for chunk in _process_final_response(
            final_message, session_id, tts_engine, request_id
        ):
            yield chunk
        
        # 处理标题生成
        async for chunk in _handle_title_generation(session_id, llm_client, request_id):
            yield chunk
        
        print(f"[REQUEST {request_id}] Response handling completed successfully")
        
    except Exception as e:
        print(f"[REQUEST {request_id}] CRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        
        yield f"data: {json.dumps({'type': 'NAGISA_TOOL_USE_CONCLUDED'})}\n\n"
        error_data = {
            'type': 'error',
            'error': f"LLM response processing failed: {str(e)}"
        }
        yield f"data: {json.dumps(error_data)}\n\n"
        raise e
    
    finally:
        # 清理活跃请求记录
        async with ACTIVE_REQUESTS_LOCK:
            if session_id in ACTIVE_REQUESTS and ACTIVE_REQUESTS[session_id] == request_id:
                del ACTIVE_REQUESTS[session_id]
                print(f"[REQUEST {request_id}] Cleaned up active request for session {session_id}")
            else:
                print(f"[REQUEST {request_id}] WARNING: Session {session_id} not found in active requests during cleanup")

async def _process_final_response(
    final_message: BaseMessage,
    session_id: str,
    tts_engine: BaseTTS,
    request_id: str
):
    """
    处理最终响应消息 - 原子性操作
    """
    print(f"[REQUEST {request_id}] Processing final response")
    
    if not hasattr(final_message, 'content'):
        print(f"[REQUEST {request_id}] No content in final message")
        return
    
    content = final_message.content
    
    # 提取文本内容
    text_content = ""
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict) and item.get('type') == 'text':
                text_content += item.get('text', '')
    else:
        text_content = str(content)
    
    if not text_content.strip():
        print(f"[REQUEST {request_id}] No text content to process")
        return
    
    print(f"[REQUEST {request_id}] Processing text content: {text_content[:100]}...")
    
    # 处理AI文本消息
    loaded_history = load_all_message_history(session_id)
    history_msgs = [message_factory(msg) if isinstance(msg, dict) else msg for msg in loaded_history]
    
    ai_msg_id, processed_content = process_ai_text_message(
        content,
        getattr(final_message, 'keyword', None),
        history_msgs,
        session_id
    )
    
    # 发送消息ID
    yield f"data: {json.dumps({'message_id': ai_msg_id})}\n\n"
    
    # 发送关键词
    if hasattr(final_message, 'keyword') and final_message.keyword:
        yield f"data: {json.dumps({'keyword': final_message.keyword})}\n\n"
    
    # 处理TTS
    async for chunk in _process_tts_content(processed_content, tts_engine, request_id):
        yield chunk

async def _process_tts_content(
    content: str,
    tts_engine: BaseTTS,
    request_id: str
):
    """
    处理TTS内容 - 原子性操作
    """
    print(f"[REQUEST {request_id}] Processing TTS content")
    
    # 处理表情和颜文字
    text_with_placeholders, kaomoji_list, emoji_list = extract_and_replace_emoticons(content)
    
    # 分句处理
    sentences = split_text_by_punctuations(text_with_placeholders)
    
    for i, sentence in enumerate(sentences):
        tts_text = clean_text_for_tts(sentence)
        tts_result = await process_tts_sentence(tts_text, tts_engine)
        
        if tts_result:
            tts_result['text'] = restore_emoticons(sentence, kaomoji_list, emoji_list)
            yield f"data: {json.dumps(tts_result)}\n\n"
            print(f"[REQUEST {request_id}] Sent TTS chunk {i+1}/{len(sentences)}")

async def _handle_title_generation(
    session_id: str,
    llm_client: LLMClientBase,
    request_id: str
):
    """
    处理标题生成 - 原子性操作
    """
    try:
        print(f"[REQUEST {request_id}] Checking title generation eligibility")
        
        loaded_history = load_all_message_history(session_id)
        history_msgs = [message_factory(msg) if isinstance(msg, dict) else msg for msg in loaded_history]
        
        if should_generate_title(session_id, history_msgs):
            print(f"[REQUEST {request_id}] Generating title")
            
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
                    print(f"[REQUEST {request_id}] Title generated: {new_title}")
        else:
            print(f"[REQUEST {request_id}] Title generation not needed")
            
    except Exception as e:
        print(f"[REQUEST {request_id}] Title generation failed: {e}")
        # 不抛出异常，标题生成失败不应影响主流程

@app.post("/api/chat/stream")
async def chat_stream_endpoint(request: Request):
    data = await request.json()
    parsed_data, session_id = parse_message_data(data)
    if not parsed_data:
        return ErrorResponse(detail="无效的消息数据")
    # 使用 load_all_message_history 来保存完整的消息历史
    loaded_history = load_all_message_history(session_id)
    history_msgs = [message_factory(msg) if isinstance(msg, dict) else msg for msg in loaded_history]
    user_msg = process_user_message(parsed_data, session_id, history_msgs)
    llm_client: LLMClientBase = request.app.state.llm_client
    tts_engine: BaseTTS = request.app.state.tts_engine
    try:
        async def generate():
            # Generate unique request ID for debugging
            import uuid
            request_id = str(uuid.uuid4())[:8]
            print(f"[DEBUG] API Request {request_id} started - Session: {session_id}")
            
            yield f"data: {json.dumps({'status': 'sent'})}\n\n"
            try:
                yield f"data: {json.dumps({'status': 'read'})}\n\n"
                # 使用 load_history 获取不含图片消息的最近对话
                recent_history = load_history(session_id) # load history without image
                # 使用 message_factory_no_thinking 创建历史消息，过滤掉 thinking 块
                recent_msgs = [message_factory_no_thinking(msg) if isinstance(msg, dict) else msg for msg in recent_history]
                recent_messages_length = get_llm_config().get("recent_messages_length", 20)
                recent_msgs = recent_msgs[-recent_messages_length:]
                
                print(f"[DEBUG] API Request {request_id} - Calling handle_llm_response")
                async for chunk in handle_llm_response(recent_msgs, session_id, llm_client, tts_engine):
                    yield chunk
                print(f"[DEBUG] API Request {request_id} - handle_llm_response completed")
            except Exception as e:
                print(f"[ERROR] API Request {request_id} - Exception in generate(): {e}")
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

@app.post("/api/chat/tts-enabled", response_model=dict)
async def update_tts_enabled(request: UpdateTTSEnabledRequest):
    """更新TTS引擎的enabled状态"""
    try:
        print(f"[DEBUG] /api/chat/tts-enabled received enabled: {request.enabled} (type: {type(request.enabled)})")
        tts_engine: BaseTTS = app.state.tts_engine
        tts_engine.enabled = request.enabled
        return {
            "success": True,
            "tts_enabled": request.enabled
        }
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"更新TTS状态失败: {str(e)}")

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
        print(f"[DEBUG] Generating image for session {session_id}")
        print(f"[DEBUG] Text prompt: {prompt_result['text_prompt'][:100]}...")
        print(f"[DEBUG] Negative prompt: {prompt_result['negative_prompt'][:100]}...")
        
        image_result = await generate_image_from_description(
            prompt=prompt_result["text_prompt"],
            negative_prompt=prompt_result["negative_prompt"]
        )
        
        print(f"[DEBUG] Image generation result type: {type(image_result)}")
        print(f"[DEBUG] Image generation result keys: {list(image_result.keys()) if isinstance(image_result, dict) else 'Not a dict'}")
        
        if not image_result:
            print("[ERROR] Image generation returned empty result")
            return {"success": False, "error": "Image generation failed."}
        
        # 3. Check for error type first
        if image_result.get("type") == "error":
            error_message = image_result.get("message", "Unknown error occurred during image generation")
            print(f"[ERROR] Image generation failed: {error_message}")
            return {"success": False, "error": error_message}
        
        # 4. Save image to session folder based on result type
        local_path = None
        if image_result.get("type") == "image_url" and image_result.get("image_url"):
            print("[DEBUG] Processing image_url result type")
            local_path = save_image_from_url(image_result["image_url"], session_id)
        elif image_result.get("type") == "image_base64" and image_result.get("image"):
            print("[DEBUG] Processing image_base64 result type")
            print(f"[DEBUG] Base64 data length: {len(image_result['image'])}")
            try:
                local_path = save_image_from_base64(image_result["image"], session_id)
                print(f"[DEBUG] Successfully saved base64 image to: {local_path}")
            except Exception as e:
                print(f"[ERROR] Failed to save base64 image in endpoint: {e}")
                return {"success": False, "error": f"Failed to save image: {str(e)}"}
        else:
            print(f"[ERROR] Unknown image result type: {image_result.get('type')}")
            print(f"[ERROR] Available keys in result: {list(image_result.keys())}")
            return {"success": False, "error": f"Unknown result type: {image_result.get('type')}"}
        
        if not local_path:
            print("[ERROR] No local path returned from image saving")
            return {"success": False, "error": "Failed to save generated image."}
        
        print(f"[DEBUG] Image successfully processed and saved to: {local_path}")
        return {"success": True, "image_path": local_path}
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return {"success": False, "error": str(e)}

@app.post("/api/location/update")
async def update_browser_location(request: Request):
    """接收前端发送的浏览器位置信息"""
    try:
        data = await request.json()
        session_id = data.get("session_id")  # 获取session_id
        
        location_data = {
            "latitude": data.get("latitude"),
            "longitude": data.get("longitude"),
            "accuracy": data.get("accuracy"),
            "timestamp": data.get("timestamp") or int(datetime.now().timestamp()),
            "source": "browser_geolocation"
        }
        
        # 更新位置管理器
        location_manager = get_location_manager()
        location_manager.update_location(
            session_id=session_id or "global",
            data=location_data
        )
        
        print(f"[DEBUG] Browser location updated for session {session_id}: {location_data}")
        return {"success": True, "session_id": session_id}
    except Exception as e:
        print(f"[ERROR] Failed to update browser location: {e}")
        return {"success": False, "error": str(e)}

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """为每个客户端会话建立 WebSocket 连接。"""
    connection_manager: ConnectionManager = websocket.app.state.connection_manager
    await connection_manager.connect(websocket, session_id)
    try:
        while True:
            # 保持连接开放以接收后端推送
            await websocket.receive_text()
    except WebSocketDisconnect:
        connection_manager.disconnect(session_id)
