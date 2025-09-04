"""
OpenAI Tool Manager

Manages MCP tool integration for OpenAI client including schema formatting,
tool execution, and result processing.
"""

from typing import List, Dict, Any, Optional
from backend.infrastructure.llm.base.tool_manager import BaseToolManager


class OpenAIToolManager(BaseToolManager):
    """
    OpenAI-specific tool manager
    
    Formats MCP tools for OpenAI function calling API and handles
    tool execution with proper result formatting.
    """
    
    def __init__(self):
        """Initialize OpenAI tool manager"""
        super().__init__()
    
    async def get_function_call_schemas(self, session_id: str, agent_profile: Optional[str] = None, debug: bool = False) -> Optional[List[Dict[str, Any]]]:
        """
        Get MCP tools formatted for OpenAI function calling
        
        Uses get_standardized_tools() from base class, then converts to OpenAI format.
        Supports agent profile filtering.
        
        Args:
            session_id: Session ID for tool caching (required)
            agent_profile: Agent profile name for tool filtering
            debug: Enable debug output
            
        Returns:
            List of OpenAI-formatted tool schemas or None if tools disabled
        """
        
        # Get standardized tools from base class
        tools_dict = await self.get_standardized_tools(session_id, agent_profile, debug)
        
        if not tools_dict:
            return None
        
        # Convert ToolSchema objects to OpenAI format
        openai_tools = []
        for tool_name, tool_schema in tools_dict.items():
            openai_tool = self._convert_tool_schema_to_openai_format(tool_schema)
            if openai_tool:
                openai_tools.append(openai_tool)
        
        if debug:
            print(f"[DEBUG] Final OpenAI tools count: {len(openai_tools)}")
        
        return openai_tools if openai_tools else None
    
    def _convert_tool_schema_to_openai_format(self, tool_schema) -> Optional[Dict[str, Any]]:
        """
        Convert ToolSchema to OpenAI function format.
        
        Args:
            tool_schema: ToolSchema object
            
        Returns:
            Dict: OpenAI-formatted tool schema, or None if conversion failed
        """
        try:
            # Get the input schema and convert to dict
            input_schema_dict = tool_schema.inputSchema.model_dump(exclude_none=True)
            
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
                "function": {
                    "name": tool_schema.name,
                    "description": tool_schema.description,
                    "parameters": input_schema_dict
                    # "strict": True  # Temporarily disabled - causes issues with optional params
                }
            }
                   
            return openai_tool
            
        except Exception as e:
            print(f"[WARNING] Failed to convert tool {tool_schema.name} to OpenAI format: {e}")
            print(f"[DEBUG] Tool schema content: {tool_schema}")
            return None

    async def get_schemas_for_system_prompt(self, session_id: str, agent_profile: Optional[str] = None, debug: bool = False) -> List[Dict[str, Any]]:
        """
        Get tool schemas in standardized dictionary format for system prompt embedding.
        
        This method returns a clean dictionary format specifically designed for embedding
        tool schemas into system prompts, separate from the API-specific formats.
        
        Args:
            session_id: Session ID for tool caching (required)
            agent_profile: Agent profile name for tool filtering
            debug: Whether to enable debug output
            
        Returns:
            List[Dict[str, Any]]: Tool schemas in standardized dictionary format for system prompt
        """
        
        # Get standardized tools from base class
        tools_dict = await self.get_standardized_tools(session_id, agent_profile, debug)
        
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
                if debug:
                    print(f"[WARNING] Failed to convert tool {tool_name} for system prompt: {e}")
                continue
        
        if debug:
            print(f"[DEBUG] OpenAI system prompt schemas count: {len(prompt_schemas)}")
        
        return prompt_schemas
    
