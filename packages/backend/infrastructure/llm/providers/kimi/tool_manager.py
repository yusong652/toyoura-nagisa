"""
Kimi (Moonshot) Tool Manager

Manages MCP tool integration for Kimi client including schema formatting,
tool execution, and result processing.

Kimi uses a nested tool schema format that differs from OpenAI's flat format.
"""

from typing import List, Dict, Any
from backend.infrastructure.llm.base.tool_manager import BaseToolManager


class KimiToolManager(BaseToolManager):
    """
    Kimi-specific tool manager

    Formats MCP tools for Kimi/Moonshot function calling API with nested structure.
    Unlike OpenAI's flat format, Kimi requires function details nested under a 'function' key.

    Example Kimi format:
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
        """Initialize Kimi tool manager"""
        super().__init__()

    async def get_function_call_schemas(self, session_id: str, agent_profile: str = 'general') -> List[Dict[str, Any]] | None:
        """
        Get MCP tools formatted for Kimi function calling with nested structure.

        Uses get_standardized_tools() from base class, then converts to Kimi's nested format.
        Supports agent profile filtering.

        Args:
            session_id: Session ID for tool caching (required)
            agent_profile: Agent profile name ("coding", "lifestyle", "general", "pfc", "disabled")

        Returns:
            List of Kimi-formatted tool schemas (nested) or None if tools disabled
        """

        # Get standardized tools from base class
        tools_dict = await self.get_standardized_tools(session_id, agent_profile)

        if not tools_dict:
            return None

        # Convert ToolSchema objects to Kimi nested format
        kimi_tools = []
        for _, tool_schema in tools_dict.items():
            kimi_tool = self._convert_tool_schema_to_kimi_format(tool_schema)
            if kimi_tool:
                kimi_tools.append(kimi_tool)

        return kimi_tools if kimi_tools else None

    def _convert_tool_schema_to_kimi_format(self, tool_schema) -> Dict[str, Any] | None:
        """
        Convert ToolSchema to Kimi nested function format.

        Kimi requires a nested structure where function details are under a 'function' key,
        unlike OpenAI's flat format.

        Args:
            tool_schema: ToolSchema object

        Returns:
            Dict: Kimi-formatted tool schema (nested), or None if conversion failed
        """
        try:
            # Get the input schema and convert to dict
            input_schema_dict = tool_schema.inputSchema.model_dump(exclude_none=True)

            # Handle required fields properly for Kimi function calling
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

            # Create Kimi tool schema with NESTED structure
            # Key difference: function details are nested under 'function' key
            kimi_tool = {
                "type": "function",
                "function": {
                    "name": tool_schema.name,
                    "description": tool_schema.description,
                    "parameters": input_schema_dict
                }
            }

            return kimi_tool

        except Exception as e:
            print(f"[WARNING] Failed to convert tool {tool_schema.name} to Kimi format: {e}")
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
                    "parameters": tool_schema.inputSchema.model_dump(exclude_none=True)
                }
                prompt_schemas.append(schema_dict)
            except Exception as e:
                if llm_settings.debug:
                    print(f"[WARNING] Failed to convert tool {tool_name} for system prompt: {e}")
                continue

        return prompt_schemas


__all__ = ['KimiToolManager']
