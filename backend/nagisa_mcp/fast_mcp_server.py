import asyncio
import json
from typing import Dict, Any, List, Optional
from fastmcp import FastMCP, Client
from backend.nagisa_mcp.tools.common_tools import register_common_tools
from backend.nagisa_mcp.tools.web_search import register_web_search_tools
from datetime import datetime

mcp = FastMCP("Fast MCP Server", 
              instructions="""
              This is a Fast MCP Server for Nagisa
              Call get_current_time() to get the current time""")

print(f"[DEBUG] Fast MCP Server initialized")

# register_common_tools(mcp)
register_web_search_tools(mcp)
    
# 启动服务器
if __name__ == "__main__":
    print("Starting Fast MCP Server with function call support...")
    mcp.run()

