"""
Tool management utilities for Gemini API interactions.

Handles MCP tool integration, caching, schema management, and tool execution
for the Gemini client. Provides session-aware tool management and meta tool handling.
"""

import json
from typing import Dict, Any, List, Optional, Set
from google.genai import types
from fastmcp import Client as MCPClient
from mcp.types import Implementation, CallToolRequestParams, CallToolRequest, ClientRequest, CallToolResult

from backend.nagisa_mcp.smart_mcp_server import mcp as GLOBAL_MCP
from backend.nagisa_mcp.utils import extract_text_from_mcp_result


class ToolManager:
    """
    Handles tool management for Gemini API interactions.
    
    This class provides methods for:
    - MCP client management and session isolation
    - Tool schema retrieval and caching
    - Meta tool handling and result processing
    - Tool execution and result formatting
    - JSON schema sanitization for Gemini compatibility
    """

    def __init__(self, mcp_client_source=None, tools_enabled: bool = True):
        """
        Initialize the tool manager.
        
        Args:
            mcp_client_source: MCP client source (defaults to GLOBAL_MCP)
            tools_enabled: Whether tools are enabled
        """
        self._mcp_client_source = mcp_client_source or GLOBAL_MCP
        self.tools_enabled = tools_enabled
        
        # 按 chat_session_id 缓存已创建的 MCPClient；None 代表默认/无会话
        self._mcp_clients: Dict[str | None, MCPClient] = {}
        
        # 工具缓存机制
        self.tool_cache: Dict[str, Any] = {}
        self.meta_tools: Set[str] = set()
        # 按会话维度的工具缓存：{session_id: List[tool_schema]}
        self.session_tool_cache: Dict[str, List[Dict[str, Any]]] = {}

    def get_mcp_client(self, session_id: Optional[str] = None) -> MCPClient:
        """
        Return (and cache) an MCPClient bound to *session_id*.

        A unique client per chat-session ensures the underlying FastMCP
        Session stays isolated. If *self._mcp_client_source* is already an
        MCPClient, we always reuse that single instance.
        
        Args:
            session_id: Optional session ID for client isolation
            
        Returns:
            MCPClient instance for the session
        """
        key = session_id or "__default__"
        client = self._mcp_clients.get(key)
        if client is None:
            client = MCPClient(
                self._mcp_client_source, 
                client_info=Implementation(name=session_id, version="0.1.0")
            )
            self._mcp_clients[key] = client
        return client

    def is_meta_tool(self, tool_name: str) -> bool:
        """
        Check if a tool is a meta tool.
        
        Args:
            tool_name: Name of the tool to check
            
        Returns:
            True if the tool is a meta tool
        """
        return tool_name in {
            "search_tools_by_keywords",
            "get_available_tool_categories"
        }

    def extract_tools_from_meta_result(self, meta_result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract tool information from meta tool results.
        
        Args:
            meta_result: Result from meta tool execution
            
        Returns:
            List of tool dictionaries with parsed metadata
        """
        tools = []
        if isinstance(meta_result, dict):
            # 处理search_tools_by_keywords的结果 - 工具信息在data字段中
            tools_data = None
            
            # 首先检查data字段中的tools（标准ToolResult格式）
            if "data" in meta_result and isinstance(meta_result["data"], dict):
                tools_data = meta_result["data"].get("tools", [])
            # 兼容性：也检查顶层的tools字段（旧格式）
            elif "tools" in meta_result and isinstance(meta_result["tools"], list):
                tools_data = meta_result["tools"]
            
            if tools_data and isinstance(tools_data, list):
                for tool_info in tools_data:
                    if isinstance(tool_info, dict) and "name" in tool_info:
                        
                        # 解析 parameters
                        params = tool_info.get("parameters", {})
                        if isinstance(params, str):
                            try:
                                params = json.loads(params)
                            except (json.JSONDecodeError, TypeError):
                                params = {}  # 解析失败则视为空
                        
                        # 解析 tags
                        tags = tool_info.get("tags", [])
                        if isinstance(tags, str):
                            try:
                                tags = json.loads(tags)
                            except (json.JSONDecodeError, TypeError):
                                tags = []  # 解析失败则视为空

                        tools.append({
                            "name": tool_info["name"],
                            "description": tool_info.get("description", ""),
                            "category": tool_info.get("category", "general"),
                            "docstring": tool_info.get("docstring", ""),
                            "parameters": params,
                            "tags": tags
                        })
        return tools

    def cache_tools_for_session(self, session_id: str, tools: List[Dict[str, Any]]) -> None:
        """
        Cache tools for a specific session.
        
        Args:
            session_id: Session ID to cache tools for
            tools: List of tool dictionaries to cache
        """
        if session_id not in self.session_tool_cache:
            self.session_tool_cache[session_id] = []
        
        # 添加新工具，避免重复
        existing_names = {tool["name"] for tool in self.session_tool_cache[session_id]}
        for tool in tools:
            if tool["name"] not in existing_names:
                self.session_tool_cache[session_id].append(tool)
                existing_names.add(tool["name"])

    def get_cached_tools_for_session(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Get cached tools for a specific session.
        
        Args:
            session_id: Session ID to get tools for
            
        Returns:
            List of cached tool dictionaries
        """
        return self.session_tool_cache.get(session_id, [])

    def clear_session_tool_cache(self, session_id: str) -> None:
        """
        Clear tool cache for a specific session.
        
        Args:
            session_id: Session ID to clear cache for
        """
        if session_id in self.session_tool_cache:
            del self.session_tool_cache[session_id]

    def sanitize_jsonschema(self, schema: dict) -> dict:
        """
        Recursively strip unsupported keys from a JSON schema for Gemini.

        Gemini function-call schema currently supports only a subset of draft-7
        JSON Schema keywords (type / properties / required / description / enum /
        items / default / title). Any additional keys like *exclusiveMinimum* will
        lead to strict validation errors when instantiating
        :class:`google.ai.generativeai.types.Tool`.

        This helper keeps only the allowed keys and removes everything else.
        
        Args:
            schema: JSON schema dictionary to sanitize
            
        Returns:
            Sanitized schema dictionary
        """
        ALLOWED_KEYS = {
            "type",
            "properties",
            "required",
            "description",
            "enum",
            "items",
            "default",
            "title",
        }

        if not isinstance(schema, dict):
            return schema

        cleaned: dict = {}
        for key, value in schema.items():
            if key not in ALLOWED_KEYS:
                # Skip unsupported keyword (e.g. exclusiveMinimum, pattern, etc.)
                continue

            if key == "properties":
                cleaned["properties"] = {
                    prop_name: self.sanitize_jsonschema(prop_schema)
                    for prop_name, prop_schema in value.items()
                    if isinstance(prop_schema, dict)
                }
            elif key == "items":
                cleaned["items"] = self.sanitize_jsonschema(value)
            else:
                cleaned[key] = value

        # If this node represents an *object* and required is missing, infer it
        if cleaned.get("type") == "object" and "required" not in cleaned and "properties" in cleaned:
            cleaned["required"] = list(cleaned["properties"].keys())

        return cleaned

    def convert_mcp_schema_to_gemini(self, schema: dict) -> dict:
        """
        Convert a fastMCP tool schema to Gemini-compatible function call schema.
        
        Args:
            schema: fastMCP tool schema
            
        Returns:
            Gemini-compatible schema dictionary
        """
        return {
            "name": schema["name"],
            "description": schema.get("description", ""),
            "parameters": schema.get("inputSchema", {"type": "object", "properties": {}})
        }

    async def get_function_call_schemas(self, session_id: Optional[str] = None, debug: bool = False) -> List[types.Tool]:
        """
        Get all MCP tool schemas in Gemini tools format.
        Returns meta tools + cached tools only, not all regular tools.
        
        Args:
            session_id: Optional session ID for tool caching
            debug: Enable debug output
            
        Returns:
            List of Gemini Tool objects with function declarations
        """
        if not self.tools_enabled:
            return []
        
        # 获取会话缓存的工具
        cached_tools = []
        if session_id:
            cached_tools = self.get_cached_tools_for_session(session_id)
            if debug:
                print(f"[DEBUG] Found {len(cached_tools)} cached tools for session {session_id}")
                for tool in cached_tools:
                    print(f"[DEBUG] Cached tool available: {tool['name']} ({tool.get('category', 'unknown')})")
        
        # 获取所有MCP工具
        mcp_client = self.get_mcp_client(session_id)
        async with mcp_client as mcp_async_client:
            mcp_tools = await mcp_async_client.list_tools()
        
        # 构建工具映射
        tools_map = {}
        meta_tools = []
        
        for tool in mcp_tools:
            tool_name = tool.name
            
            # 简化参数处理
            input_schema = getattr(tool, "inputSchema", {"type": "object", "properties": {}})
            if "properties" in input_schema:
                for prop in input_schema["properties"].values():
                    if "description" not in prop:
                        prop["description"] = f"Parameter value"
                input_schema["required"] = list(input_schema["properties"].keys())
            if "type" not in input_schema:
                input_schema["type"] = "object"
            # Gemini 不允许 additionalProperties 字段
            input_schema.pop("additionalProperties", None)
            
            # 移除 Gemini 不支持的 JSON Schema 关键字（如 exclusiveMinimum）
            input_schema = self.sanitize_jsonschema(input_schema)
            
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
        added_tool_names = {tool["name"] for tool in meta_tools}  # 追踪已添加的工具名
        
        for cached_tool in cached_tools:
            tool_name = cached_tool["name"]
            if tool_name in added_tool_names:
                if debug:
                    print(f"[DEBUG] Skipped duplicate cached tool: {tool_name}")
                continue  # 跳过已经添加的工具
                
            # 复制参数，避免污染原 dict
            cached_params = dict(cached_tool.get("parameters", {}))
            cached_params.pop("additionalProperties", None)
            cached_params = self.sanitize_jsonschema(cached_params)
            if tool_name in tools_map:
                final_tools.append(tools_map[tool_name])
                added_tool_names.add(tool_name)
                if debug:
                    print(f"[DEBUG] Added cached tool: {tool_name}")
            else:
                final_tools.append({
                    "name": tool_name,
                    "description": cached_tool.get("description", tool_name),
                    "parameters": {
                        "type": "object",
                        "properties": cached_params,
                        "required": list(cached_params.keys())
                    }
                })
                added_tool_names.add(tool_name)
                if debug:
                    print(f"[DEBUG] Added cached tool with basic schema: {tool_name}")
        
        if debug:
            print(f"[DEBUG] Final tools count: {len(final_tools)} (meta: {len(meta_tools)}, cached: {len(cached_tools)})")
        
        # 转换为 Gemini 格式
        function_declarations = [
            {
                "name": tool["name"],
                "description": tool.get("description", ""),
                "parameters": self.sanitize_jsonschema(tool.get("parameters", {"type": "object", "properties": {}})),
            }
            for tool in final_tools
        ]
        
        tools = []
        if function_declarations:
            tools.append(types.Tool(function_declarations=function_declarations))
        
        return tools

    async def handle_function_call(self, function_call: dict, session_id: Optional[str] = None, debug: bool = False):
        """
        Handle LLM-generated function_call requests, dispatching to MCP tools.
        
        Args:
            function_call: Function call dict with name, arguments, and optional id
            session_id: Optional session ID for context-aware tools
            debug: Enable debug output
            
        Returns:
            Tool execution result or error information
        """
        tool_name = function_call["name"]
        tool_args = function_call.get("arguments", {})
        tool_id = function_call.get("id", "")

        # 1. Meta tool handling
        if self.is_meta_tool(tool_name):
            if debug:
                print(f"[DEBUG] Handling meta tool: {tool_name}")
            
            try:
                mcp_client = self.get_mcp_client(session_id)
                async with mcp_client as mcp_async_client:
                    if session_id:
                        try:
                            params = CallToolRequestParams(
                                name=tool_name,
                                arguments=tool_args,
                                **{"_meta": {"client_id": session_id}},
                            )
                            call_req = ClientRequest(CallToolRequest(method="tools/call", params=params))
                            result: CallToolResult = await mcp_async_client.session.send_request(
                                call_req,
                                CallToolResult,
                            )
                        except Exception:
                            result = await mcp_async_client.call_tool(tool_name, tool_args)
                    
                    text_result = extract_text_from_mcp_result(result)
                    
                    # Check for error
                    if isinstance(result, dict) and result.get("error"):
                        return {
                            "type": "tool_result",
                            "tool_use_id": tool_id,
                            "name": tool_name,
                            "content": text_result,
                            "is_error": True
                        }
                    
                    # Extract llm_content for meta tools (same as normal tools)
                    content_for_llm = text_result
                    if isinstance(text_result, dict):
                        # If it's our standard ToolResult, extract the specific llm_content part
                        if 'llm_content' in text_result:
                            content_for_llm = text_result['llm_content']
                        
                        # Check for error status in the standard ToolResult
                        if text_result.get("status") == "error":
                            return {
                                "type": "tool_result",
                                "tool_use_id": tool_id,
                                "name": tool_name,
                                "content": text_result.get("message", "Tool execution failed."),
                                "is_error": True
                            }
                    
                    # Cache meta results
                    if tool_name == "search_tools_by_keywords" and session_id:
                        try:
                            meta_result = {}
                            if isinstance(text_result, dict):
                                meta_result = text_result
                            elif isinstance(text_result, str):
                                try:
                                    meta_result = json.loads(text_result)
                                except (json.JSONDecodeError, TypeError):
                                    meta_result = {}
                            
                            if debug:
                                print(f"[DEBUG] Meta tool result structure: {list(meta_result.keys()) if isinstance(meta_result, dict) else type(meta_result)}")
                                if isinstance(meta_result, dict) and "data" in meta_result:
                                    print(f"[DEBUG] Data field keys: {list(meta_result['data'].keys()) if isinstance(meta_result['data'], dict) else type(meta_result['data'])}")
                            
                            extracted_tools = self.extract_tools_from_meta_result(meta_result)
                            if extracted_tools:
                                self.cache_tools_for_session(session_id, extracted_tools)
                                if debug:
                                    print(f"[DEBUG] Successfully cached {len(extracted_tools)} tools for session {session_id}")
                                    for tool in extracted_tools:
                                        print(f"[DEBUG] Cached tool: {tool['name']} ({tool['category']})")
                            else:
                                if debug:
                                    print(f"[DEBUG] No tools extracted from meta result for caching")

                        except Exception as e:
                            if debug:
                                print(f"[DEBUG] Failed to cache tools from meta result: {e}")
                                import traceback
                                print(f"[DEBUG] Traceback: {traceback.format_exc()}")
                    
                    return content_for_llm
                    
            except Exception as e:
                if debug:
                    print(f"Error calling meta tool {tool_name}: {str(e)}")
                return {
                    "type": "tool_result",
                    "tool_use_id": tool_id,
                    "name": tool_name,
                    "content": f"Error: Meta tool execution failed - {str(e)}",
                    "is_error": True
                }

        # 2. Normal tool handling
        try:
            mcp_client = self.get_mcp_client(session_id)
            async with mcp_client as mcp_async_client:
                # Inject session_id if present
                if session_id:
                    try:
                        params = CallToolRequestParams(
                            name=tool_name,
                            arguments=tool_args,
                            **{"_meta": {"client_id": session_id}},
                        )
                        call_req = ClientRequest(CallToolRequest(method="tools/call", params=params))
                        result_obj = await mcp_async_client.session.send_request(
                            call_req,
                            CallToolResult,
                        )
                    except Exception:
                        result_obj = await mcp_async_client.call_tool(tool_name, tool_args)
                else:
                    result_obj = await mcp_async_client.call_tool(tool_name, tool_args)

            # Extract the dict from ToolResult.model_dump()
            tool_output = extract_text_from_mcp_result(result_obj)

            # Default content for LLM is the whole output, for backward compatibility
            content_for_llm = tool_output

            if isinstance(tool_output, dict):
                # If it's our standard ToolResult, extract the specific llm_content part
                if 'llm_content' in tool_output:
                    content_for_llm = tool_output['llm_content']
                
                # Check for error status in the standard ToolResult
                if tool_output.get("status") == "error":
                    return {
                        "type": "tool_result",
                        "tool_use_id": tool_id,
                        "name": tool_name,
                        "content": tool_output.get("message", "Tool execution failed."),
                        "is_error": True
                    }
            
            return content_for_llm

        except Exception as e:
            if debug:
                print(f"Error calling tool {tool_name}: {str(e)}")
            return {
                "type": "tool_result",
                "tool_use_id": tool_id,
                "name": tool_name,
                "content": f"Error: Tool execution failed - {str(e)}",
                "is_error": True
            } 