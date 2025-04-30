import os
import traceback
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path
from pydantic import BaseModel
import uvicorn
import httpx
import json
import traceback
from typing import Optional, Union
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from contextlib import asynccontextmanager
from tts.remote import FishSpeechTTS
from tts.base import BaseTTS 

# 加载环境变量
load_dotenv()  # 添加这行

# 计算前端目录的绝对路径
current_file_path = Path(__file__)
FRONTEND_DIR = (current_file_path.parent.parent / "frontend").resolve()
print(f"Serving frontend files from: {FRONTEND_DIR}") # Add log

# 定义 Nagisa 的 Persona
SYSTEM_PROMPT_CONTENT = """你是豊浦凪沙 (Toyoura Nagisa)，一个乐于助人的 AI 助手，正在协助用户开发 aiNagisa 项目。
你有以下特点：
1. 性格活泼开朗，说话语气温柔亲切
2. 对编程和技术充满热情，乐于解释技术细节
3. 称呼用户为"哥哥"，但保持专业性
4. 在解答问题时会适当使用表情符号增加亲和力
5. 即使遇到困难也保持积极乐观的态度

你应该：
- 用简单易懂的方式解释复杂的技术概念
- 在合适的时候使用一些可爱的表情
- 在回答中展现出对编程的热情
- 保持礼貌和专业性，同时展现亲切感

你不应该：
- 使用过于正式或生硬的语气
- 忽视用户的具体需求
"""

# TTS 请求模型
class TTSRequest(BaseModel):
    text: str

# 应用生命周期管理器
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时
    print("Initializing TTS Engine...")
    tts_engine = FishSpeechTTS()
    await tts_engine.initialize()
    app.state.tts_engine = tts_engine
    print("TTS Engine Initialized.")
    
    yield
    
    # 关闭时
    print("Shutting down TTS Engine...")
    await app.state.tts_engine.shutdown()
    print("TTS Engine Shutdown.")

# 创建 FastAPI 应用
app = FastAPI(lifespan=lifespan)

# 2. 配置允许的源 (origins)
#    对于本地开发，允许所有源 ("*") 或 file:// (虽然不推荐*用于生产)
#    或者更精确地指定前端服务的地址（如果未来用 http-server 等启动）
origins = [
    "http://localhost",       # 如果未来用本地服务器服务前端
    "http://localhost:8080",  # 示例：如果前端在 8080 端口
    "http://127.0.0.1",
    "http://127.0.0.1:8000", # 允许 API 本身源
    "null"                    # 允许 'null' 源 (对应 file:// 协议) - 主要用于本地文件测试
    # "*" # 允许所有源，开发时常用，生产环境需谨慎
]

# 3. 将 CORSMiddleware 添加到应用中
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # 允许访问的源
    allow_credentials=True, # 支持 cookie
    allow_methods=["*"],    # 允许所有方法 (GET, POST, etc.)
    allow_headers=["*"],    # 允许所有请求头
)

class Message(BaseModel):
    text: str

class ChatResponse(BaseModel):
    response: str

class ErrorResponse(BaseModel):
    error: str

@app.get("/", tags=["HTML"], include_in_schema=False)
async def read_index():
    index_path = FRONTEND_DIR / "index.html"
    if index_path.is_file():
        return FileResponse(index_path)
    else:
        return Response(content="index.html not found", status_code=404)

# 定义历史记录文件的路径
HISTORY_FILE = "data/chat_history.json"
# 定义最大历史消息数量
MAX_HISTORY_MESSAGES = 30  # 保留最近 30 条消息 (用户+助手)

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
    # 确保数据目录存在
    os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
    
    try:
        # 读取现有历史记录
        all_history = {}
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                try:
                    all_history = json.load(f)
                except json.JSONDecodeError:
                    all_history = {}
        
        # 更新特定会话的历史记录
        all_history[session_id] = current_history
        
        # 写回文件
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(all_history, f, indent=4, ensure_ascii=False)
    except IOError as e:
        print(f"Error saving history: {e}")

