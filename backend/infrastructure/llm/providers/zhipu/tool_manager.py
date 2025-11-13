"""
Zhipu (智谱) Tool Manager

Manages MCP tool integration for Zhipu client including schema formatting,
tool execution, and result processing.

Zhipu uses OpenAI-compatible nested tool schema format.
"""

from typing import List, Dict, Any
from backend.infrastructure.llm.base.tool_manager import BaseToolManager


class ZhipuToolManager(BaseToolManager):
    """
    Zhipu-specific tool manager

    Formats MCP tools for Zhipu function calling API with nested structure.
    Uses OpenAI-compatible format where function details are nested under a 'function' key.

    Example Zhipu format (from official docs):
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "获取指定地点的天气信息",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "地点名称"
                    }
                },
                "required": ["location"]
            }
        }
    }
    """

    def __init__(self):
        """Initialize Zhipu tool manager"""
        super().__init__()

    async def get_function_call_schemas(self, session_id: str, agent_profile: str = 'general') -> List[Dict[str, Any]] | None:
        """
        Get MCP tools formatted for Zhipu function calling with nested structure.

        Uses get_standardized_tools() from base class, then converts to Zhipu's nested format.
        Supports agent profile filtering.

        Args:
            session_id: Session ID for tool caching (required)
            agent_profile: Agent profile name ("coding", "lifestyle", "general", "pfc", "disabled")

        Returns:
            List of Zhipu-formatted tool schemas (nested) or None if tools disabled
        """

        # Get standardized tools from base class
        tools_dict = await self.get_standardized_tools(session_id, agent_profile)

        if not tools_dict:
            return None

        # Convert ToolSchema objects to Zhipu nested format
        zhipu_tools = []
        for _, tool_schema in tools_dict.items():
            zhipu_tool = self._convert_tool_schema_to_zhipu_format(tool_schema)
            if zhipu_tool:
                zhipu_tools.append(zhipu_tool)

        from backend.config.llm import get_llm_settings
        llm_settings = get_llm_settings()
        if llm_settings.debug:
            print(f"[DEBUG] Final Zhipu tools count: {len(zhipu_tools)}")

        return zhipu_tools if zhipu_tools else None

    def _convert_tool_schema_to_zhipu_format(self, tool_schema) -> Dict[str, Any] | None:
        """
        Convert ToolSchema to Zhipu nested function format (OpenAI-compatible).

        Args:
            tool_schema: ToolSchema object

        Returns:
            Dict: Zhipu-formatted tool schema (nested), or None if conversion failed
        """
        try:
            # Get the input schema and convert to dict
            input_schema_dict = tool_schema.inputSchema.model_dump(exclude_none=True)

            # Handle required fields properly for Zhipu function calling
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

            # Create Zhipu tool schema with NESTED structure (OpenAI-compatible)
            zhipu_tool = {
                "type": "function",
                "function": {
                    "name": tool_schema.name,
                    "description": tool_schema.description,
                    "parameters": input_schema_dict
                }
            }

            return zhipu_tool

        except Exception as e:
            print(f"[WARNING] Failed to convert tool {tool_schema.name} to Zhipu format: {e}")
            print(f"[DEBUG] Tool schema content: {tool_schema}")
            return None

    async def get_schemas_for_system_prompt(self, session_id: str, agent_profile: str = 'general') -> List[Dict[str, Any]]:
        """
        Get tool schemas in standardized dictionary format for system prompt embedding.

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

        if llm_settings.debug:
            print(f"[DEBUG] Zhipu system prompt schemas count: {len(prompt_schemas)}")

        return prompt_schemas


__all__ = ['ZhipuToolManager']
