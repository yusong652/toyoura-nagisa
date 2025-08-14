import os
import traceback
from datetime import datetime
from fastapi import FastAPI, HTTPException, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, StreamingResponse
from typing import Optional, Union, List
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from contextlib import asynccontextmanager
from backend.infrastructure.tts.base import BaseTTS, TTSRequest
from backend.infrastructure.llm import LLMClientBase, ErrorResponse
from backend.infrastructure.storage.session_manager import load_history, save_history
# Image storage imports removed - now handled in content service
from backend.infrastructure.llm.base.factory import initialize_factory
from backend.infrastructure.tts.tts_factory import get_tts_engine
from backend.config import get_llm_settings, LOCATION_DB_PATH
# API models imports removed - now handled in specific service modules
from backend.infrastructure.mcp.smart_mcp_server import mcp
from fastmcp import Client, Context
import threading
# Text-to-image import removed - now handled in content service
from backend.presentation.api import images
from backend.presentation.api import agent_profiles  
from backend.presentation.api import sessions
from backend.presentation.api import messages
from backend.presentation.api import content
from backend.presentation.api import settings
from backend.presentation.api import chat


# 加载环境变量
load_dotenv()

# ========== 导入重构后的模块 ==========
from backend.presentation.websocket.connection import ConnectionManager

# 使用已初始化的 MCP 实例
mcp_client = Client(mcp)

# 位置响应事件存储 - 非阻塞事件机制
# 格式: {session_id: {"location_data": {...}, "timestamp": timestamp, "event": asyncio.Event}}
_location_response_events = {}

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
        
        # 初始化 LLM Factory
        llm_factory = initialize_factory()
        llm_client = llm_factory.create_client()
        app.state.llm_client = llm_client
        app.state.llm_factory = llm_factory
        print(f"[INIT] LLM Factory initialized successfully")
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
        from backend.shared.utils.config_validator import validate_llm_configuration
        await validate_llm_configuration()
        
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
app.include_router(agent_profiles.router)
app.include_router(sessions.router, prefix="/api")
app.include_router(messages.router, prefix="/api")
app.include_router(content.router, prefix="/api")
app.include_router(settings.router, prefix="/api")
app.include_router(chat.router, prefix="/api")

# Create session endpoint moved to backend/presentation/api/sessions.py

# Session management endpoints moved to backend/presentation/api/sessions.py

# Get session history endpoint moved to backend/presentation/api/sessions.py

# Delete session endpoint moved to backend/presentation/api/sessions.py

# Switch session endpoint moved to backend/presentation/api/sessions.py

# Chat stream endpoint moved to backend/presentation/api/chat.py

# Delete message endpoint moved to backend/presentation/api/messages.py

# Title generation endpoint moved to backend/presentation/api/content.py

# Tools enabled endpoint moved to backend/presentation/api/settings.py

# TTS enabled endpoint moved to backend/presentation/api/settings.py

# Image generation endpoint moved to backend/presentation/api/content.py

# Location update API removed - now handled via WebSocket LOCATION_RESPONSE messages

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """为每个客户端会话建立 WebSocket 连接。"""
    import json
    import asyncio
    
    connection_manager: ConnectionManager = websocket.app.state.connection_manager
    await connection_manager.connect(websocket, session_id)
    try:
        while True:
            # 接收并处理来自前端的消息
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                
                # 处理心跳响应消息
                if message.get("type") == "HEARTBEAT_ACK":
                    connection_manager.handle_heartbeat_response(session_id)
                    continue
                
                # 处理位置响应消息
                if message.get("type") == "LOCATION_RESPONSE":
                    print(f"[DEBUG] Received location response for session {session_id}: {message}")
                    
                    # 存储位置数据并触发事件
                    if session_id in _location_response_events:
                        event_info = _location_response_events[session_id]
                        
                        # 存储位置数据
                        if "location_data" in message:
                            event_info["location_data"] = message["location_data"]
                            event_info["timestamp"] = message.get("timestamp", int(datetime.now().timestamp()))
                            event_info["success"] = True
                        else:
                            event_info["error"] = message.get("error", "Unknown error")
                            event_info["success"] = False
                        
                        # 触发事件，通知等待的工具
                        event_info["event"].set()
                        print(f"[DEBUG] Location event triggered for session {session_id}")
                    else:
                        print(f"[DEBUG] No location request pending for session {session_id}")
                        
            except json.JSONDecodeError:
                print(f"[DEBUG] Received non-JSON message from {session_id}: {data}")
                
    except WebSocketDisconnect:
        connection_manager.disconnect(session_id)

# ========== 全局异常处理器 - SOTA架构 ==========

from backend.shared.utils.exception_handlers import handle_value_error, handle_import_error

@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    """处理配置相关的值错误，特别是LLM客户端不支持的情况"""
    return await handle_value_error(request, exc)

@app.exception_handler(ImportError)
async def import_error_handler(request: Request, exc: ImportError):
    """处理导入错误，通常是由于缺少依赖或已删除的模块引起"""
    return await handle_import_error(request, exc)

