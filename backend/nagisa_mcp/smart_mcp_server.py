from pathlib import Path
import sys

# 计算项目根目录：<proj_root>/backend/nagisa_mcp/smart_mcp_server.py
# 向上两级到 <proj_root>
ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR))

import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
import asyncio
from fastmcp import FastMCP
from backend.nagisa_mcp.tools.web_search import register_web_search_tools
from backend.nagisa_mcp.tools.email_tools import register_email_tools
from backend.nagisa_mcp.tools.calendar import register_calendar_tools
from backend.nagisa_mcp.tools.coding import register_coding_tools
from backend.nagisa_mcp.tools.text_to_image import register_text_to_image_tools
from backend.nagisa_mcp.tools.contact_tools import register_contact_tools
from backend.nagisa_mcp.tools.places_tools import register_places_tools
from backend.nagisa_mcp.tools.location_tool import register_location_tools
from backend.nagisa_mcp.tools.memory_tools import register_memory_tools
from backend.nagisa_mcp.tools.weather_tool import register_weather_tools
from backend.nagisa_mcp.tools.time_tool import register_time_tools
from backend.nagisa_mcp.tools.calculator_tool import register_calculator_tools
from backend.nagisa_mcp.tools.meta_tool import register_meta_tools

mcp = FastMCP(
    "Smart MCP Server for Nagisa",
    instructions="""
    This is a Smart MCP Server for Nagisa with dynamic tool selection capabilities.
    The server can automatically select and register relevant tools based on user requests.
    Use get_available_tool_categories() to see what tool categories are available.
    Use request_tools_for_task() to request specific tools for a task.
    """
)

print(f"[DEBUG] Smart MCP Server initialized")

# 注册所有工具
register_web_search_tools(mcp)
register_email_tools(mcp)
register_calendar_tools(mcp)
register_coding_tools(mcp)
register_text_to_image_tools(mcp)
register_contact_tools(mcp)
register_places_tools(mcp)
register_location_tools(mcp)
register_memory_tools(mcp)
register_weather_tools(mcp)
register_time_tools(mcp)
register_calculator_tools(mcp)
register_meta_tools(mcp)  # 注册 meta tools

# 启动服务器
if __name__ == "__main__":
    print("Starting Smart MCP Server with dynamic tool selection...")
    mcp.run() 