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
        
        # Collect all available tools
        all_tools = []
        added_tool_names = set()
        
        # Get all MCP tools and add meta tools to the list
        mcp_client = self.get_mcp_client(session_id)
        
        try:
            async with mcp_client as mcp_async_client:
                mcp_tools_result = await mcp_async_client.list_tools()
                
                # Handle different return formats from MCP client
                if hasattr(mcp_tools_result, 'tools'):
                    mcp_tools = mcp_tools_result.tools
                elif isinstance(mcp_tools_result, list):
                    mcp_tools = mcp_tools_result
                else:
                    if debug:
                        print(f"[DEBUG] Unexpected MCP tools format: {type(mcp_tools_result)}")
                    mcp_tools = []
                
                # Convert meta tools from MCP format to cached format and add them
                for tool in mcp_tools:
                    if self.is_meta_tool(tool.name):
                        tool_dict = self._convert_mcp_tool_to_dict(tool)
                        if tool_dict:
                            all_tools.append(tool_dict)
                            added_tool_names.add(tool.name)
                
                # Add cached tools (avoid duplicates)
                if session_id:
                    cached_tools = self.get_cached_tools_for_session(session_id)
                    if debug:
                        print(f"[DEBUG] Found {len(cached_tools)} cached tools for session {session_id}")
                    
                    for cached_tool in cached_tools:
                        tool_name = cached_tool["name"]
                        if tool_name not in added_tool_names:
                            all_tools.append(cached_tool)
                            added_tool_names.add(tool_name)
                        elif debug:
                            print(f"[DEBUG] Skipped duplicate cached tool: {tool_name}")
                
                # Convert all tools using unified method
                function_declarations = []
                for tool_dict in all_tools:
                    func_decl = self._convert_tool_dict_to_gemini_declaration(tool_dict)
                    if func_decl:
                        function_declarations.append(func_decl)
                
                if debug:
                    print(f"[DEBUG] Final tools count: {len(function_declarations)}")
                    for func_decl in function_declarations:
                        print(f"[DEBUG]   - {func_decl.name}")
                
                # Return as Tool objects
                if function_declarations:
                    return [types.Tool(function_declarations=function_declarations)]
                else:
                    return []
                
        except Exception as e:
            if debug:
                print(f"[DEBUG] Error getting function call schemas: {e}")
            return []
    
    def _convert_mcp_tool_to_dict(self, mcp_tool) -> Optional[Dict[str, Any]]:
        """
        Convert MCP tool to dictionary format (same as cached tools).
        
        Args:
            mcp_tool: MCP tool object
            
        Returns:
            Dict[str, Any]: Tool dictionary, or None if conversion failed
        """
        try:
            tool_dict = {
                "name": mcp_tool.name,
                "description": mcp_tool.description or "No description available"
            }
            
            # Get inputSchema and ensure proper format like old version
            input_schema = getattr(mcp_tool, "inputSchema", {"type": "object", "properties": {}})
            
            # Apply same preprocessing as old version
            if "properties" in input_schema:
                for prop in input_schema["properties"].values():
                    if "description" not in prop:
                        prop["description"] = "Parameter value"
                input_schema["required"] = list(input_schema["properties"].keys())
            if "type" not in input_schema:
                input_schema["type"] = "object"
            # Remove Gemini unsupported fields
            input_schema.pop("additionalProperties", None)
            
            tool_dict["inputSchema"] = input_schema
            
            return tool_dict
            
        except Exception as e:
            print(f"[WARNING] Failed to convert MCP tool {mcp_tool.name} to dict format: {e}")
            return None
    
    def _convert_tool_dict_to_gemini_declaration(self, tool_dict: Dict[str, Any]) -> Optional[types.FunctionDeclaration]:
        """
        Convert tool dictionary to Gemini FunctionDeclaration format.
        Unified method for both MCP tools and cached tools.
        
        Args:
            tool_dict: Tool information dictionary
            
        Returns:
            types.FunctionDeclaration: Gemini function declaration, or None if conversion failed
        """
        try:
            # Build function declaration
            func_decl_dict = {
                "name": tool_dict["name"],
                "description": tool_dict.get("description", "No description available")
            }
            
            # Add parameters - handle both inputSchema and parameters fields
            input_schema = None
            
            # First try inputSchema (preferred)
            if "inputSchema" in tool_dict and tool_dict["inputSchema"] is not None:
                input_schema = tool_dict["inputSchema"]
            # Fallback to parameters field for backward compatibility
            elif "parameters" in tool_dict and tool_dict["parameters"] is not None:
                parameters = tool_dict["parameters"]
                if isinstance(parameters, dict):
                    if "type" in parameters and "properties" in parameters:
                        # Already a complete schema
                        input_schema = parameters
                    else:
                        # Just properties, wrap it
                        input_schema = {
                            "type": "object",
                            "properties": parameters,
                            "required": list(parameters.keys()) if parameters else []
                        }
            else:
                # Default empty schema for tools without parameters
                input_schema = {"type": "object", "properties": {}}
            
            # Ensure proper schema structure like old version
            if isinstance(input_schema, dict):
                # Apply same preprocessing as old version for cached tools
                if "properties" in input_schema:
                    for prop in input_schema["properties"].values():
                        if isinstance(prop, dict) and "description" not in prop:
                            prop["description"] = "Parameter value"
                    if "required" not in input_schema:
                        input_schema["required"] = list(input_schema["properties"].keys())
                if "type" not in input_schema:
                    input_schema["type"] = "object"
                # Remove Gemini unsupported fields
                input_schema.pop("additionalProperties", None)
                
                # Sanitize for Gemini
                input_schema = self._sanitize_jsonschema_for_gemini(input_schema)
                func_decl_dict["parameters"] = input_schema
            
            return types.FunctionDeclaration(**func_decl_dict)
            
        except Exception as e:
            print(f"[WARNING] Failed to convert tool {tool_dict.get('name', 'unknown')} to Gemini format: {e}")
            return None
    
    def _sanitize_jsonschema_for_gemini(self, schema: dict) -> dict:
        """
        Sanitize JSON schema for Gemini API compatibility.
        
        Gemini function-call schema only supports a subset of JSON Schema draft-7
        (type/properties/required/description/enum/items/default/title)
        Other keywords like exclusiveMinimum will cause validation errors.
        
        Args:
            schema: Schema to sanitize
            
        Returns:
            dict: Sanitized schema
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
        
        # Auto-infer required fields for object type
        if cleaned.get("type") == "object" and "required" not in cleaned and "properties" in cleaned:
            cleaned["required"] = list(cleaned["properties"].keys())
        
        # Ensure type is set
        if "type" not in cleaned:
            cleaned["type"] = "object"
        
        return cleaned