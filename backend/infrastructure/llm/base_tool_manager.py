"""
BaseToolManager - 所有LLM客户端Tool Manager的抽象基类

专为aiNagisa多LLM架构设计的统一工具管理接口。
定义了所有Tool Manager必须实现的核心方法，确保一致性和可扩展性。
"""

import json
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Set
from fastmcp import Client as MCPClient
from mcp.types import Implementation, CallToolRequestParams, CallToolRequest, ClientRequest, CallToolResult

from backend.infrastructure.mcp.smart_mcp_server import mcp as GLOBAL_MCP
from backend.infrastructure.mcp.utils import extract_tool_result_from_mcp


class BaseToolManager(ABC):
    """
    LLM客户端工具管理器的抽象基类
    
    定义了统一的接口规范，支持：
    - MCP客户端管理和会话隔离
    - 工具schema检索和缓存
    - Meta工具处理和结果解析
    - 工具执行和结果格式化
    - 客户端特定的schema格式化
    """
    
    def __init__(self, mcp_client_source=None, tools_enabled: bool = True):
        """初始化基础状态"""
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
        确保每个聊天会话的MCP Session保持隔离。
        
        Args:
            session_id: 可选的会话ID，用于客户端隔离
            
        Returns:
            MCPClient 会话专用实例
        """
        # 如果源已经是MCPClient实例，直接复用
        if isinstance(self._mcp_client_source, MCPClient):
            return self._mcp_client_source
        
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
        检查是否为meta工具
        
        Args:
            tool_name: 工具名称
            
        Returns:
            bool: 如果是meta工具返回True
        """
        return tool_name in {
            "search_tools_by_keywords",
            "get_available_tool_categories",
            "search_tools",  # Gemini客户端使用的名称
        }
    
    def extract_tools_from_meta_result(self, meta_result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        从meta工具结果中提取工具信息
        
        Args:
            meta_result: meta工具执行结果（标准ToolResult格式）
            
        Returns:
            List: 解析后的工具信息列表
        """
        if not isinstance(meta_result, dict) or "data" not in meta_result:
            return []
        
        data = meta_result["data"]
        if not isinstance(data, dict) or "tools" not in data:
            return []
        
        tools_data = data["tools"]
        if not isinstance(tools_data, list):
            return []
        
        processed_tools = []
        for tool_info in tools_data:
            if not isinstance(tool_info, dict) or "name" not in tool_info:
                continue
            
            # 直接使用meta工具返回的标准化工具信息
            # meta工具已经处理了parameters格式转换
            processed_tools.append({
                "name": tool_info["name"],
                "description": tool_info.get("description", ""),
                "category": tool_info.get("category", "general"),
                "docstring": tool_info.get("docstring", ""),
                "inputSchema": tool_info.get("parameters", {}),
                "parameters": tool_info.get("parameters", {}),  # 保持向后兼容
                "tags": tool_info.get("tags", [])
            })
        
        return processed_tools
    
    def cache_tools_for_session(self, session_id: str, tools: List[Dict[str, Any]]) -> None:
        """
        为特定会话缓存工具
        
        Args:
            session_id: 会话ID
            tools: 要缓存的工具列表
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
        获取特定会话的缓存工具
        
        Args:
            session_id: 会话ID
            
        Returns:
            List: 缓存的工具列表
        """
        return self.session_tool_cache.get(session_id, [])
    
    def clear_session_tool_cache(self, session_id: str) -> None:
        """
        清除特定会话的工具缓存
        
        Args:
            session_id: 要清除缓存的会话ID
        """
        if session_id in self.session_tool_cache:
            del self.session_tool_cache[session_id]
    
    @abstractmethod
    async def get_function_call_schemas(self, session_id: Optional[str] = None, debug: bool = False) -> Any:
        """
        获取所有MCP工具的schema，返回适合目标LLM的格式
        只返回meta tools + cached tools，不返回所有regular tools
        
        Args:
            session_id: 可选的会话ID，用于工具缓存
            debug: 是否启用调试输出
            
        Returns:
            适配目标LLM格式的工具schema列表（格式因客户端而异）
        """
        pass
    
    async def _handle_meta_tool(self, tool_name: str, tool_args: Dict[str, Any], tool_id: str, 
                               session_id: Optional[str] = None, debug: bool = False) -> Any:
        """
        处理meta工具调用
        
        Args:
            tool_name: 工具名称
            tool_args: 工具参数
            tool_id: 工具调用ID
            session_id: 可选的会话ID
            debug: 是否启用调试输出
            
        Returns:
            Any: Meta工具执行结果
        """
        
        if debug:
            print(f"[DEBUG] Handling meta tool: {tool_name}")
        
        try:
            # 执行meta工具
            result = await self._execute_mcp_tool(tool_name, tool_args, session_id)
            text_result = extract_tool_result_from_mcp(result)
            
            # 检查执行错误
            if isinstance(result, dict) and result.get("error"):
                return self._create_error_response(tool_id, tool_name, text_result)
            
            # 缓存搜索工具的结果
            if tool_name in ["search_tools_by_keywords", "search_tools"] and session_id:
                await self._cache_meta_tool_results(result, text_result, session_id, debug)
            
            return text_result
            
        except Exception as e:
            if debug:
                print(f"Error calling meta tool {tool_name}: {str(e)}")
            return self._create_error_response(
                tool_id, tool_name, f"Error: Meta tool execution failed - {str(e)}"
            )
    
    async def _handle_regular_tool(self, tool_name: str, tool_args: Dict[str, Any], tool_id: str,
                                  session_id: Optional[str] = None, debug: bool = False) -> Any:
        """
        处理普通工具调用
        
        Args:
            tool_name: 工具名称
            tool_args: 工具参数
            tool_id: 工具调用ID
            session_id: 可选的会话ID
            debug: 是否启用调试输出
            
        Returns:
            Any: 工具执行结果，传递给LLM
        """
        try:
            # 执行普通工具
            result_obj = await self._execute_mcp_tool(tool_name, tool_args, session_id)
            tool_result = extract_tool_result_from_mcp(result_obj)
            
            # 检查MCP层面的错误（is_error字段）
            if tool_result.get("is_error"):
                return self._create_error_response(
                    tool_id, tool_name, tool_result.get("content", "Tool execution failed.")
                )
            
            # 处理多模态内容：检查是否有inline_data并提取
            if self._has_multimodal_content(tool_result):
                return self._extract_multimodal_content(tool_result)
            
            # 普通内容：也使用统一的内容提取方法
            return self._extract_regular_content(tool_result)
            
        except Exception as e:
            if debug:
                print(f"Error calling tool {tool_name}: {str(e)}")
            return self._create_error_response(
                tool_id, tool_name, f"Error: Tool execution failed - {str(e)}"
            )
    
    async def _execute_mcp_tool(self, tool_name: str, tool_args: Dict[str, Any], 
                               session_id: Optional[str] = None) -> Any:
        """
        执行MCP工具调用的统一方法
        
        Args:
            tool_name: 工具名称
            tool_args: 工具参数
            session_id: 可选的会话ID
            
        Returns:
            Any: MCP工具执行结果
        """
        mcp_client = self.get_mcp_client(session_id)
        async with mcp_client as mcp_async_client:
            if session_id:
                try:
                    # 尝试使用带会话ID的调用方式
                    params = CallToolRequestParams(
                        name=tool_name,
                        arguments=tool_args,
                        **{"_meta": {"client_id": session_id}},
                    )
                    call_req = ClientRequest(CallToolRequest(method="tools/call", params=params))
                    return await mcp_async_client.session.send_request(call_req, CallToolResult)
                except Exception:
                    # 降级到标准调用方式
                    return await mcp_async_client.call_tool(tool_name, tool_args)
            else:
                return await mcp_async_client.call_tool(tool_name, tool_args)
    
    async def _cache_meta_tool_results(self, result: Any, text_result: Any, 
                                      session_id: str, debug: bool = False) -> None:
        """
        缓存meta工具的搜索结果
        
        Args:
            result: 原始MCP工具结果
            text_result: 提取后的文本结果
            session_id: 会话ID
            debug: 是否启用调试输出
        """
        
        try:
            meta_result = {}
            
            # 解析不同格式的结果对象
            if hasattr(result, 'content') and result.content:
                # MCP CallToolResult对象
                if hasattr(result.content[0], 'text'):
                    try:
                        meta_result = json.loads(result.content[0].text)
                    except (json.JSONDecodeError, TypeError):
                        meta_result = {}
            elif isinstance(result, dict):
                # 直接的字典结果
                meta_result = result
            else:
                # 从text_result解析（兼容性处理）
                if isinstance(text_result, dict):
                    meta_result = text_result
                elif isinstance(text_result, str):
                    try:
                        meta_result = json.loads(text_result)
                    except (json.JSONDecodeError, TypeError):
                        meta_result = {}
            
            if debug:
                print(f"[DEBUG] Meta result structure: {type(meta_result)}")
                if isinstance(meta_result, dict):
                    print(f"[DEBUG] Meta result keys: {list(meta_result.keys())}")
            
            # 提取并缓存工具信息
            extracted_tools = self.extract_tools_from_meta_result(meta_result)
            if extracted_tools:
                self.cache_tools_for_session(session_id, extracted_tools)
                if debug:
                    print(f"[DEBUG] Cached {len(extracted_tools)} tools for session {session_id}")
                    for tool in extracted_tools:
                        print(f"[DEBUG]   - {tool['name']}: {tool.get('description', '')}")
            else:
                if debug:
                    print(f"[DEBUG] No tools extracted from meta result")
                    
        except Exception as e:
            if debug:
                print(f"[DEBUG] Failed to cache tools from meta result: {e}")
                import traceback
                print(f"[DEBUG] Traceback: {traceback.format_exc()}")
    
    def _has_multimodal_content(self, tool_result: Dict[str, Any]) -> bool:
        """
        检查ToolResult是否包含多模态内容
        
        Args:
            tool_result: 完整的ToolResult字典
            
        Returns:
            bool: 是否包含多模态内容
        """
        return (
            tool_result.get("data", {})
            .get("processing_result", {})
            .get("content_format") == "inline_data"
        )
    
    def _extract_multimodal_content(self, tool_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        提取多模态内容，合并llm_content和inline_data
        
        Args:
            tool_result: 完整的ToolResult字典
            
        Returns:
            Dict: 合并后的内容，包含inline_data
        """
        llm_content = tool_result.get("llm_content", {})
        inline_data = (
            tool_result.get("data", {})
            .get("processing_result", {})
            .get("content", {})
            .get("inline_data", {})
        )
        
        return {
            **llm_content,
            "inline_data": inline_data
        }
    
    def _extract_regular_content(self, tool_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        提取普通内容，包装在llm_content字段中，与多模态内容格式对齐
        
        Args:
            tool_result: 完整的ToolResult字典
            
        Returns:
            Dict: 包含llm_content字段的字典，与多模态内容格式一致
        """
        return {
            "llm_content": tool_result.get("llm_content")
        }
    
    def _create_error_response(self, tool_id: str, tool_name: str, error_message: str) -> Dict[str, Any]:
        """
        创建标准化的错误响应
        
        Args:
            tool_id: 工具调用ID
            tool_name: 工具名称
            error_message: 错误消息
            
        Returns:
            Dict: 标准化的错误响应结构
        """
        return {
            "type": "tool_result",
            "tool_use_id": tool_id,
            "name": tool_name,
            "content": error_message,
            "is_error": True
        }
    
    async def handle_function_call(self, function_call: dict, session_id: Optional[str] = None, debug: bool = False) -> Any:
        """
        处理LLM生成的function_call请求，优雅地分发到对应的工具处理器
        
        Args:
            function_call: 函数调用字典，包含name、arguments等
            session_id: 可选的会话ID，用于上下文感知的工具
            debug: 是否启用调试输出
            
        Returns:
            Any: 工具执行结果或错误信息
        """
        tool_name = function_call["name"]
        tool_args = function_call.get("arguments", {})
        tool_id = function_call.get("id", "")
        
        # 根据工具类型分发到相应的处理器
        if self.is_meta_tool(tool_name):
            return await self._handle_meta_tool(tool_name, tool_args, tool_id, session_id, debug)
        else:
            return await self._handle_regular_tool(tool_name, tool_args, tool_id, session_id, debug)