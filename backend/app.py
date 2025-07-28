import os
import traceback
from datetime import datetime
from fastapi import FastAPI, HTTPException, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from typing import Optional, Union, List
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from contextlib import asynccontextmanager
from backend.infrastructure.tts.base import BaseTTS, TTSRequest
from backend.infrastructure.llm import LLMClientBase, ErrorResponse
from backend.infrastructure.llm.utils import load_history, save_history, create_new_history, get_all_sessions, delete_session_data, delete_message, update_session_title, save_image_from_url, save_image_from_base64, load_all_message_history
from backend.infrastructure.llm.llm_factory import get_client
from backend.infrastructure.tts.tts_factory import get_tts_engine
from backend.config import get_llm_settings, LOCATION_DB_PATH
from backend.shared.utils.helpers import (
    parse_message_data,
    process_user_message,
    generate_title_for_session,
)
from backend.infrastructure.llm.models import message_factory
from backend.infrastructure.llm.models import (
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
from backend.infrastructure.mcp.smart_mcp_server import mcp
from fastmcp import Client, Context
import threading
from backend.infrastructure.mcp.tools.text_to_image import generate_image_from_description
from backend.presentation.api import images
from backend.infrastructure.memory.memory_manager import MemoryManager


# 加载环境变量
load_dotenv()

# ========== 导入重构后的模块 ==========
from backend.presentation.websocket.connection import ConnectionManager
from backend.presentation.streaming.handlers import generate_chat_stream

# 使用已初始化的 MCP 实例
mcp_client = Client(mcp)

# ========== 应用生命周期管理器 - 增强版 ==========
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    SOTA应用生命周期管理 - 完整的初始化和清理流程
    
    增强功能：
    1. 组件依赖管理
    2. 优雅关闭处理
    3. 错误恢复机制
    4. 资源监控
    """
    try:
        # 初始化 WebSocket 连接管理器
        connection_manager = ConnectionManager()
        app.state.connection_manager = connection_manager

        # 初始化 TTS 引擎
        tts_engine = get_tts_engine()
        await tts_engine.initialize()
        app.state.tts_engine = tts_engine
        print("[INIT] TTS Engine initialized successfully")
        
        # 初始化 LLM Client
        llm_client = get_client()
        app.state.llm_client = llm_client
        print(f"[INIT] LLM Client initialized: {type(llm_client).__name__}")
        
        # 初始化 MCP 服务器
        app.state.mcp = mcp
        mcp.app = app
        app.state.mcp_client = mcp_client
        
        # 启动 MCP SSE server（后台线程）
        mcp_thread = threading.Thread(target=lambda: mcp.run(transport="sse", port=9000), daemon=True)
        mcp_thread.start()
        print("[INIT] MCP Server started on SSE port 9000")
        
        # 验证LLM配置
        await _validate_llm_configuration()
        
        print("[INIT] All services initialized successfully")
        yield
        
    except Exception as e:
        print(f"[ERROR] Application initialization failed: {e}")
        raise
    finally:
        # 优雅关闭流程
        try:
            print("[SHUTDOWN] Starting graceful shutdown...")
            await app.state.tts_engine.shutdown()
            print("[SHUTDOWN] TTS Engine shutdown complete")
        except Exception as e:
            print(f"[ERROR] Shutdown error: {e}")

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
        recent_messages_length = get_llm_settings().recent_messages_length
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

# 注意：流式处理逻辑已移动到 backend/core/streaming.py

@app.post("/api/chat/stream")
async def chat_stream_endpoint(request: Request):
    """聊天流式端点 - 使用重构后的流式处理模块"""
    data = await request.json()
    parsed_data, session_id = parse_message_data(data)
    if not parsed_data:
        return ErrorResponse(detail="无效的消息数据")
    
    # 处理用户消息
    loaded_history = load_all_message_history(session_id)
    history_msgs = [message_factory(msg) if isinstance(msg, dict) else msg for msg in loaded_history]
    process_user_message(parsed_data, session_id, history_msgs)
    
    # 获取服务组件
    llm_client: LLMClientBase = request.app.state.llm_client
    tts_engine: BaseTTS = request.app.state.tts_engine
    
    try:
        # 使用重构后的流式处理模块
        return StreamingResponse(
            generate_chat_stream(session_id, [], llm_client, tts_engine),
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
        session_id = data.get("session_id")
        
        location_data = {
            "latitude": data.get("latitude"),
            "longitude": data.get("longitude"),
            "accuracy": data.get("accuracy"),
            "timestamp": data.get("timestamp") or int(datetime.now().timestamp()),
            "source": "browser_geolocation"
        }
        
        # Store in temporary location storage for active tool calls
        from backend.infrastructure.mcp.tools.location_tool.tool import store_temp_location
        if session_id:
            store_temp_location(session_id, location_data)
        
        print(f"[DEBUG] Browser location stored temporarily for session {session_id}: {location_data}")
        return {"success": True, "session_id": session_id}
    except Exception as e:
        print(f"[ERROR] Failed to process browser location: {e}")
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

# ========== 全局异常处理器 - SOTA架构 ==========

@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    """
    处理配置相关的值错误，特别是LLM客户端不支持的情况
    """
    error_message = str(exc)
    
    # 检查是否是LLM客户端相关的错误
    if "Unsupported LLM client" in error_message or "Unknown LLM client" in error_message:
        return JSONResponse(
            status_code=400,
            content={
                "error": "LLM Configuration Error",
                "message": error_message,
                "type": "unsupported_llm_client",
                "suggestion": "Please update your configuration to use 'gemini' as the LLM client."
            }
        )
    
    # 其他值错误
    return JSONResponse(
        status_code=400,
        content={
            "error": "Configuration Error",
            "message": error_message,
            "type": "value_error"
        }
    )

@app.exception_handler(ImportError)
async def import_error_handler(request: Request, exc: ImportError):
    """
    处理导入错误，通常是由于缺少依赖或已删除的模块引起
    """
    error_message = str(exc)
    
    # 检查是否是LLM客户端相关的导入错误
    if any(client in error_message for client in ["gpt", "anthropic", "mistral", "grok"]):
        return JSONResponse(
            status_code=500,
            content={
                "error": "LLM Client Import Error",
                "message": "Legacy LLM clients have been removed in the new architecture.",
                "type": "deprecated_client",
                "details": error_message,
                "solution": "Please configure your system to use 'gemini' as the LLM client."
            }
        )
    
    # 其他导入错误
    return JSONResponse(
        status_code=500,
        content={
            "error": "Import Error",
            "message": error_message,
            "type": "import_error"
        }
    )

# ========== 启动时验证 ==========

async def _validate_llm_configuration():
    """
    验证LLM配置，确保使用的是支持的客户端
    """
    try:
        from backend.infrastructure.llm.llm_factory import get_supported_clients, is_client_supported
        from backend.config.llm import get_llm_settings
        
        current_llm = get_llm_settings().provider
        supported_clients = get_supported_clients()
        
        if not is_client_supported(current_llm):
            print(f"❌ [STARTUP ERROR] Unsupported LLM client configured: '{current_llm}'")
            print(f"📋 Supported clients: {', '.join(supported_clients)}")
            print(f"💡 Please update your configuration to use one of the supported clients.")
            # 注意：这里不抛出异常，让应用启动，但在运行时会被工厂方法捕获
            
        else:
            print(f"✅ [STARTUP] LLM client '{current_llm}' is supported and ready")
            
    except Exception as e:
        print(f"⚠️  [STARTUP WARNING] Could not validate LLM configuration: {e}")

# ========== API ENDPOINTS - 保持不变 ==========
