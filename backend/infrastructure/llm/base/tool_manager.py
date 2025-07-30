"""
BaseToolManager - Abstract base class for all LLM client Tool Managers.

Designed for aiNagisa's multi-LLM architecture as a unified tool management interface.
Defines core methods that all Tool Managers must implement to ensure consistency and extensibility.
"""

import json
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Set
from fastmcp import Client as MCPClient
from mcp.types import Implementation, CallToolRequestParams, CallToolRequest, ClientRequest, CallToolResult

from backend.infrastructure.mcp.smart_mcp_server import mcp as GLOBAL_MCP
from backend.infrastructure.mcp.utils import extract_tool_result_from_mcp
# Security imports removed - all tools now require session ID


class BaseToolManager(ABC):
    """
    Abstract base class for LLM client tool managers.
    
    Defines unified interface specifications supporting:
    - MCP client management and session isolation
    - Tool schema retrieval and caching
    - Meta tool processing and result parsing
    - Tool execution and result formatting
    - Client-specific schema formatting
    """
    
    def __init__(self, mcp_client_source=None, tools_enabled: bool = True):
        """Initialize base state."""
        self._mcp_client_source = mcp_client_source or GLOBAL_MCP
        self.tools_enabled = tools_enabled
        
        # Cache MCPClient instances by chat_session_id; None represents default/no session
        self._mcp_clients: Dict[str | None, MCPClient] = {}
        
        # Tool caching mechanism
        self.tool_cache: Dict[str, Any] = {}
        self.meta_tools: Set[str] = set()
        # Session-level tool cache: {session_id: List[tool_schema]}
        self.session_tool_cache: Dict[str, List[Dict[str, Any]]] = {}
    
    def get_mcp_client(self, session_id: Optional[str] = None) -> MCPClient:
        """
        Return (and cache) an MCPClient bound to *session_id*.
        Ensures each chat session's MCP Session remains isolated.
        
        Args:
            session_id: Optional session ID for client isolation
            
        Returns:
            MCPClient session-specific instance
        """
        # If source is already an MCPClient instance, reuse directly
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
        Check if this is a meta tool.
        
        Args:
            tool_name: Tool name
            
        Returns:
            bool: True if it's a meta tool
        """
        return tool_name in {
            "search_tools_by_keywords",
            "get_available_tool_categories",
            "search_tools",  # Name used by Gemini client
        }
    
    async def extract_tools_from_meta_result(self, meta_result: Dict[str, Any], session_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Extract tool information from meta tool result and get live schemas from MCP server.
        
        Args:
            meta_result: Meta tool execution result (standard ToolResult format)
            session_id: Optional session ID for MCP client
            
        Returns:
            List: Parsed tool information list with live schemas
        """
        if not isinstance(meta_result, dict) or "data" not in meta_result:
            return []
        
        data = meta_result["data"]
        if not isinstance(data, dict) or "tools" not in data:
            return []
        
        tools_data = data["tools"]
        if not isinstance(tools_data, list):
            return []
        
        # Extract tool names from meta result (discovery from vector DB)
        tool_names = []
        meta_info = {}
        for tool_info in tools_data:
            if not isinstance(tool_info, dict) or "name" not in tool_info:
                continue
            tool_name = tool_info["name"]
            tool_names.append(tool_name)
            # Store meta info (description, category, tags) but not schema
            meta_info[tool_name] = {
                "description": tool_info.get("description", ""),
                "category": tool_info.get("category", "general"),
                "docstring": tool_info.get("docstring", ""),
                "tags": tool_info.get("tags", [])
            }
        
        if not tool_names:
            return []
        
        # Get live schemas from MCP server
        processed_tools = []
        try:
            mcp_client = self.get_mcp_client(session_id)
            async with mcp_client as mcp_async_client:
                mcp_tools_result = await mcp_async_client.list_tools()
                
                # Handle different return formats from MCP client
                if hasattr(mcp_tools_result, 'tools'):
                    mcp_tools = mcp_tools_result.tools
                elif isinstance(mcp_tools_result, list):
                    mcp_tools = mcp_tools_result
                else:
                    mcp_tools = []
                
                # Match tools by name and use live schema
                for mcp_tool in mcp_tools:
                    tool_name = mcp_tool.name
                    if tool_name in tool_names:
                        # Use live schema from MCP server
                        input_schema = getattr(mcp_tool, "inputSchema", {}) or {}
                        
                        # Combine live schema with meta info
                        tool_data = {
                            "name": tool_name,
                            "inputSchema": input_schema,
                            "parameters": input_schema,  # Maintain backward compatibility
                        }
                        
                        # Add meta info if available, otherwise use MCP tool info
                        if tool_name in meta_info:
                            tool_data.update(meta_info[tool_name])
                        else:
                            tool_data.update({
                                "description": mcp_tool.description or "",
                                "category": "general",
                                "docstring": mcp_tool.description or "",
                                "tags": []
                            })
                        
                        processed_tools.append(tool_data)
        
        except Exception as e:
            print(f"[WARNING] Failed to get live schemas from MCP server: {e}")
            # Fallback to original behavior (using cached parameters)
            for tool_info in tools_data:
                if not isinstance(tool_info, dict) or "name" not in tool_info:
                    continue
                
                processed_tools.append({
                    "name": tool_info["name"],
                    "description": tool_info.get("description", ""),
                    "category": tool_info.get("category", "general"),
                    "docstring": tool_info.get("docstring", ""),
                    "inputSchema": tool_info.get("parameters", {}),
                    "parameters": tool_info.get("parameters", {}),  # Maintain backward compatibility
                    "tags": tool_info.get("tags", [])
                })
        
        return processed_tools
    
    def cache_tools_for_session(self, session_id: str, tools: List[Dict[str, Any]]) -> None:
        """
        Cache tools for specific session.
        
        Args:
            session_id: Session ID
            tools: Tools list to cache
        """
        if session_id not in self.session_tool_cache:
            self.session_tool_cache[session_id] = []
        
        # Add new tools, avoid duplicates
        existing_names = {tool["name"] for tool in self.session_tool_cache[session_id]}
        for tool in tools:
            if tool["name"] not in existing_names:
                self.session_tool_cache[session_id].append(tool)
                existing_names.add(tool["name"])
    
    def get_cached_tools_for_session(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Get cached tools for specific session.
        
        Args:
            session_id: Session ID
            
        Returns:
            List: Cached tools list
        """
        return self.session_tool_cache.get(session_id, [])
    
    def clear_session_tool_cache(self, session_id: str) -> None:
        """
        Clear tool cache for specific session.
        
        Args:
            session_id: Session ID to clear cache for
        """
        if session_id in self.session_tool_cache:
            del self.session_tool_cache[session_id]
    
    @abstractmethod
    async def get_function_call_schemas(self, session_id: Optional[str] = None, debug: bool = False) -> Any:
        """
        Get all MCP tool schemas, return format suitable for target LLM.
        Only return meta tools + cached tools, not all regular tools.
        
        Args:
            session_id: Optional session ID for tool caching
            debug: Whether to enable debug output
            
        Returns:
            Tool schema list adapted for target LLM format (format varies by client)
        """
        pass
    
    async def _handle_meta_tool(self, tool_name: str, tool_args: Dict[str, Any], tool_id: str, 
                               session_id: Optional[str] = None, debug: bool = False) -> Any:
        """
        Handle meta tool call.
        
        Args:
            tool_name: Tool name
            tool_args: Tool arguments
            tool_id: Tool call ID
            session_id: Optional session ID
            debug: Whether to enable debug output
            
        Returns:
            Any: Meta tool execution result
        """
        
        if debug:
            print(f"[DEBUG] Handling meta tool: {tool_name}")
        
        try:
            # Execute meta tool
            result = await self._execute_mcp_tool(tool_name, tool_args, session_id)
            text_result = extract_tool_result_from_mcp(result)
            
            # Check execution error - return tool's original error structure
            if isinstance(result, dict) and result.get("error"):
                return text_result
            
            # Cache results from search tools
            if tool_name in ["search_tools_by_keywords", "search_tools"] and session_id:
                await self._cache_meta_tool_results(result, text_result, session_id, debug)
            
            return text_result
            
        except (ValueError, PermissionError) as e:
            # Security policy violations - provide clear error messages
            if debug:
                print(f"Security policy violation for meta tool {tool_name}: {str(e)}")
            return self._create_error_response(tool_id, tool_name, f"Security Error: {str(e)}")
        except Exception as e:
            if debug:
                print(f"Error calling meta tool {tool_name}: {str(e)}")
            return self._create_error_response(
                tool_id, tool_name, f"Error: Meta tool execution failed - {str(e)}"
            )
    
    async def _handle_regular_tool(self, tool_name: str, tool_args: Dict[str, Any], tool_id: str,
                                  session_id: Optional[str] = None, debug: bool = False) -> Any:
        """
        Handle regular tool call.
        
        Args:
            tool_name: Tool name
            tool_args: Tool arguments
            tool_id: Tool call ID
            session_id: Optional session ID
            debug: Whether to enable debug output
            
        Returns:
            Any: Tool execution result passed to LLM
        """
        try:
            # Execute regular tool
            result_obj = await self._execute_mcp_tool(tool_name, tool_args, session_id)
            tool_result = extract_tool_result_from_mcp(result_obj)
            
            # Check MCP-level errors (is_error field) - return tool's original error structure
            if tool_result.get("is_error"):
                return tool_result
            
            # Handle multimodal content: check for inline_data and extract
            if self._has_multimodal_content(tool_result):
                return self._extract_multimodal_content(tool_result)
            
            # Regular content: also use unified content extraction method
            return self._extract_regular_content(tool_result)
            
        except (ValueError, PermissionError) as e:
            # Security policy violations - provide clear error messages
            if debug:
                print(f"Security policy violation for tool {tool_name}: {str(e)}")
            return self._create_error_response(tool_id, tool_name, f"Security Error: {str(e)}")
        except Exception as e:
            if debug:
                print(f"Error calling tool {tool_name}: {str(e)}")
            return self._create_error_response(
                tool_id, tool_name, f"Error: Tool execution failed - {str(e)}"
            )
    
    async def _execute_mcp_tool(self, tool_name: str, tool_args: Dict[str, Any], 
                               session_id: Optional[str] = None) -> Any:
        """
        Unified method for executing MCP tool calls with mandatory session injection.
        
        Args:
            tool_name: Tool name
            tool_args: Tool arguments
            session_id: Session ID (required for all tools)
            
        Returns:
            Any: MCP tool execution result
            
        Raises:
            ValueError: If session ID is not provided
        """
        # All tools now require session ID for dependency injection
        if session_id is None:
            raise ValueError(
                f"Tool '{tool_name}' requires session ID for dependency injection. "
                f"All tools must be executed with session context."
            )
        
        mcp_client = self.get_mcp_client(session_id)
        async with mcp_client as mcp_async_client:
            # Always use session ID-aware call method
            params = CallToolRequestParams(
                name=tool_name,
                arguments=tool_args,
                **{"_meta": {"client_id": session_id}},
            )
            call_req = ClientRequest(CallToolRequest(method="tools/call", params=params))
            return await mcp_async_client.session.send_request(call_req, CallToolResult)
    
    async def _cache_meta_tool_results(self, result: Any, text_result: Any, 
                                      session_id: str, debug: bool = False) -> None:
        """
        Cache meta tool search results.
        
        Args:
            result: Raw MCP tool result
            text_result: Extracted text result
            session_id: Session ID
            debug: Whether to enable debug output
        """
        
        try:
            meta_result = {}
            
            # Parse different formats of result objects
            if hasattr(result, 'content') and result.content:
                # MCP CallToolResult object
                if hasattr(result.content[0], 'text'):
                    try:
                        meta_result = json.loads(result.content[0].text)
                    except (json.JSONDecodeError, TypeError):
                        meta_result = {}
            elif isinstance(result, dict):
                # Direct dictionary result
                meta_result = result
            else:
                # Parse from text_result (compatibility handling)
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
            
            # Extract and cache tool information
            extracted_tools = await self.extract_tools_from_meta_result(meta_result, session_id)
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
        Check if ToolResult contains multimodal content.
        
        Args:
            tool_result: Complete ToolResult dictionary
            
        Returns:
            bool: Whether it contains multimodal content
        """
        return (
            tool_result.get("data", {})
            .get("processing_result", {})
            .get("content_format") == "inline_data"
        )
    
    def _extract_multimodal_content(self, tool_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract multimodal content, merge llm_content and inline_data.
        
        Args:
            tool_result: Complete ToolResult dictionary
            
        Returns:
            Dict: Merged content including inline_data
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
        Extract regular content, wrapped in llm_content field, aligned with multimodal content format.
        
        Args:
            tool_result: Complete ToolResult dictionary
            
        Returns:
            Dict: Dictionary containing llm_content field, consistent with multimodal content format
        """
        return {
            "llm_content": tool_result.get("llm_content")
        }
    
    def _create_error_response(self, tool_id: str, tool_name: str, error_message: str) -> Dict[str, Any]:
        """
        Create standardized error response.
        
        Args:
            tool_id: Tool call ID
            tool_name: Tool name
            error_message: Error message
            
        Returns:
            Dict: Standardized error response structure
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
        Handle LLM-generated function_call requests, gracefully dispatch to corresponding tool handlers.
        
        Args:
            function_call: Function call dictionary containing name, arguments, etc.
            session_id: Optional session ID for context-aware tools
            debug: Whether to enable debug output
            
        Returns:
            Any: Tool execution result or error information
        """
        tool_name = function_call["name"]
        tool_args = function_call.get("arguments", {})
        tool_id = function_call.get("id", "")
        
        # Dispatch to appropriate handler based on tool type
        if self.is_meta_tool(tool_name):
            return await self._handle_meta_tool(tool_name, tool_args, tool_id, session_id, debug)
        else:
            return await self._handle_regular_tool(tool_name, tool_args, tool_id, session_id, debug)