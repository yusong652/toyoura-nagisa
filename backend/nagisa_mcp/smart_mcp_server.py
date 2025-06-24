import asyncio
from fastmcp import FastMCP
from backend.nagisa_mcp.tools.common_tools import register_common_tools
from backend.nagisa_mcp.tools.web_search import register_web_search_tools
from backend.nagisa_mcp.tools.email_tools import register_email_tools
from backend.nagisa_mcp.tools.calendar import register_calendar_tools
from backend.nagisa_mcp.tools.coding import register_coding_tools
from backend.nagisa_mcp.tools.text_to_image import register_text_to_image_tool
from backend.nagisa_mcp.tools.contact_tools import register_contact_tools
from backend.nagisa_mcp.tools.places_tools import register_places_tools
from backend.nagisa_mcp.tools.memory_tools import register_memory_tools
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
register_common_tools(mcp)
register_web_search_tools(mcp)
register_email_tools(mcp)
register_calendar_tools(mcp)
register_coding_tools(mcp)
register_text_to_image_tool(mcp)
register_contact_tools(mcp)
register_places_tools(mcp)
register_memory_tools(mcp)
register_meta_tools(mcp)  # 注册 meta tools

# 启动服务器
if __name__ == "__main__":
    print("Starting Smart MCP Server with dynamic tool selection...")
    mcp.run() 