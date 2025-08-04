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
from backend.infrastructure.llm.shared.utils.tool_schema import ToolSchema
from backend.shared.utils.tool_utils import is_meta_tool
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
    
    def __init__(self, tools_enabled: bool = True):
        """Initialize base state."""
        self.tools_enabled = tools_enabled
        
        # Single shared MCP client - FastMCP handles session isolation per request
        self._mcp_client = MCPClient(
            GLOBAL_MCP,
            client_info=Implementation(name="aiNagisa_shared", version="0.1.0")
        )
        
        # Tool caching mechanism
        self.tool_cache: Dict[str, Any] = {}
        self.meta_tools: Set[str] = set()
        # Session-level tool cache: {session_id: List[ToolSchema]}
        self.session_tool_cache: Dict[str, List[ToolSchema]] = {}
    
    def get_mcp_client(self) -> MCPClient:
        """
        Return the shared MCP client. FastMCP handles session isolation per request
        through the _meta.client_id parameter in tool calls.
        
        Returns:
            MCPClient: Shared client instance
        """
        return self._mcp_client
    
    def is_meta_tool(self, tool_name: str) -> bool:
        """
        Check if this is a meta tool.
        
        Args:
            tool_name: Tool name
            
        Returns:
            bool: True if it's a meta tool
        """
        return is_meta_tool(tool_name)
    
    async def extract_tools_from_meta_result(self, meta_result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract tool information from meta tool result and get live schemas from MCP server.
        
        Args:
            meta_result: Meta tool execution result (standard ToolResult format)
            
        Returns:
            List: Parsed tool information list with live schemas
        """
        # Extract tools data from meta result - guaranteed standard format
        tools_data = meta_result["data"]["tools"] # Format: [{"name": "tool_name", ...}, ...]
        
        # Extract tool names from meta result - simplified format
        discovered_tool_names = [tool_info["name"] for tool_info in tools_data]
        
        # Get live schemas from MCP server for all discovered tools
        mcp_client = self.get_mcp_client()
        async with mcp_client:
            registered_mcp_tools = await mcp_client.list_tools()
            
            # Build tool name to MCP tool mapping for O(1) lookup
            mcp_tools_map = {tool.name: tool for tool in registered_mcp_tools}
            
            # Match and build final tools with live schemas
            return [
                {
                    "name": tool_name,
                    "description": mcp_tools_map[tool_name].description or "",
                    "inputSchema": getattr(mcp_tools_map[tool_name], "inputSchema", {}) or {}
                }
                for tool_name in discovered_tool_names
                if tool_name in mcp_tools_map
            ]
    
    def cache_tools_for_session(self, session_id: str, tools: List[Dict[str, Any]]) -> None:
        """
        Cache tools for specific session. Converts dict tools to ToolSchema objects.
        
        Args:
            session_id: Session ID
            tools: Tools list to cache (in dict format)
        """
        if session_id not in self.session_tool_cache:
            self.session_tool_cache[session_id] = []
        
        # Convert dict tools to ToolSchema objects and add new tools, avoid duplicates
        existing_names = {tool.name for tool in self.session_tool_cache[session_id]}
        for tool_dict in tools:
            tool_name = tool_dict["name"]
            if tool_name not in existing_names:
                tool_schema = ToolSchema.from_dict(tool_dict)
                self.session_tool_cache[session_id].append(tool_schema)
                existing_names.add(tool_name)
    
    def get_cached_tools_for_session(self, session_id: str) -> List[ToolSchema]:
        """
        Get cached tools for specific session.
        
        Args:
            session_id: Session ID
            
        Returns:
            List[ToolSchema]: Cached tools list
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
    
    async def get_standardized_tools(self, session_id: str, debug: bool = False) -> Dict[str, ToolSchema]:
        """
        Get standardized ToolSchema objects for meta tools + cached tools.
        This method provides the unified tool data that providers can then format.
        
        Args:
            session_id: Session ID for tool caching (required)
            debug: Whether to enable debug output
            
        Returns:
            Dict[str, ToolSchema]: Tool name -> ToolSchema mapping
        """
        if not self.tools_enabled:
            return {}
        
        tools_dict: Dict[str, ToolSchema] = {}
        
        try:
            mcp_client = self.get_mcp_client()
            async with mcp_client as mcp_async_client:
                # Get all MCP tools - list_tools() always returns a list
                mcp_tools = await mcp_async_client.list_tools()
                
                # Add meta tools first (never vectorized, always available)
                for mcp_tool in mcp_tools:
                    if self.is_meta_tool(mcp_tool.name):
                        tool_schema = ToolSchema.from_mcp_tool(mcp_tool)
                        tools_dict[tool_schema.name] = tool_schema
                
                # Add cached tools (no conflict possible since meta tools are never cached)
                cached_tools = self.get_cached_tools_for_session(session_id)
                for cached_tool in cached_tools:
                    tools_dict[cached_tool.name] = cached_tool

                return tools_dict
                
        except Exception as e:
            if debug:
                print(f"[DEBUG] Error getting standardized tools: {e}")
            return {}

    @abstractmethod
    async def get_function_call_schemas(self, session_id: str, debug: bool = False) -> Any:
        """
        Get tool schemas formatted for the specific LLM provider.
        Uses get_standardized_tools() internally, then converts to provider format.
        
        Args:
            session_id: Session ID for tool caching (required)
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
        # tool_id is unused but kept for API compatibility
        _ = tool_id
        
        if debug:
            print(f"[DEBUG] Handling meta tool: {tool_name}")
        
        try:
            # Execute meta tool
            result = await self._execute_mcp_tool(tool_name, tool_args, session_id)
            tool_result = extract_tool_result_from_mcp(result)
            
            # Cache results from search tools
            if tool_name in ["search_tools"] and session_id:
                await self._cache_meta_tool_results(tool_result, session_id, debug)
            
            return tool_result
            
        except Exception as e:
            # System/infrastructure errors - re-raise for upper layer handling
            if debug:
                print(f"Error calling meta tool {tool_name}: {str(e)}")
            raise RuntimeError(f"Meta tool '{tool_name}' execution failed: {str(e)}") from e
    
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
        # tool_id is unused but kept for API compatibility
        _ = tool_id
        
        try:
            # Execute regular tool
            call_tool_result = await self._execute_mcp_tool(tool_name, tool_args, session_id)
            tool_result = extract_tool_result_from_mcp(call_tool_result)
            
            # Check MCP-level errors (is_error field) - return tool's original error structure
            if tool_result.get("is_error"):
                return tool_result
            
            # Unified handling: always return inline_data + llm_content structure
            if self._has_multimodal_content(tool_result):
                inline_data = self._extract_multimodal_content(tool_result)
            else:
                inline_data = {}  # Empty for non-multimodal content
            
            return {
                "inline_data": inline_data,
                "llm_content": tool_result.get("llm_content")
            }
            
        except Exception as e:
            # System/infrastructure errors - re-raise for upper layer handling
            if debug:
                print(f"Error calling tool {tool_name}: {str(e)}")
            raise RuntimeError(f"Tool '{tool_name}' execution failed: {str(e)}") from e
    
    async def _execute_mcp_tool(self, tool_name: str, tool_args: Dict[str, Any], 
                               session_id: Optional[str] = None) -> CallToolResult:
        """
        Unified method for executing MCP tool calls with mandatory session injection.
        
        Args:
            tool_name: Tool name
            tool_args: Tool arguments
            session_id: Session ID (required for all tools)
            
        Returns:
            CallToolResult: MCP tool execution result containing content, structuredContent, and isError fields
            
        Raises:
            ValueError: If session ID is not provided
        """
        # All tools now require session ID for dependency injection
        if session_id is None:
            raise ValueError(
                f"Tool '{tool_name}' requires session ID for dependency injection. "
                f"All tools must be executed with session context."
            )
        
        mcp_client = self.get_mcp_client()
        async with mcp_client as mcp_async_client:
            # Session isolation is handled by FastMCP per request via _meta.client_id
            params = CallToolRequestParams(
                name=tool_name,
                arguments=tool_args,
                **{"_meta": {"client_id": session_id}},
            )
            call_req = ClientRequest(CallToolRequest(method="tools/call", params=params))
            return await mcp_async_client.session.send_request(call_req, CallToolResult)
    
    async def _cache_meta_tool_results(self, tool_result: Dict[str, Any], 
                                      session_id: str, debug: bool = False) -> None:
        """
        Cache meta tool search results.
        
        Args:
            tool_result: Extracted tool result dictionary from extract_tool_result_from_mcp
            session_id: Session ID
            debug: Whether to enable debug output
        """
        
        try:
            # tool_result is already processed by extract_tool_result_from_mcp
            # Extract and cache tool information directly
            extracted_tools = await self.extract_tools_from_meta_result(tool_result)
            self.cache_tools_for_session(session_id, extracted_tools)
            if debug:
                print(f"[DEBUG] Cached {len(extracted_tools)} tools for session {session_id}")
                    
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
        # For read_file tool: check data.processing_result.content_format
        data = tool_result.get("data")
        if data and isinstance(data, dict):
            processing_result = data.get("processing_result")
            if processing_result and isinstance(processing_result, dict):
                return processing_result.get("content_format") == "inline_data"
        
        return False
    
    def _extract_multimodal_content(self, tool_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract multimodal content inline_data.
        
        Precondition: _has_multimodal_content() has already confirmed presence of multimodal content.
        
        Args:
            tool_result: Complete ToolResult dictionary
            
        Returns:
            Dict: inline_data structure with mime_type and data
        """
        # Extract inline_data from data.processing_result.content
        return tool_result["data"]["processing_result"]["content"]["inline_data"]
    
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