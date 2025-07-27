"""
Gemini Tool Manager - 专门用于Gemini API的工具管理器

继承自BaseToolManager，实现Gemini特定的工具schema格式化和处理逻辑。
专门针对Gemini API的要求进行优化，包括JSON schema清理和Tool对象构建。
"""

from typing import Dict, Any, List, Optional
from google.genai import types

from backend.infrastructure.llm.base_tool_manager import BaseToolManager


class GeminiToolManager(BaseToolManager):
    """
    Gemini专用工具管理器
    
    继承BaseToolManager的通用功能，并实现Gemini特定的：
    - JSON Schema清理（移除不支持的关键字）
    - Gemini Tool对象构建
    - 函数声明格式化
    """
    
    def _sanitize_jsonschema_for_gemini(self, schema: dict) -> dict:
        """
        为Gemini清理JSON schema，移除不支持的关键字
        
        Gemini function-call schema目前只支持draft-7 JSON Schema的子集
        (type/properties/required/description/enum/items/default/title)
        其他关键字如exclusiveMinimum会导致严格验证错误
        
        Args:
            schema: 待清理的JSON schema
            
        Returns:
            dict: 清理后的schema
        """
        ALLOWED_KEYS = {
            "type", "properties", "required", "description", 
            "enum", "items", "default", "title",
        }
        
        if not isinstance(schema, dict):
            return schema
        
        cleaned: dict = {}
        for key, value in schema.items():
            if key not in ALLOWED_KEYS:
                continue
            
            if key == "properties":
                cleaned["properties"] = {
                    prop_name: self._sanitize_jsonschema_for_gemini(prop_schema)
                    for prop_name, prop_schema in value.items()
                    if isinstance(prop_schema, dict)
                }
            elif key == "items":
                cleaned["items"] = self._sanitize_jsonschema_for_gemini(value)
            else:
                cleaned[key] = value
        
        # 为object类型自动推断required字段
        if cleaned.get("type") == "object" and "required" not in cleaned and "properties" in cleaned:
            cleaned["required"] = list(cleaned["properties"].keys())
        
        return cleaned
    
    def convert_mcp_schema_to_gemini(self, schema: dict) -> dict:
        """
        将fastMCP工具schema转换为Gemini兼容的函数调用schema
        
        Args:
            schema: fastMCP工具schema
            
        Returns:
            Gemini兼容的schema字典
        """
        return {
            "name": schema["name"],
            "description": schema.get("description", ""),
            "parameters": schema.get("inputSchema", {"type": "object", "properties": {}})
        }
    
    async def get_function_call_schemas(self, session_id: Optional[str] = None, debug: bool = False) -> List[types.Tool]:
        """
        获取所有MCP工具的schema，返回Gemini Tools格式
        只返回meta tools + cached tools，不返回所有regular tools
        
        Args:
            session_id: 可选的会话ID，用于工具缓存
            debug: 是否启用调试输出
            
        Returns:
            List[types.Tool]: Gemini Tool对象列表，包含function declarations
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
            
            # 为Gemini清理schema
            if "properties" in input_schema:
                for prop in input_schema["properties"].values():
                    if "description" not in prop:
                        prop["description"] = "Parameter value"
                input_schema["required"] = list(input_schema["properties"].keys())
            if "type" not in input_schema:
                input_schema["type"] = "object"
            # Gemini不允许additionalProperties字段
            input_schema.pop("additionalProperties", None)
            
            # 移除Gemini不支持的JSON Schema关键字
            input_schema = self._sanitize_jsonschema_for_gemini(input_schema)
            
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
                            "required": list(cached_input_schema.keys()) if cached_input_schema else []
                        }
                else:
                    # 默认空schema
                    input_schema = {"type": "object", "properties": {}}
                
                # 清理Gemini不支持的字段并sanitize
                input_schema.pop("additionalProperties", None)
                input_schema = self._sanitize_jsonschema_for_gemini(input_schema)
                
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
        
        # 转换为Gemini Tool对象格式
        function_declarations = [
            {
                "name": tool["name"],
                "description": tool.get("description", ""),
                "parameters": self._sanitize_jsonschema_for_gemini(tool.get("parameters", {"type": "object", "properties": {}})),
            }
            for tool in final_tools
        ]
        
        tools = []
        if function_declarations:
            tools.append(types.Tool(function_declarations=function_declarations))
        
        return tools

    # 保持向后兼容的别名方法
    def sanitize_jsonschema(self, schema: dict) -> dict:
        """向后兼容的方法别名"""
        return self._sanitize_jsonschema_for_gemini(schema)


# 为了向后兼容，保持原有的类名
ToolManager = GeminiToolManager