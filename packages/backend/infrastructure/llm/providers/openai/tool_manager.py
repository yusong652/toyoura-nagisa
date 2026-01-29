"""
OpenAI Tool Manager

Manages MCP tool integration for OpenAI client including schema formatting,
tool execution, and result processing.
"""

from typing import List, Dict, Any
from backend.infrastructure.llm.base.tool_manager import BaseToolManager
from backend.config.dev import get_dev_config


class OpenAIToolManager(BaseToolManager):
    """
    OpenAI-specific tool manager
    
    Formats MCP tools for OpenAI function calling API and handles
    tool execution with proper result formatting.
    """
    
    def __init__(self):
        """Initialize OpenAI tool manager"""
        super().__init__()
    
    async def get_function_call_schemas(self, session_id: str, agent_profile = 'pfc_expert') -> List[Dict[str, Any]] | None:
        """
        Get MCP tools formatted for OpenAI function calling

        Uses get_standardized_tools() from base class, then converts to OpenAI format.
        Supports agent profile filtering.

        Args:
            session_id: Session ID for tool caching (required)
            agent_profile: Agent profile name ("pfc_expert", "disabled")

        Returns:
            List of OpenAI-formatted tool schemas or None if tools disabled
        """
        
        # Get standardized tools from base class
        tools_dict = await self.get_standardized_tools(session_id, agent_profile)

        if not tools_dict:
            return None

        # Convert ToolSchema objects to OpenAI format
        openai_tools = []
        for _, tool_schema in tools_dict.items():
            openai_tool = self._convert_tool_schema_to_openai_format(tool_schema)
            if openai_tool:
                openai_tools.append(openai_tool)

        return openai_tools if openai_tools else None
    
    def _convert_tool_schema_to_openai_format(self, tool_schema) -> Dict[str, Any] | None:
        """
        Convert ToolSchema to OpenAI function format.
        
        Args:
            tool_schema: ToolSchema object
            
        Returns:
            Dict: OpenAI-formatted tool schema, or None if conversion failed
        """
        try:
            # Get the input schema and convert to dict
            input_schema_dict = tool_schema.inputSchema.model_dump(exclude_none=True, by_alias=True)
            
            # Handle required fields properly for OpenAI function calling
            if "properties" in input_schema_dict:
                # Respect the original schema's required field if it exists
                if "required" not in input_schema_dict:
                    # If no required field specified, assume no parameters are required
                    # This is more lenient and works better with optional parameters
                    input_schema_dict["required"] = []
                # else: keep the existing required field as-is
            else:
                input_schema_dict["properties"] = {}
                input_schema_dict["required"] = []
            
            # Ensure all required fields for OpenAI structured outputs
            if "additionalProperties" not in input_schema_dict:
                input_schema_dict["additionalProperties"] = False
            
            if "type" not in input_schema_dict:
                input_schema_dict["type"] = "object"
            
            # Create OpenAI tool schema
            # Note: Temporarily disable strict mode to avoid schema validation issues
            # OpenAI's strict mode requires ALL properties to be in required array
            # which may not work well with optional parameters in MCP tools
            openai_tool = {
                "type": "function",
                "name": tool_schema.name,
                "description": tool_schema.description,
                "parameters": input_schema_dict,
                "strict": False
            }
                   
            return openai_tool

        except Exception as e:
            print(f"[WARNING] Failed to convert tool {tool_schema.name} to OpenAI format: {e}")
            return None


