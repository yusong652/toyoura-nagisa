import asyncio
import json
from typing import Dict, Any, List, Optional
from fastmcp import FastMCP, Client
from datetime import datetime

mcp = FastMCP("Fast MCP Server")
print(f"[DEBUG] Fast MCP Server initialized")

# 工具函数定义
@mcp.tool()
async def get_current_time() -> str:
    """获取当前时间"""
    print(f"[DEBUG] get_current_time called")
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
# 启动服务器
if __name__ == "__main__":
    print("Starting Fast MCP Server with function call support...")
    mcp.run()

