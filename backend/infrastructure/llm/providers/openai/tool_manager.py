"""
OpenAI Tool Manager

Manages MCP tool integration for OpenAI client including schema formatting,
tool execution, and result processing.
"""

from typing import List, Dict, Any, Optional
from backend.infrastructure.llm.base.tool_manager import BaseToolManager


class OpenAIToolManager(BaseToolManager):
    """
    OpenAI-specific tool manager
    
    Formats MCP tools for OpenAI function calling API and handles
    tool execution with proper result formatting.
    """
    
    def __init__(self, mcp_client_source=None, tools_enabled: bool = True):
        """Initialize OpenAI tool manager"""
        super().__init__(mcp_client_source, tools_enabled)
    
    async def get_function_call_schemas(self, session_id: Optional[str] = None, debug: bool = False) -> Optional[List[Dict[str, Any]]]:
        """
        Get MCP tools formatted for OpenAI function calling
        
        Returns only meta tools + cached tools in OpenAI tools format.
        
        Args:
            session_id: Optional session ID for tool caching
            debug: Enable debug output
            
        Returns:
            List of OpenAI-formatted tool schemas or None if tools disabled
        """
        if not self.tools_enabled:
            return None
        
        mcp_client = self.get_mcp_client()
        
        try:
            async with mcp_client as mcp_async_client:
                mcp_tools = await mcp_async_client.list_tools()
        except Exception as e:
            if debug:
                print(f"[DEBUG] Failed to list MCP tools: {e}")
            return None
        
        # Build tools map and separate meta tools
        tools_map: Dict[str, Dict[str, Any]] = {}
        meta_tools: List[Dict[str, Any]] = []
        
        for tool in mcp_tools:
            # Get input schema with defaults
            input_schema = getattr(tool, "inputSchema", {"type": "object", "properties": {}})
            
            # Ensure required fields are present
            if "properties" in input_schema:
                if "required" not in input_schema:
                    input_schema["required"] = list(input_schema["properties"].keys())
            else:
                input_schema = {"type": "object", "properties": {}, "required": []}
            
            if "additionalProperties" not in input_schema:
                input_schema["additionalProperties"] = False
            
            # Create OpenAI tool schema
            tool_schema = {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": getattr(tool, "description", ""),
                    "parameters": input_schema,
                    "strict": True  # Enable structured outputs
                }
            }
            
            tools_map[tool.name] = tool_schema
            
            # Add to meta tools if applicable
            if self.is_meta_tool(tool.name):
                meta_tools.append(tool_schema)
        
        # Start with meta tools
        final_tools: List[Dict[str, Any]] = meta_tools.copy()
        added_tool_names = {tool["function"]["name"] for tool in meta_tools}
        
        # Add cached tools for the session
        if session_id:
            cached_tools = self.get_cached_tools_for_session(session_id)
            for cached_tool in cached_tools:
                tool_name = cached_tool["name"]
                
                # Skip if already added
                if tool_name in added_tool_names:
                    continue
                
                # Use existing schema if available
                if tool_name in tools_map:
                    final_tools.append(tools_map[tool_name])
                    added_tool_names.add(tool_name)
                else:
                    # Create minimal schema from cached info
                    parameters = cached_tool.get("parameters", {})
                    if not isinstance(parameters, dict):
                        parameters = {}
                    
                    tool_schema = {
                        "type": "function",
                        "function": {
                            "name": tool_name,
                            "description": cached_tool.get("description", tool_name),
                            "parameters": {
                                "type": "object",
                                "properties": parameters,
                                "required": list(parameters.keys()),
                                "additionalProperties": False
                            },
                            "strict": True
                        }
                    }
                    
                    final_tools.append(tool_schema)
                    added_tool_names.add(tool_name)
        
        if debug:
            print(f"[DEBUG] OpenAI tools loaded: {len(final_tools)} total")
            print(f"[DEBUG] Meta tools: {len(meta_tools)}")
            if session_id:
                cached_count = len(self.get_cached_tools_for_session(session_id))
                print(f"[DEBUG] Cached tools for session {session_id}: {cached_count}")
        
        return final_tools if final_tools else None
    
    async def handle_function_call(self, function_call: Dict[str, Any], session_id: Optional[str] = None, debug: bool = False) -> Any:
        """
        Handle OpenAI function call request
        
        Args:
            function_call: OpenAI function call dict with name, arguments, id
            session_id: Optional session ID for context
            debug: Enable debug output
            
        Returns:
            Tool execution result formatted for OpenAI
        """
        tool_name = function_call["name"]
        tool_args = function_call.get("arguments", {})
        tool_id = function_call.get("id", "")
        
        if debug:
            print(f"[DEBUG] OpenAI handling function call: {tool_name}")
        
        # Route to appropriate handler
        if self.is_meta_tool(tool_name):
            result = await self._handle_meta_tool(tool_name, tool_args, tool_id, session_id, debug)
            
            # Cache meta tool results if it's a search tool
            if tool_name in ["search_tools_by_keywords", "search_tools"] and session_id:
                await self._process_meta_tool_caching(result, session_id, debug)
            
            return result
        else:
            return await self._handle_regular_tool(tool_name, tool_args, tool_id, session_id, debug)
    
    async def _process_meta_tool_caching(self, result: Any, session_id: str, debug: bool = False) -> None:
        """
        Process and cache results from meta tool search
        
        Args:
            result: Meta tool result
            session_id: Session ID for caching
            debug: Enable debug output
        """
        try:
            # Convert result to dict format expected by extract_tools_from_meta_result
            if isinstance(result, str):
                import json
                try:
                    meta_result = json.loads(result)
                except json.JSONDecodeError:
                    meta_result = {"data": {"tools": []}}
            elif isinstance(result, dict):
                meta_result = result
            else:
                meta_result = {"data": {"tools": []}}
            
            # Extract and cache tools
            extracted_tools = await self.extract_tools_from_meta_result(meta_result)
            if extracted_tools:
                self.cache_tools_for_session(session_id, extracted_tools)
                if debug:
                    print(f"[DEBUG] Cached {len(extracted_tools)} tools from meta search")
            
        except Exception as e:
            if debug:
                print(f"[DEBUG] Failed to process meta tool caching: {e}")
    
    def _create_error_response(self, tool_id: str, tool_name: str, error_message: str) -> Dict[str, Any]:
        """
        Create OpenAI-specific error response
        
        Args:
            tool_id: Tool call ID
            tool_name: Tool name
            error_message: Error message
            
        Returns:
            Formatted error response
        """
        return {
            "type": "tool_result",
            "tool_call_id": tool_id,
            "name": tool_name,
            "content": error_message,
            "is_error": True
        }