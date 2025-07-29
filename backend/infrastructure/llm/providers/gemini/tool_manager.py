"""
Gemini-specific tool manager using unified base.

Handles Gemini-specific tool schema formatting while leveraging shared tool management logic.
"""

from typing import List, Dict, Any, Optional
from google.genai import types
from backend.infrastructure.llm.base.tool_manager import BaseToolManager


class GeminiToolManager(BaseToolManager):
    """
    Gemini-specific tool manager.
    
    Inherits common tool management logic from BaseToolManager and implements
    Gemini-specific schema formatting and tool execution.
    """
    
    async def get_function_call_schemas(self, session_id: Optional[str] = None, debug: bool = False) -> List[types.Tool]:
        """
        Get all MCP tool schemas in Gemini format.
        Only return meta tools + cached tools, not all regular tools.
        
        Args:
            session_id: Optional session ID for tool caching
            debug: Whether to enable debug output
            
        Returns:
            List[types.Tool]: Tool schemas formatted for Gemini API
        """
        if not self.tools_enabled:
            return []
        
        tools = []
        
        # Get MCP client for this session
        mcp_client = self.get_mcp_client(session_id)
        
        try:
            async with mcp_client as mcp_async_client:
                # Get available tools from MCP server
                list_tools_result = await mcp_async_client.list_tools()
                
                # Add meta tools (always available)
                for tool in list_tools_result.tools:
                    if self.is_meta_tool(tool.name):
                        gemini_tool = self._convert_mcp_tool_to_gemini(tool)
                        if gemini_tool:
                            tools.append(gemini_tool)
                
                # Add cached tools for this session
                if session_id:
                    cached_tools = self.get_cached_tools_for_session(session_id)
                    for cached_tool in cached_tools:
                        gemini_tool = self._convert_cached_tool_to_gemini(cached_tool)
                        if gemini_tool:
                            tools.append(gemini_tool)
                
                if debug:
                    print(f"[DEBUG] Returning {len(tools)} tools for Gemini (session: {session_id})")
                    for tool in tools:
                        if hasattr(tool, 'function_declarations'):
                            for func_decl in tool.function_declarations:
                                print(f"[DEBUG]   - {func_decl.name}")
                
                return tools
                
        except Exception as e:
            if debug:
                print(f"[DEBUG] Error getting function call schemas: {e}")
            return []
    
    def _convert_mcp_tool_to_gemini(self, mcp_tool) -> Optional[types.Tool]:
        """
        Convert MCP tool to Gemini Tool format.
        
        Args:
            mcp_tool: MCP tool object
            
        Returns:
            types.Tool: Gemini tool format, or None if conversion failed
        """
        try:
            # Build function declaration
            func_decl = types.FunctionDeclaration(
                name=mcp_tool.name,
                description=mcp_tool.description or "No description available"
            )
            
            # Add parameters if available
            if hasattr(mcp_tool, 'inputSchema') and mcp_tool.inputSchema:
                func_decl.parameters = self._convert_json_schema_to_gemini(mcp_tool.inputSchema)
            
            return types.Tool(function_declarations=[func_decl])
            
        except Exception as e:
            print(f"[WARNING] Failed to convert MCP tool {mcp_tool.name} to Gemini format: {e}")
            return None
    
    def _convert_cached_tool_to_gemini(self, cached_tool: Dict[str, Any]) -> Optional[types.Tool]:
        """
        Convert cached tool info to Gemini Tool format.
        
        Args:
            cached_tool: Cached tool information dictionary
            
        Returns:
            types.Tool: Gemini tool format, or None if conversion failed
        """
        try:
            # Build function declaration
            func_decl = types.FunctionDeclaration(
                name=cached_tool["name"],
                description=cached_tool.get("description", "No description available")
            )
            
            # Add parameters if available
            if "inputSchema" in cached_tool and cached_tool["inputSchema"]:
                func_decl.parameters = self._convert_json_schema_to_gemini(cached_tool["inputSchema"])
            elif "parameters" in cached_tool and cached_tool["parameters"]:
                func_decl.parameters = self._convert_json_schema_to_gemini(cached_tool["parameters"])
            
            return types.Tool(function_declarations=[func_decl])
            
        except Exception as e:
            print(f"[WARNING] Failed to convert cached tool {cached_tool.get('name', 'unknown')} to Gemini format: {e}")
            return None
    
    def _convert_json_schema_to_gemini(self, json_schema: Dict[str, Any]) -> types.Schema:
        """
        Convert JSON schema to Gemini Schema format.
        
        Args:
            json_schema: JSON schema dictionary
            
        Returns:
            types.Schema: Gemini schema format
        """
        # Handle different schema formats
        if "type" not in json_schema and "properties" in json_schema:
            # Assume object type if properties exist but type is missing
            json_schema = {"type": "object", **json_schema}
        
        # Build Gemini schema
        schema_dict = {
            "type": json_schema.get("type", "object")
        }
        
        # Add properties if present
        if "properties" in json_schema:
            schema_dict["properties"] = {}
            for prop_name, prop_schema in json_schema["properties"].items():
                schema_dict["properties"][prop_name] = self._convert_property_schema(prop_schema)
        
        # Add required fields
        if "required" in json_schema:
            schema_dict["required"] = json_schema["required"]
        
        # Add description
        if "description" in json_schema:
            schema_dict["description"] = json_schema["description"]
        
        return types.Schema(**schema_dict)
    
    def _convert_property_schema(self, prop_schema: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert property schema to Gemini format.
        
        Args:
            prop_schema: Property schema dictionary
            
        Returns:
            Dict[str, Any]: Converted property schema
        """
        result = {
            "type": prop_schema.get("type", "string")
        }
        
        if "description" in prop_schema:
            result["description"] = prop_schema["description"]
        
        if "enum" in prop_schema:
            result["enum"] = prop_schema["enum"]
        
        if "items" in prop_schema:
            result["items"] = self._convert_property_schema(prop_schema["items"])
        
        if "properties" in prop_schema:
            result["properties"] = {}
            for nested_name, nested_schema in prop_schema["properties"].items():
                result["properties"][nested_name] = self._convert_property_schema(nested_schema)
        
        return result