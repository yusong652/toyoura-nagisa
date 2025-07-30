"""
Anthropic Tool Manager - 专门用于Anthropic API的工具管理器

继承自BaseToolManager，实现Anthropic特定的工具schema格式化和处理逻辑。
专门针对Anthropic Claude API的要求进行优化，包括input_schema格式化。
"""

from typing import Dict, Any, List, Optional

from backend.infrastructure.llm.base.tool_manager import BaseToolManager


class AnthropicToolManager(BaseToolManager):
    """
    Anthropic专用工具管理器
    
    继承BaseToolManager的通用功能，并实现Anthropic特定的：
    - input_schema格式化
    - Anthropic tool对象构建
    - 参数描述和验证
    """
    
    def _format_schema_for_anthropic(self, tool_schema: Dict[str, Any]) -> Dict[str, Any]:
        """
        格式化工具schema为Anthropic格式
        
        Args:
            tool_schema: 原始工具schema
            
        Returns:
            Dict: Anthropic格式的工具schema
        """
        input_schema = tool_schema.get("parameters", {"type": "object", "properties": {}})
        
        # 确保schema完整性
        if "properties" in input_schema:
            # 确保所有参数都有描述
            for prop in input_schema["properties"].values():
                if "description" not in prop:
                    prop["description"] = "Parameter value"
            # 设置required字段
            input_schema["required"] = list(input_schema["properties"].keys())
        
        if "type" not in input_schema:
            input_schema["type"] = "object"
        if "additionalProperties" not in input_schema:
            input_schema["additionalProperties"] = False
        
        return {
            "name": tool_schema["name"],
            "description": tool_schema.get("description", tool_schema["name"]),
            "input_schema": input_schema
        }
    
    async def get_function_call_schemas(self, session_id: Optional[str] = None, debug: bool = False) -> List[Dict[str, Any]]:
        """
        获取所有MCP工具的schema，返回Anthropic格式
        只返回meta tools + cached tools，不返回所有regular tools
        
        Args:
            session_id: 可选的会话ID，用于工具缓存
            debug: 是否启用调试输出
            
        Returns:
            List[Dict[str, Any]]: Anthropic格式的工具schema列表
        """
        if not self.tools_enabled:
            return []
        
        # 获取会话缓存的工具
        cached_tools = []
        if session_id:
            cached_tools = self.get_cached_tools_for_session(session_id)
            if debug:
                print(f"[DEBUG] Found {len(cached_tools)} cached tools for session {session_id}")
        
        # 获取所有MCP工具
        mcp_client = self.get_mcp_client(session_id)
        async with mcp_client as mcp_async_client:
            mcp_tools = await mcp_async_client.list_tools()
        
        # 构建工具映射
        tools_map = {}
        meta_tools = []
        
        for tool in mcp_tools:
            tool_name = tool.name
            input_schema = getattr(tool, "inputSchema", {"type": "object", "properties": {}})
            
            tool_schema = {
                "name": tool_name,
                "description": getattr(tool, "description", tool_name),
                "parameters": input_schema
            }
            
            tools_map[tool_name] = tool_schema
            if self.is_meta_tool(tool_name):
                meta_tools.append(tool_schema)
        
        # 构建最终工具列表：meta tools + cached tools（避免重复）
        final_tools = meta_tools.copy()
        added_tool_names = {tool["name"] for tool in meta_tools}
        
        for cached_tool in cached_tools:
            tool_name = cached_tool["name"]
            if tool_name in added_tool_names:
                if debug:
                    print(f"[DEBUG] Skipped duplicate cached tool: {tool_name}")
                continue
                
            if tool_name in tools_map:
                # 工具在MCP中存在，使用完整的MCP schema
                final_tools.append(tools_map[tool_name])
                added_tool_names.add(tool_name)
                if debug:
                    print(f"[DEBUG] Added cached tool from MCP: {tool_name}")
            else:
                # 工具不在MCP中，使用缓存的schema信息
                # 优先使用inputSchema，其次使用parameters
                cached_input_schema = cached_tool.get("inputSchema") or cached_tool.get("parameters", {})
                
                # 确保是正确的schema格式
                if isinstance(cached_input_schema, dict):
                    if "type" in cached_input_schema and "properties" in cached_input_schema:
                        # 已经是完整的inputSchema格式
                        input_schema = dict(cached_input_schema)
                    else:
                        # 只是properties字典，需要包装
                        input_schema = {
                            "type": "object",
                            "properties": cached_input_schema,
                            "required": list(cached_input_schema.keys()) if cached_input_schema else [],
                            "additionalProperties": False
                        }
                else:
                    # 默认空schema
                    input_schema = {
                        "type": "object", 
                        "properties": {},
                        "required": [],
                        "additionalProperties": False
                    }
                
                final_tools.append({
                    "name": tool_name,
                    "description": cached_tool.get("description", tool_name),
                    "parameters": input_schema
                })
                added_tool_names.add(tool_name)
                if debug:
                    print(f"[DEBUG] Added cached tool with constructed schema: {tool_name}")
        
        if debug:
            print(f"[DEBUG] Final tools count: {len(final_tools)} (meta: {len(meta_tools)}, cached: {len(cached_tools)})")
        
        # 格式化为Anthropic格式
        return [self._format_schema_for_anthropic(tool) for tool in final_tools]