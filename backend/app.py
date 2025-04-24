from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn
# 1. 导入 CORSMiddleware
from fastapi.middleware.cors import CORSMiddleware

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

@app.get("/")
async def read_root():
    return {"message": "Welcome to aiNagisa backend!"}

@app.post("/api/chat")
async def chat_endpoint(message: Message):
    # TODO: Implement actual LLM logic later
    response_text = f"Received: {message.text}. Replying soon!"
    # 注意：FastAPI 会自动将字典转为 JSON 响应
    return {"response": response_text}

# Add this block to run directly for testing
if __name__ == "__main__":
    # 在这里运行 uvicorn 时，CORS 中间件已添加
    uvicorn.run(app, host="127.0.0.1", port=8000)