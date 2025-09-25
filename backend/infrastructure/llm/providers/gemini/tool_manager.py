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
    
    async def get_function_call_schemas(self, session_id: str, agent_profile: Optional[str] = None) -> List[types.Tool]:
        """
        Get MCP tool schemas in Gemini format based on agent profile.
        Uses get_standardized_tools() from base class, then converts to Gemini format.

        Args:
            session_id: Session ID for tool caching (required)
            agent_profile: Agent profile name for tool filtering

        Returns:
            List[types.Tool]: Tool schemas formatted for Gemini API
        """
        # Get standardized tools from base class
        tools_dict = await self.get_standardized_tools(session_id, agent_profile)
        
        if not tools_dict:
            return []
        
        # Convert ToolSchema objects to Gemini FunctionDeclarations
        function_declarations = []
        for tool_name, tool_schema in tools_dict.items():
            func_decl = self._convert_tool_schema_to_gemini_declaration(tool_schema)
            if func_decl:
                function_declarations.append(func_decl)
        
        from backend.config.llm import get_llm_settings
        llm_settings = get_llm_settings()
        if llm_settings.debug:
            print(f"[DEBUG] Final Gemini tools count: {len(function_declarations)}")
        
        # Return as Tool objects
        if function_declarations:
            return [types.Tool(function_declarations=function_declarations)]
        else:
            return []

    async def get_schemas_for_system_prompt(self, session_id: str, agent_profile: Optional[str] = None) -> List[dict]:
        """
        Get tool schemas in standardized dictionary format for system prompt embedding.

        This method returns a clean dictionary format specifically designed for embedding
        tool schemas into system prompts, separate from the API-specific formats.

        Args:
            session_id: Session ID for tool caching (required)
            agent_profile: Agent profile name for tool filtering

        Returns:
            List[dict]: Tool schemas in standardized dictionary format for system prompt
        """
        # Get standardized tools from base class
        from backend.config.llm import get_llm_settings
        llm_settings = get_llm_settings()

        tools_dict = await self.get_standardized_tools(session_id, agent_profile)

        if not tools_dict:
            return []

        # Convert ToolSchema objects to clean dictionary format for system prompt
        prompt_schemas = []
        for tool_name, tool_schema in tools_dict.items():
            try:
                # Build clean schema dictionary
                schema_dict = {
                    "name": tool_schema.name,
                    "description": tool_schema.description,
                    "parameters": tool_schema.inputSchema.model_dump(exclude_none=True)
                }
                prompt_schemas.append(schema_dict)
            except Exception as e:
                if llm_settings.debug:
                    print(f"[WARNING] Failed to convert tool {tool_name} for system prompt: {e}")
                continue

        if llm_settings.debug:
            print(f"[DEBUG] Gemini system prompt schemas count: {len(prompt_schemas)}")
        
        return prompt_schemas
    
    def _convert_tool_schema_to_gemini_declaration(self, tool_schema: ToolSchema) -> Optional[types.FunctionDeclaration]:
        """
        Convert ToolSchema to Gemini FunctionDeclaration format.
        
        Args:
            tool_schema: ToolSchema object
            
        Returns:
            types.FunctionDeclaration: Gemini function declaration, or None if conversion failed
        """
        try:
            # Get the input schema and sanitize for Gemini
            input_schema_dict = tool_schema.inputSchema.model_dump(exclude_none=True)
            sanitized_schema = self._sanitize_jsonschema_for_gemini(input_schema_dict)

            # Create FunctionDeclaration with properly typed parameters
            return types.FunctionDeclaration(
                name=tool_schema.name,
                description=tool_schema.description,
                parameters=types.Schema(**sanitized_schema)
            )
            
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
        
        # Don't auto-infer required fields - respect what the schema provides
        # If "required" is not in the original schema, it means all fields are optional
        
        # Ensure type is set
        if "type" not in cleaned:
            cleaned["type"] = "object"
        
        return cleaned