from fastmcp import Client as FastMCPClient
from .client_base import MCPClientBase
from .models import ToolCallRequest, ToolCallResponse
from typing import Any, Dict, List

class MCPClient(MCPClientBase):
    def __init__(self, server_entry: str = "mcp/server.py"):
        self.server_entry = server_entry
        self._client = FastMCPClient(server_entry)

    async def list_tools(self) -> List[dict]:
        async with self._client as client:
            tools = await client.list_tools()
            # tools is a list of ToolSchema objects (dict-like)
            return [tool.model_dump() if hasattr(tool, 'model_dump') else dict(tool) for tool in tools]

    async def call_tool(self, tool_name: str, params: Dict[str, Any]) -> Any:
        async with self._client as client:
            return await client.call_tool(tool_name, params)

    async def get_tool_schemas(self) -> List[dict]:
        """
        获取所有工具的 schema，适合传递给 LLM 作为 function call 描述。
        """
        return await self.list_tools()

    async def call_tool(self, tool_name: str, params: Dict[str, Any]) -> Any:
        req = ToolCallRequest(tool_name=tool_name, params=params)
        async with self._client:
            try:
                result = await self._client.call_tool(req.tool_name, req.params)
                return ToolCallResponse(result=result)
            except Exception as e:
                return ToolCallResponse(result=None, error=str(e))

    async def list_tools(self) -> List[str]:
        # FastMCP 没有直接的工具列表API，这里假设有实现或返回空
        # 你可以扩展为通过 introspect 或注册表获取
        return [] 