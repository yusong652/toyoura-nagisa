"""
Moonshot (Moonshot) Tool Manager

Manages MCP tool integration for Moonshot client including schema formatting,
tool execution, and result processing.

Moonshot uses a nested tool schema format that differs from OpenAI's flat format.
"""

from typing import List, Dict, Any
from backend.infrastructure.llm.base.tool_manager import BaseToolManager
from backend.infrastructure.llm.shared.utils.tool_schema import transform_schema_for_openai_compat
from backend.config.dev import get_dev_config


class MoonshotToolManager(BaseToolManager):
    """
    Moonshot-specific tool manager

    Formats MCP tools for Moonshot/Moonshot function calling API with nested structure.
    Unlike OpenAI's flat format, Moonshot requires function details nested under a 'function' key.

    Example Moonshot format:
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
        """Initialize Moonshot tool manager"""
        super().__init__()

    async def get_function_call_schemas(self, session_id: str, agent_profile = 'pfc_expert') -> List[Dict[str, Any]] | None:
        """
        Get MCP tools formatted for Moonshot function calling with nested structure.

        Uses get_standardized_tools() from base class, then converts to Moonshot's nested format.
        Supports agent profile filtering.

        Args:
            session_id: Session ID for tool caching (required)
            agent_profile: Agent profile name ("pfc_expert", "disabled")

        Returns:
            List of Moonshot-formatted tool schemas (nested) or None if tools disabled
        """

        # Get standardized tools from base class
        tools_dict = await self.get_standardized_tools(session_id, agent_profile)

        if not tools_dict:
            return None

        # Convert ToolSchema objects to Moonshot nested format
        moonshot_tools = []
        for _, tool_schema in tools_dict.items():
            moonshot_tool = self._convert_tool_schema_to_moonshot_format(tool_schema)
            if moonshot_tool:
                moonshot_tools.append(moonshot_tool)

        return moonshot_tools if moonshot_tools else None

    def _convert_tool_schema_to_moonshot_format(self, tool_schema) -> Dict[str, Any] | None:
        """
        Convert ToolSchema to Moonshot nested function format.

        Moonshot requires a nested structure where function details are under a 'function' key,
        unlike OpenAI's flat format.

        Args:
            tool_schema: ToolSchema object

        Returns:
            Dict: Moonshot-formatted tool schema (nested), or None if conversion failed
        """
        try:
            # Get the input schema and convert to dict
            input_schema_dict = tool_schema.inputSchema.model_dump(exclude_none=True, by_alias=True)

            # Transform schema for OpenAI compatibility:
            # - Dereference $ref (inline definitions)
            # - Convert anyOf with null to type array format
            input_schema_dict = transform_schema_for_openai_compat(input_schema_dict)

            # Handle required fields properly for Moonshot function calling
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

            # Create Moonshot tool schema with NESTED structure
            # Key difference: function details are nested under 'function' key
            moonshot_tool = {
                "type": "function",
                "function": {
                    "name": tool_schema.name,
                    "description": tool_schema.description,
                    "parameters": input_schema_dict
                }
            }

            return moonshot_tool

        except Exception as e:
            print(f"[WARNING] Failed to convert tool {tool_schema.name} to Moonshot format: {e}")
            print(f"[DEBUG] Tool schema content: {tool_schema}")
            return None

    async def get_schemas_for_system_prompt(self, session_id: str, agent_profile = 'pfc_expert') -> List[Dict[str, Any]]:
        """
        Get tool schemas in standardized dictionary format for system prompt embedding.

        This method returns a clean dictionary format specifically designed for embedding
        tool schemas into system prompts, separate from the API-specific formats.

        Args:
            session_id: Session ID for tool caching (required)
            agent_profile: Agent profile name ("pfc_expert", "disabled")

        Returns:
            List[Dict[str, Any]]: Tool schemas in standardized dictionary format for system prompt
        """

        # Get standardized tools from base class
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
                if get_dev_config().debug_mode:
                    print(f"[WARNING] Failed to convert tool {tool_name} for system prompt: {e}")
                continue

        return prompt_schemas


__all__ = ['MoonshotToolManager']
