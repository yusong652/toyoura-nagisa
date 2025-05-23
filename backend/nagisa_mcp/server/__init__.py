# from fastmcp import FastMCP

# mcp = FastMCP("My MCP Server")

# 导入所有工具函数，自动注册到 mcp
from nagisa_mcp.tools.basic_tools import register_tools as register_basic_tools
from nagisa_mcp.tools.weather import register_tools as register_weather_tools
from nagisa_mcp.tools.translate import register_tools as register_translate_tools

if __name__ == "__main__":
    from fastmcp import FastMCP  # 延迟导入，避免循环依赖
    mcp = FastMCP("My MCP Server")
    # 注册所有工具
    register_basic_tools()
    register_weather_tools()
    register_translate_tools()
    print("Starting Fast MCP Server with function call support...")
    mcp.run() 