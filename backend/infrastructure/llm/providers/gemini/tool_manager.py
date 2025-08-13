"""
Gemini-specific tool manager using unified base.

Handles Gemini-specific tool schema formatting while leveraging shared tool management logic.
"""

from typing import List, Optional
from google.genai import types
from backend.infrastructure.llm.base.tool_manager import BaseToolManager
from backend.infrastructure.llm.shared.utils.tool_schema import ToolSchema


class GeminiToolManager(BaseToolManager):
    """
    Gemini-specific tool manager.
    
    Inherits common tool management logic from BaseToolManager and implements
    Gemini-specific schema formatting and tool execution.
    """
    
    async def get_function_call_schemas(self, session_id: str, agent_profile: Optional[str] = None, debug: bool = False) -> List[types.Tool]:
        """
        Get MCP tool schemas in Gemini format based on agent profile.
        Uses get_standardized_tools() from base class, then converts to Gemini format.
        
        Args:
            session_id: Session ID for tool caching (required)
            agent_profile: Agent profile name for tool filtering
            debug: Whether to enable debug output
            
        Returns:
            List[types.Tool]: Tool schemas formatted for Gemini API
        """
        # Get standardized tools from base class
        tools_dict = await self.get_standardized_tools(session_id, agent_profile, debug)
        
        if not tools_dict:
            return []
        
        # Convert ToolSchema objects to Gemini FunctionDeclarations
        function_declarations = []
        for tool_name, tool_schema in tools_dict.items():
            func_decl = self._convert_tool_schema_to_gemini_declaration(tool_schema)
            if func_decl:
                function_declarations.append(func_decl)
        
        if debug:
            print(f"[DEBUG] Final Gemini tools count: {len(function_declarations)}")
        
        # Return as Tool objects
        if function_declarations:
            return [types.Tool(function_declarations=function_declarations)]
        else:
            return []
    
    def _convert_tool_schema_to_gemini_declaration(self, tool_schema: ToolSchema) -> Optional[types.FunctionDeclaration]:
        """
        Convert ToolSchema to Gemini FunctionDeclaration format.
        
        Args:
            tool_schema: ToolSchema object
            
        Returns:
            types.FunctionDeclaration: Gemini function declaration, or None if conversion failed
        """
        try:
            # Build function declaration
            func_decl_dict = {
                "name": tool_schema.name,
                "description": tool_schema.description
            }
            
            # Get the input schema and sanitize for Gemini
            input_schema_dict = tool_schema.inputSchema.model_dump(exclude_none=True)
            sanitized_schema = self._sanitize_jsonschema_for_gemini(input_schema_dict)
            func_decl_dict["parameters"] = sanitized_schema
            
            return types.FunctionDeclaration(**func_decl_dict)
            
        except Exception as e:
            print(f"[WARNING] Failed to convert tool {tool_schema.name} to Gemini format: {e}")
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