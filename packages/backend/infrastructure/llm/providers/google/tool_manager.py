"""
Gemini-specific tool manager using unified base.

Handles Gemini-specific tool schema formatting while leveraging shared tool management logic.
"""

from typing import List, Dict, Any
from google.genai import types
from backend.infrastructure.llm.base.tool_manager import BaseToolManager
from backend.infrastructure.llm.shared.utils.tool_schema import ToolSchema


class GoogleToolManager(BaseToolManager):
    """
    Gemini-specific tool manager.
    
    Inherits common tool management logic from BaseToolManager and implements
    Gemini-specific schema formatting and tool execution.
    """
    
    async def get_function_call_schemas(self, session_id: str, agent_profile: str = 'general') -> List[types.Tool]:
        """
        Get MCP tool schemas in Gemini format based on agent profile.
        Uses get_standardized_tools() from base class, then converts to Gemini format.

        Args:
            session_id: Session ID for tool caching (required)
            agent_profile: Agent profile name ("coding", "lifestyle", "general", "pfc", "disabled")

        Returns:
            List[types.Tool]: Tool schemas formatted for Gemini API
        """
        # Get standardized tools from base class
        tools_dict = await self.get_standardized_tools(session_id, agent_profile)
        
        if not tools_dict:
            return []
        
        # Convert ToolSchema objects to Gemini FunctionDeclarations
        function_declarations = []
        for _, tool_schema in tools_dict.items():
            func_decl = self._convert_tool_schema_to_gemini_declaration(tool_schema)
            if func_decl:
                function_declarations.append(func_decl)
        
        from backend.config.llm import get_llm_settings
        # Return as Tool objects
        if function_declarations:
            return [types.Tool(function_declarations=function_declarations)]
        else:
            return []

    async def get_schemas_for_system_prompt(self, session_id: str, agent_profile: str = 'general') -> List[dict]:
        """
        Get tool schemas in standardized dictionary format for system prompt embedding.

        This method returns a clean dictionary format specifically designed for embedding
        tool schemas into system prompts, separate from the API-specific formats.

        Args:
            session_id: Session ID for tool caching (required)
            agent_profile: Agent profile name ("coding", "lifestyle", "general", "pfc", "disabled")

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
                    "parameters": tool_schema.inputSchema.model_dump(exclude_none=True, by_alias=True)
                }
                prompt_schemas.append(schema_dict)
            except Exception as e:
                if llm_settings.debug:
                    print(f"[WARNING] Failed to convert tool {tool_name} for system prompt: {e}")
                continue
        
        return prompt_schemas
    
    def _convert_tool_schema_to_gemini_declaration(self, tool_schema: ToolSchema) -> types.FunctionDeclaration | None:
        """
        Convert ToolSchema to Gemini FunctionDeclaration format.

        Uses google-genai SDK's built-in Schema.from_json_schema() to convert
        JSON Schema to Gemini's native format. This automatically:
        - Dereferences $ref and inlines $defs definitions
        - Converts anyOf with null to nullable: true
        - Preserves enum, minimum/maximum, minItems/maxItems, etc.

        Note: SDK's from_json_schema() loses descriptions on anyOf fields,
        so we restore them manually after conversion.

        Args:
            tool_schema: ToolSchema object

        Returns:
            types.FunctionDeclaration: Gemini function declaration, or None if conversion failed
        """
        try:
            input_schema_dict = tool_schema.inputSchema.model_dump(exclude_none=True, by_alias=True)

            # Normalize schema: convert 'definitions' -> '$defs' (SDK doesn't auto-alias this)
            sdk_schema = self._normalize_schema_for_sdk(input_schema_dict)

            # Convert to Gemini Schema using SDK's built-in converter
            # This handles $ref dereferencing, anyOf->nullable conversion, etc.
            json_schema_obj = types.JSONSchema(**sdk_schema)
            gemini_schema = types.Schema.from_json_schema(json_schema=json_schema_obj)

            # Restore descriptions lost during anyOf conversion (SDK bug workaround)
            self._restore_descriptions(gemini_schema, sdk_schema)

            return types.FunctionDeclaration(
                name=tool_schema.name,
                description=tool_schema.description,
                parameters=gemini_schema
            )

        except Exception as e:
            print(f"[WARNING] Failed to convert tool {tool_schema.name} to Gemini format: {e}")
            return None

    def _restore_descriptions(self, gemini_schema: types.Schema, original_schema: Dict[str, Any]) -> None:
        """
        Restore descriptions lost during SDK's from_json_schema() conversion.

        The SDK's anyOf->nullable conversion drops the description field.
        This method walks through both schemas and restores missing descriptions.

        Args:
            gemini_schema: Converted Gemini Schema (modified in place)
            original_schema: Original JSON Schema dict with descriptions
        """
        if not gemini_schema.properties or not original_schema.get("properties"):
            return

        original_props = original_schema.get("properties", {})

        for prop_name, gemini_prop in gemini_schema.properties.items():
            if prop_name not in original_props:
                continue

            original_prop = original_props[prop_name]

            # Restore description if missing in Gemini schema but present in original
            if gemini_prop.description is None and isinstance(original_prop, dict):
                desc = original_prop.get("description")
                if desc:
                    gemini_prop.description = desc

            # Recursively handle nested object properties
            if gemini_prop.properties and isinstance(original_prop, dict):
                self._restore_descriptions(gemini_prop, original_prop)

    def _normalize_schema_for_sdk(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize JSON Schema for google-genai SDK compatibility.

        The SDK's types.JSONSchema natively supports standard JSON Schema field names
        (anyOf, $ref, $defs, minItems, etc.) via Pydantic aliases. The only exception
        is 'definitions' (a Pydantic alias for $defs) which the SDK doesn't recognize.

        This method recursively converts 'definitions' -> '$defs' throughout the schema.

        Args:
            schema: JSON Schema dict (may contain 'definitions' from local JSONSchema class)

        Returns:
            Dict with 'definitions' replaced by '$defs' for SDK compatibility
        """
        if not isinstance(schema, dict):
            return schema

        result = {}
        for key, value in schema.items():
            # Convert 'definitions' to '$defs' (the only field SDK doesn't auto-alias)
            out_key = "$defs" if key == "definitions" else key

            # Recursively process nested structures
            if isinstance(value, dict):
                result[out_key] = self._normalize_schema_for_sdk(value)
            elif isinstance(value, list):
                result[out_key] = [
                    self._normalize_schema_for_sdk(item) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                result[out_key] = value

        return result