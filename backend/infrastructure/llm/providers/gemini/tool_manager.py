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
        
        # Get cached tools for session
        cached_tools = []
        if session_id:
            cached_tools = self.get_cached_tools_for_session(session_id)
            if debug:
                print(f"[DEBUG] Found {len(cached_tools)} cached tools for session {session_id}")
        
        # Get all MCP tools
        mcp_client = self.get_mcp_client(session_id)
        
        try:
            async with mcp_client as mcp_async_client:
                mcp_tools_result = await mcp_async_client.list_tools()
                
                # Build tools map and collect meta tools
                function_declarations = []
                added_tool_names = set()
                
                # Handle different return formats from MCP client
                if hasattr(mcp_tools_result, 'tools'):
                    mcp_tools = mcp_tools_result.tools
                elif isinstance(mcp_tools_result, list):
                    mcp_tools = mcp_tools_result
                else:
                    if debug:
                        print(f"[DEBUG] Unexpected MCP tools format: {type(mcp_tools_result)}")
                    mcp_tools = []
                
                # Add meta tools first
                for tool in mcp_tools:
                    if self.is_meta_tool(tool.name):
                        func_decl = self._convert_mcp_tool_to_gemini_declaration(tool)
                        if func_decl:
                            function_declarations.append(func_decl)
                            added_tool_names.add(tool.name)
                
                # Add cached tools (avoid duplicates)
                for cached_tool in cached_tools:
                    tool_name = cached_tool["name"]
                    if tool_name in added_tool_names:
                        if debug:
                            print(f"[DEBUG] Skipped duplicate cached tool: {tool_name}")
                        continue
                    
                    func_decl = self._convert_cached_tool_to_gemini_declaration(cached_tool)
                    if func_decl:
                        function_declarations.append(func_decl)
                        added_tool_names.add(tool_name)
                
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
    
    def _convert_mcp_tool_to_gemini_declaration(self, mcp_tool) -> Optional[types.FunctionDeclaration]:
        """
        Convert MCP tool to Gemini FunctionDeclaration format.
        
        Args:
            mcp_tool: MCP tool object
            
        Returns:
            types.FunctionDeclaration: Gemini function declaration, or None if conversion failed
        """
        try:
            # Build function declaration
            func_decl_dict = {
                "name": mcp_tool.name,
                "description": mcp_tool.description or "No description available"
            }
            
            # Add parameters if available
            if hasattr(mcp_tool, 'inputSchema') and mcp_tool.inputSchema:
                input_schema = self._sanitize_jsonschema_for_gemini(mcp_tool.inputSchema)
                func_decl_dict["parameters"] = input_schema
            
            return types.FunctionDeclaration(**func_decl_dict)
            
        except Exception as e:
            print(f"[WARNING] Failed to convert MCP tool {mcp_tool.name} to Gemini format: {e}")
            return None
    
    def _convert_cached_tool_to_gemini_declaration(self, cached_tool: Dict[str, Any]) -> Optional[types.FunctionDeclaration]:
        """
        Convert cached tool info to Gemini FunctionDeclaration format.
        
        Args:
            cached_tool: Cached tool information dictionary
            
        Returns:
            types.FunctionDeclaration: Gemini function declaration, or None if conversion failed
        """
        try:
            # Build function declaration
            func_decl_dict = {
                "name": cached_tool["name"],
                "description": cached_tool.get("description", "No description available")
            }
            
            # Add parameters if available
            if "inputSchema" in cached_tool and cached_tool["inputSchema"]:
                input_schema = self._sanitize_jsonschema_for_gemini(cached_tool["inputSchema"])
                func_decl_dict["parameters"] = input_schema
            elif "parameters" in cached_tool and cached_tool["parameters"]:
                # Handle different parameter formats
                parameters = cached_tool["parameters"]
                if isinstance(parameters, dict):
                    if "type" in parameters and "properties" in parameters:
                        # Already a complete schema
                        input_schema = self._sanitize_jsonschema_for_gemini(parameters)
                    else:
                        # Just properties, wrap it
                        input_schema = {
                            "type": "object",
                            "properties": parameters,
                            "required": list(parameters.keys()) if parameters else []
                        }
                        input_schema = self._sanitize_jsonschema_for_gemini(input_schema)
                    func_decl_dict["parameters"] = input_schema
            
            return types.FunctionDeclaration(**func_decl_dict)
            
        except Exception as e:
            print(f"[WARNING] Failed to convert cached tool {cached_tool.get('name', 'unknown')} to Gemini format: {e}")
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