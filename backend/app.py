from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
import httpx
import os
from typing import Optional, Union
# 1. 导入 CORSMiddleware
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv  # 添加这行

# 加载环境变量
load_dotenv()  # 添加这行

app = FastAPI()

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

@app.get("/")
async def read_root():
    return {"message": "Welcome to aiNagisa backend!"}

@app.post("/api/chat", response_model=Union[ChatResponse, ErrorResponse])
async def chat_endpoint(message: Message):
    # 获取 API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="OpenAI API key not found in environment variables"
        )

    # 准备 OpenAI API 请求
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "gpt-3.5-turbo",
        "messages": [
            {"role": "user", "content": message.text}
        ]
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
            reply = response_data["choices"][0]["message"]["content"]
            return ChatResponse(response=reply)

    except httpx.TimeoutException:
        return ErrorResponse(error="Request to LLM timed out")
    except httpx.HTTPStatusError as e:
        return ErrorResponse(error=f"LLM API error: {str(e)}")
    except Exception as e:
        return ErrorResponse(error=f"Failed to get response from LLM: {str(e)}")

# Add this block to run directly for testing
if __name__ == "__main__":
    # 在这里运行 uvicorn 时，CORS 中间件已添加
    uvicorn.run(app, host="127.0.0.1", port=8000)