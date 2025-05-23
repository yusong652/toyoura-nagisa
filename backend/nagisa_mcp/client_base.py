from abc import ABC, abstractmethod
from typing import Any, Dict, List

class MCPClientBase(ABC):
    """
    抽象基类：所有 MCP 客户端都应继承此类，统一接口。
    """
    @abstractmethod
    async def call_tool(self, tool_name: str, params: Dict[str, Any]) -> Any:
        """
        调用指定工具。
        Args:
            tool_name: 工具名称
            params: 参数字典
        Returns:
            工具执行结果
        """
        pass

    async def list_tools(self) -> List[str]:
        """
        可选：返回可用工具列表。
        Returns:
            工具名称列表
        """
        raise NotImplementedError("list_tools is not implemented.") 