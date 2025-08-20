from pathlib import Path
import sys

# 使用 pathlib 优雅处理路径
_CURRENT_FILE = Path(__file__)
_NAGISA_MCP_DIR = _CURRENT_FILE.parent     # nagisa_mcp目录
_BACKEND_DIR = _NAGISA_MCP_DIR.parent      # backend目录
_PROJECT_ROOT = _BACKEND_DIR.parent        # 项目根目录

# 添加必要路径到 sys.path
sys.path.insert(0, str(_PROJECT_ROOT))
import asyncio
from fastmcp import FastMCP
from backend.infrastructure.mcp.tools.builtin import register_builtin_tools
from backend.infrastructure.mcp.tools.lifestyle.tools.email import register_email_tools
from backend.infrastructure.mcp.tools.lifestyle.tools.calendar import register_calendar_tools
from backend.infrastructure.mcp.tools.coding import register_coding_tools
from backend.infrastructure.mcp.tools.lifestyle.tools.text_to_image import register_text_to_image_tools
from backend.infrastructure.mcp.tools.lifestyle.tools.contacts import register_contact_tools
from backend.infrastructure.mcp.tools.lifestyle.tools.places import register_places_tools
from backend.infrastructure.mcp.tools.lifestyle.tools.location import register_location_tools
from backend.infrastructure.mcp.tools.lifestyle.tools.time import register_time_tools

mcp = FastMCP(
    "Smart MCP Server for Nagisa",
    instructions="""
    This is a Smart MCP Server for Nagisa with comprehensive tool support.
    The server provides various tool categories for different tasks including coding,
    communication, information retrieval, media generation, and utilities.
    """
)

print(f"[DEBUG] Smart MCP Server initialized")

# 注册所有工具
register_builtin_tools(mcp)
register_email_tools(mcp)
register_calendar_tools(mcp)
register_coding_tools(mcp)
register_text_to_image_tools(mcp)
register_contact_tools(mcp)
register_places_tools(mcp)
register_location_tools(mcp)
register_time_tools(mcp)

# 启动服务器
if __name__ == "__main__":
    print("Starting Smart MCP Server with dynamic tool selection...")
    mcp.run() 