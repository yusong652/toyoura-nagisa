"""
BaseToolManager - Abstract base class for all LLM client Tool Managers.

Designed for aiNagisa's multi-LLM architecture as a unified tool management interface.
Defines core methods that all Tool Managers must implement to ensure consistency and extensibility.
"""

import json
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from fastmcp import Client as MCPClient
from mcp.types import CallToolRequestParams, CallToolRequest, ClientRequest, CallToolResult

from backend.infrastructure.mcp.utils import extract_tool_result_from_mcp
from backend.infrastructure.llm.shared.utils.tool_schema import ToolSchema
from backend.infrastructure.mcp.tool_profile_manager import ToolProfileManager
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
    
    def __init__(self):
        """Initialize base state."""

        # MCP client will be retrieved from app state when needed
        self._mcp_client = None
    
    def get_mcp_client(self) -> MCPClient:
        """
        Return the shared MCP client from app state. FastMCP handles session isolation per request
        through the _meta.client_id parameter in tool calls.

        Returns:
            MCPClient: Shared client instance from app state
        """
        if self._mcp_client is None:
            from backend.shared.utils.app_context import get_mcp_client
            self._mcp_client = get_mcp_client()
        return self._mcp_client
    

    async def get_standardized_tools(self, session_id: str, agent_profile: Optional[str] = None, debug: bool = False) -> Dict[str, ToolSchema]:
        """
        Get standardized ToolSchema objects based on agent profile.

        Args:
            session_id: Session ID (required)
            agent_profile: Agent profile name ("coding", "lifestyle", "general", or None for all tools)
            debug: Whether to enable debug output
            
        Returns:
            Dict[str, ToolSchema]: Tool name -> ToolSchema mapping
        """
        
        tools_dict: Dict[str, ToolSchema] = {}
        
        try:
            mcp_client = self.get_mcp_client()
            async with mcp_client as mcp_async_client:
                # Get all MCP tools - list_tools() always returns a list
                mcp_tools = await mcp_async_client.list_tools()
                
                # 确定要加载的工具集合
                if agent_profile:
                    profile_enum = ToolProfileManager.validate_profile(agent_profile)
                    if profile_enum and ToolProfileManager.should_disable_all_tools(profile_enum):
                        # DISABLED 状态：不加载任何工具
                        if debug:
                            print(f"[DEBUG] Disabling all tools (profile: {agent_profile})")
                        return {}
                    elif profile_enum and not ToolProfileManager.should_load_all_tools(profile_enum):
                        # 使用指定profile的工具集合
                        allowed_tools = set(ToolProfileManager.get_tools_for_profile(profile_enum))
                        if debug:
                            print(f"[DEBUG] Loading tools for profile '{agent_profile}': {len(allowed_tools)} tools")
                    else:
                        # Profile无效或为general，加载所有工具
                        allowed_tools = None
                        if debug:
                            print(f"[DEBUG] Loading all tools (profile: {agent_profile})")
                else:
                    # 未指定profile，加载所有工具
                    allowed_tools = None
                    if debug:
                        print("[DEBUG] Loading all tools (no profile specified)")
                
                # 添加工具到字典
                for mcp_tool in mcp_tools:
                    # 如果设置了allowed_tools，只加载允许的工具
                    if allowed_tools is not None and mcp_tool.name not in allowed_tools:
                        continue
                        
                    tool_schema = ToolSchema.from_mcp_tool(mcp_tool)
                    tools_dict[tool_schema.name] = tool_schema

                if debug:
                    print(f"[DEBUG] Loaded {len(tools_dict)} tools for session {session_id}")
                
                return tools_dict
                
        except Exception as e:
            if debug:
                print(f"[DEBUG] Error getting standardized tools: {e}")
            return {}

    @abstractmethod
    async def get_function_call_schemas(self, session_id: str, agent_profile: Optional[str] = None, debug: bool = False) -> Any:
        """
        Get tool schemas formatted for the specific LLM provider.
        Uses get_standardized_tools() internally, then converts to provider format.
        
        Args:
            session_id: Session ID (required)
            agent_profile: Agent profile name for tool filtering
            debug: Whether to enable debug output
            
        Returns:
            Tool schema list adapted for target LLM format (format varies by client)
        """
        pass

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
            # Create params with _meta as dict (FastMCP will handle conversion)
            params = CallToolRequestParams(
                name=tool_name,
                arguments=tool_args,
                _meta={"client_id": session_id}  # type: ignore
            )
            call_req = ClientRequest(CallToolRequest(method="tools/call", params=params))
            return await mcp_async_client.session.send_request(call_req, CallToolResult)
    
    
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
    
    async def handle_function_call(self, function_call: dict, session_id: Optional[str] = None, debug: bool = False) -> Dict[str, Any]:
        """
        Handle LLM-generated function_call requests.

        Args:
            function_call: Function call dictionary containing:
                - name: str - Tool name to execute
                - arguments: Dict[str, Any] - Tool arguments (optional, defaults to {})
                - id: str - Tool call ID for tracking (optional, defaults to "")
            session_id: Optional session ID for context-aware tools (required for execution)
            debug: Whether to enable debug output

        Returns:
            Dict[str, Any]: Unified tool result structure:
                - inline_data: Dict with multimodal content or empty {}
                - llm_content: Tool's response

        Raises:
            RuntimeError: When tool execution fails due to infrastructure errors
            ValueError: When required session_id is not provided
        """
        tool_name = function_call["name"]
        tool_args = function_call.get("arguments", {})
        tool_id = function_call.get("id", "")

        # tool_id is not used by MCP but preserved for LLM context managers
        # which need it to properly format tool results in conversation history
        _ = tool_id

        try:
            # Execute tool
            call_tool_result = await self._execute_mcp_tool(tool_name, tool_args, session_id)
            tool_result = extract_tool_result_from_mcp(call_tool_result)

            # Check MCP-level errors (is_error field) - return unified format with error info
            if tool_result.get("is_error"):
                return {
                    "inline_data": {},
                    "llm_content": f"<error>{tool_result.get('message', 'Unknown MCP error')}</error>"
                }

            # Check tool-level errors (status="error") - return unified format with error info
            if tool_result.get("status") == "error":
                error_message = tool_result.get("message", tool_result.get("error", "Unknown error"))
                return {
                    "inline_data": {},
                    "llm_content": f"<error>{error_message}</error>"
                }

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