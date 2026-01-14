"""
Anthropic Tool Manager - Tool manager for Anthropic API

Inherits from BaseToolManager and implements Anthropic-specific tool schema formatting.
Optimized for Anthropic Claude API requirements including input_schema formatting.
"""

from typing import Dict, Any, List

from backend.infrastructure.llm.base.tool_manager import BaseToolManager


class AnthropicToolManager(BaseToolManager):
    """
    Anthropic-specific tool manager

    Inherits common functionality from BaseToolManager and implements Anthropic-specific:
    - input_schema formatting
    - Anthropic tool object construction
    - Parameter description and validation
    """
    
    def _format_schema_for_anthropic(self, tool_schema: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format tool schema for Anthropic format

        Args:
            tool_schema: Original tool schema

        Returns:
            Dict: Tool schema in Anthropic format
        """
        input_schema = tool_schema.get("parameters", {"type": "object", "properties": {}})
        
        # Ensure schema completeness
        if "properties" in input_schema:
            # Ensure all parameters have descriptions
            for prop in input_schema["properties"].values():
                if "description" not in prop:
                    prop["description"] = "Parameter value"

            # Preserve original required field, don't auto-infer all fields as required
            # If schema has no required field, all fields are optional
            if "required" not in input_schema:
                input_schema["required"] = []  # Empty array means all fields are optional
        
        if "type" not in input_schema:
            input_schema["type"] = "object"
        if "additionalProperties" not in input_schema:
            input_schema["additionalProperties"] = False
        
        return {
            "name": tool_schema["name"],
            "description": tool_schema.get("description", tool_schema["name"]),
            "input_schema": input_schema
        }
    
    async def get_function_call_schemas(self, session_id: str, agent_profile: str = 'general') -> List[Dict[str, Any]]:
        """
        Get MCP tool schemas in Anthropic format with agent profile filtering

        Args:
            session_id: Session ID for tool caching (required)
            agent_profile: Agent profile name ("coding", "lifestyle", "general", "pfc", "disabled")

        Returns:
            List[Dict[str, Any]]: Tool schemas in Anthropic format
        """
        
        # Get standardized tools from base class
        tools_dict = await self.get_standardized_tools(session_id, agent_profile)

        if not tools_dict:
            return []

        # Convert ToolSchema objects to Anthropic format
        anthropic_tools = []
        for _, tool_schema in tools_dict.items():
            # Convert JSONSchema object to dictionary
            input_schema_dict = tool_schema.inputSchema.model_dump(exclude_none=True, by_alias=True)

            anthropic_tool = self._format_schema_for_anthropic({
                "name": tool_schema.name,
                "description": tool_schema.description,
                "parameters": input_schema_dict
            })
            anthropic_tools.append(anthropic_tool)
        from backend.config import get_llm_settings
        debug = get_llm_settings().debug
        if debug:
            print(f"[DEBUG] Final Anthropic tools count: {len(anthropic_tools)}")
        
        return anthropic_tools

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
        from backend.config import get_llm_settings
        debug = get_llm_settings().debug
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
                if debug:
                    print(f"[WARNING] Failed to convert tool {tool_name} for system prompt: {e}")
                continue
        
        if debug:
            print(f"[DEBUG] Anthropic system prompt schemas count: {len(prompt_schemas)}")
        
        return prompt_schemas