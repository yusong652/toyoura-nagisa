from fastmcp import FastMCP
from nagisa_mcp.tools.meta_tool.tool import register_meta_tools

if __name__ == "__main__":
    mcp = FastMCP("TestMeta")
    register_meta_tools(mcp)
    tool_obj = mcp.get_tool("search_tools_by_keywords")
    result = tool_obj.callable("time clock current time", 5)
    print("[TEST] meta_tool.search_tools_by_keywords 返回：")
    print(result) 