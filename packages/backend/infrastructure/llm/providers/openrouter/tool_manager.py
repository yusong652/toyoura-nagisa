"""
OpenRouter Tool Manager

Manages MCP tool integration for OpenRouter client including schema formatting,
tool execution, and result processing.

OpenRouter uses the same nested tool schema format as OpenAI Chat Completions API.
"""

from typing import List, Dict, Any
from backend.infrastructure.llm.base.tool_manager import BaseToolManager
from backend.infrastructure.llm.shared.utils.tool_schema import transform_schema_for_openai_compat


class OpenRouterToolManager(BaseToolManager):
    """
    OpenRouter-specific tool manager

    Formats MCP tools for OpenRouter function calling API with nested structure.
    Uses the same format as OpenAI Chat Completions API.

    Example OpenRouter format:
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get weather info",
            "parameters": {
                "type": "object",
                "properties": {...},
                "required": [...]
            }
        }
    }
    """

    def __init__(self):
        """Initialize OpenRouter tool manager"""
        super().__init__()

    async def get_function_call_schemas(self, session_id: str, agent_profile: str = 'general') -> List[Dict[str, Any]] | None:
        """
        Get MCP tools formatted for OpenRouter function calling with nested structure.

        Uses get_standardized_tools() from base class, then converts to OpenRouter's nested format.
        Supports agent profile filtering.

        Args:
            session_id: Session ID for tool caching (required)
            agent_profile: Agent profile name ("coding", "lifestyle", "general", "pfc", "disabled")

        Returns:
            List of OpenRouter-formatted tool schemas (nested) or None if tools disabled
        """

        # Get standardized tools from base class
        tools_dict = await self.get_standardized_tools(session_id, agent_profile)

        if not tools_dict:
            return None

        # Convert ToolSchema objects to OpenRouter nested format
        openrouter_tools = []
        for _, tool_schema in tools_dict.items():
            openrouter_tool = self._convert_tool_schema_to_openrouter_format(tool_schema)
            if openrouter_tool:
                openrouter_tools.append(openrouter_tool)

        from backend.config.llm import get_llm_settings
        llm_settings = get_llm_settings()
        if llm_settings.debug:
            print(f"[DEBUG] Final OpenRouter tools count: {len(openrouter_tools)}")

        return openrouter_tools if openrouter_tools else None

    def _convert_tool_schema_to_openrouter_format(self, tool_schema) -> Dict[str, Any] | None:
        """
        Convert ToolSchema to OpenRouter nested function format.

        OpenRouter requires a nested structure where function details are under a 'function' key,
        same as OpenAI Chat Completions API.

        Args:
            tool_schema: ToolSchema object

        Returns:
            Dict: OpenRouter-formatted tool schema (nested), or None if conversion failed
        """
        try:
            # Get the input schema and convert to dict
            input_schema_dict = tool_schema.inputSchema.model_dump(exclude_none=True, by_alias=True)

            # Transform schema for OpenAI compatibility:
            # - Dereference $ref (inline definitions)
            # - Convert anyOf with null to type array format
            input_schema_dict = transform_schema_for_openai_compat(input_schema_dict)

            # Handle required fields properly for OpenRouter function calling
            if "properties" in input_schema_dict:
                # Respect the original schema's required field if it exists
                if "required" not in input_schema_dict:
                    # If no required field specified, assume no parameters are required
                    input_schema_dict["required"] = []
            else:
                input_schema_dict["properties"] = {}
                input_schema_dict["required"] = []

            if "type" not in input_schema_dict:
                input_schema_dict["type"] = "object"

            # Create OpenRouter tool schema with NESTED structure
            # Function details are nested under 'function' key
            openrouter_tool = {
                "type": "function",
                "function": {
                    "name": tool_schema.name,
                    "description": tool_schema.description,
                    "parameters": input_schema_dict
                }
            }

            return openrouter_tool

        except Exception as e:
            print(f"[WARNING] Failed to convert tool {tool_schema.name} to OpenRouter format: {e}")
            print(f"[DEBUG] Tool schema content: {tool_schema}")
            return None

    async def get_schemas_for_system_prompt(self, session_id: str, agent_profile: str = 'general') -> List[Dict[str, Any]]:
        """
        Get tool schemas in standardized dictionary format for system prompt embedding.

        This method returns a clean dictionary format specifically designed for embedding
        tool schemas into system prompts, separate from the API-specific formats.

        Args:
            session_id: Session ID for tool caching (required)
            agent_profile: Agent profile name ("coding", "lifestyle", "general", "pfc", "disabled")

        Returns:
            List[Dict[str, Any]]: Tool schemas in standardized dictionary format for system prompt
        """

        # Get standardized tools from base class
        tools_dict = await self.get_standardized_tools(session_id, agent_profile)

        if not tools_dict:
            return []

        # Convert ToolSchema objects to clean dictionary format for system prompt
        prompt_schemas = []
        from backend.config.llm import get_llm_settings
        llm_settings = get_llm_settings()

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

        if llm_settings.debug:
            print(f"[DEBUG] OpenRouter system prompt schemas count: {len(prompt_schemas)}")

        return prompt_schemas


__all__ = ['OpenRouterToolManager']