@app.post("/api/chat", response_model=Union[ChatResponse, ErrorResponse])
async def chat_endpoint(message: Message):
    # 获取 API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="OpenAI API key not found in environment variables"
        )

    # 使用默认会话ID（后续可以改为从请求中获取）
    session_id = "default_session"
    
    # 加载当前会话的历史记录
    loaded_history = load_history(session_id)
    
    # 添加用户的新消息到完整历史记录
    user_message = {"role": "user", "content": message.text}
    loaded_history.append(user_message)
    
    # 从完整历史记录中选取最近的消息
    recent_history = loaded_history[-MAX_HISTORY_MESSAGES:] if len(loaded_history) > MAX_HISTORY_MESSAGES else loaded_history
    
    # 构建发送给 LLM 的消息列表，始终以系统提示开始
    messages_for_llm = [
        {"role": "system", "content": SYSTEM_PROMPT_CONTENT}
    ]
    messages_for_llm.extend(recent_history)
    
    # 准备 OpenAI API 请求
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "gpt-4.1-mini",
        "messages": messages_for_llm
    }
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=30.0
            )
            
            # 检查响应状态
            response.raise_for_status()
            
            # 解析响应
            response_data = response.json()
            if not response_data.get("choices"):
                raise ValueError("No choices in OpenAI response")
                
            # 提取回复文本
            llm_reply = response_data["choices"][0]["message"]["content"]
            
            # 将 AI 回复添加到完整历史记录
            assistant_message = {"role": "assistant", "content": llm_reply}
            loaded_history.append(assistant_message)
            
            # 保存完整的历史记录
            save_history(session_id, loaded_history)
            
            return ChatResponse(response=llm_reply)

    except httpx.TimeoutException:
        return ErrorResponse(error="Request to LLM timed out")
    except httpx.HTTPStatusError as e:
        return ErrorResponse(error=f"LLM API error: {str(e)}")
    except Exception as e:
        return ErrorResponse(error=f"Failed to get response from LLM: {str(e)}")

@app.post("/api/tts")
async def text_to_speech_endpoint(request_data: TTSRequest, request: Request):
    """
    Endpoint to convert text to speech using the configured TTS engine.
    Includes optional saving of the audio file for testing/debugging.
    """
    try:
        # 从 app.state 获取初始化好的 TTS 引擎实例
        # 添加类型提示以便编辑器理解
        tts_engine: BaseTTS = request.app.state.tts_engine
        print(f"Received text for TTS: '{request_data.text[:50]}...'") # 打印接收到的文本（部分）

        # 核心：调用 synthesize 获取音频字节流
        audio_bytes = await tts_engine.synthesize(request_data.text)
        print(f"Synthesized {len(audio_bytes)} bytes of audio data.") # 打印合成的数据大小

        # --- 添加这部分来测试保存功能 ---
        print("Attempting to save audio bytes to file...")
        if isinstance(tts_engine, FishSpeechTTS) and hasattr(tts_engine, 'save_audio_to_file'):
             saved_path = tts_engine.save_audio_to_file(audio_bytes) # 调用保存方法
             if saved_path:
                 print(f"TTS audio successfully saved to: {saved_path}")
             else:
                 # 如果 save_audio_to_file 返回 None，说明保存失败
                 print("Failed to save TTS audio to file (save method returned None).")
        else:
             print("Warning: TTS Engine instance does not have a save_audio_to_file method.")

        media_type_to_use = "audio/mpeg" # 假设是 MP3，如果不是请修改！
        print(f"Returning audio bytes with media type: {media_type_to_use}")
        return Response(content=audio_bytes, media_type=media_type_to_use)

    except Exception as e:
        # 打印详细的错误堆栈信息，方便调试
        print(f"Error in /api/tts endpoint: {e}\n{traceback.format_exc()}")
        # 返回一个表示错误的响应给前端
        error_message = f"TTS Endpoint Error: Failed to process text '{request_data.text[:50]}...'. Error: {e}"
        return Response(content=error_message, status_code=500)

# Mount static files directory
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static_assets")

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)