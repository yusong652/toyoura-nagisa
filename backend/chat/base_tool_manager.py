"""
BaseToolManager - 所有LLM客户端Tool Manager的抽象基类

专为aiNagisa多LLM架构设计的统一工具管理接口。
定义了所有Tool Manager必须实现的核心方法，确保一致性和可扩展性。
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Set
from fastmcp import Client as MCPClient
from mcp.types import Implementation, CallToolRequestParams, CallToolRequest, ClientRequest, CallToolResult

from backend.nagisa_mcp.smart_mcp_server import mcp as GLOBAL_MCP
from backend.nagisa_mcp.utils import extract_text_from_mcp_result


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
            meta_result: meta工具执行结果
            
        Returns:
            List: 解析后的工具信息列表
        """
        import json
        
        tools = []
        if isinstance(meta_result, dict):
            # 处理不同格式的meta工具结果
            tools_data = None
            
            # 检查data字段中的tools（标准ToolResult格式）
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
                                params = {}
                        
                        # 解析 tags
                        tags = tool_info.get("tags", [])
                        if isinstance(tags, str):
                            try:
                                tags = json.loads(tags)
                            except (json.JSONDecodeError, TypeError):
                                tags = []
                        
                        # 转换parameters格式为标准的JSON Schema inputSchema
                        if isinstance(params, dict):
                            if "type" in params and "properties" in params:
                                # 已经是完整的inputSchema格式
                                input_schema = params
                            else:
                                # 从tool vectorizer格式转换为JSON Schema格式
                                properties = {}
                                required = []
                                
                                for param_name, param_info in params.items():
                                    if isinstance(param_info, dict):
                                        # 转换类型名称
                                        param_type = param_info.get('type', 'string')
                                        if param_type.startswith('<class \'') and param_type.endswith('\'>'):
                                            # 从 <class 'str'> 格式提取类型
                                            param_type = param_type.split('\'')[1]
                                        
                                        # 映射Python类型到JSON Schema类型
                                        type_mapping = {
                                            'str': 'string',
                                            'int': 'integer', 
                                            'float': 'number',
                                            'bool': 'boolean',
                                            'list': 'array',
                                            'dict': 'object'
                                        }
                                        json_type = type_mapping.get(param_type, 'string')
                                        
                                        properties[param_name] = {
                                            "type": json_type,
                                            "description": f"Parameter {param_name}"
                                        }
                                        
                                        # 检查是否必需
                                        if param_info.get('required', True):
                                            required.append(param_name)
                                    else:
                                        # 简单格式处理
                                        properties[param_name] = {
                                            "type": "string",
                                            "description": f"Parameter {param_name}"
                                        }
                                        required.append(param_name)
                                
                                input_schema = {
                                    "type": "object",
                                    "properties": properties,
                                    "required": required,
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
                        
                        tools.append({
                            "name": tool_info["name"],
                            "description": tool_info.get("description", ""),
                            "category": tool_info.get("category", "general"),
                            "docstring": tool_info.get("docstring", ""),
                            "inputSchema": input_schema,  # 使用标准的inputSchema字段名
                            "parameters": input_schema,   # 保持向后兼容
                            "tags": tags
                        })
        return tools
    
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
    
    async def handle_function_call(self, function_call: dict, session_id: Optional[str] = None, debug: bool = False):
        """
        处理LLM生成的function_call请求，分发到MCP工具
        
        Args:
            function_call: 函数调用字典，包含name、arguments等
            session_id: 可选的会话ID，用于上下文感知的工具
            debug: 是否启用调试输出
            
        Returns:
            Any: 工具执行结果或错误信息
        """
        import json
        
        tool_name = function_call["name"]
        tool_args = function_call.get("arguments", {})
        tool_id = function_call.get("id", "")
        
        # 1. Meta工具处理
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
                    else:
                        result = await mcp_async_client.call_tool(tool_name, tool_args)
                
                text_result = extract_text_from_mcp_result(result)
                
                # 检查错误
                if isinstance(result, dict) and result.get("error"):
                    return {
                        "type": "tool_result",
                        "tool_use_id": tool_id,
                        "name": tool_name,
                        "content": text_result,
                        "is_error": True
                    }
                
                # 缓存meta工具结果 - 从完整的result对象中提取，而不是从text_result中
                if tool_name in ["search_tools_by_keywords", "search_tools"] and session_id:
                    try:
                        # 使用完整的result对象进行工具提取
                        meta_result = {}
                        
                        # 处理不同类型的result对象
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
                            # 尝试从text_result解析（兼容性处理）
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
                
                return text_result
                
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
        
        # 2. 普通工具处理
        try:
            mcp_client = self.get_mcp_client(session_id)
            async with mcp_client as mcp_async_client:
                # 注入会话ID（如果存在）
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
            
            # 提取工具输出
            tool_output = extract_text_from_mcp_result(result_obj)
            
            # 检查错误状态
            if isinstance(tool_output, dict):
                if tool_output.get("status") == "error":
                    return {
                        "type": "tool_result",
                        "tool_use_id": tool_id,
                        "name": tool_name,
                        "content": tool_output.get("message", "Tool execution failed."),
                        "is_error": True
                    }
                
                # 处理multimodal内容（如inline_data）
                has_inline_data = False
                if ('data' in tool_output and 
                    isinstance(tool_output['data'], dict) and
                    'processing_result' in tool_output['data'] and
                    isinstance(tool_output['data']['processing_result'], dict)):
                    
                    processing_result = tool_output['data']['processing_result']
                    if (processing_result.get('content_format') == 'inline_data' and
                        'content' in processing_result and
                        isinstance(processing_result['content'], dict) and
                        'inline_data' in processing_result['content']):
                        
                        has_inline_data = True
                        inline_data_content = processing_result['content']
                        
                        if debug:
                            print(f"[DEBUG] Detected inline_data in {tool_name} result")
                
                # 如果有inline_data，返回包含多媒体内容的结构
                if has_inline_data:
                    return {
                        **tool_output.get('llm_content', {}),
                        'inline_data': inline_data_content['inline_data']
                    }
                
                # 提取llm_content（如果有）
                if 'llm_content' in tool_output:
                    return tool_output['llm_content']
            
            return tool_output
        
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