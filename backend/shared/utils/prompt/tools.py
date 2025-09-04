"""
Tool schema embedding and management for prompt system.
"""

import json
import logging
from typing import List, Dict, Any, Optional

from .core import _load_prompt_file

logger = logging.getLogger(__name__)


async def get_tool_prompt_with_schemas(
    session_id: str,
    agent_profile: Optional[str] = None,
    tools_enabled: bool = True
) -> str:
    """
    Build tool prompt with embedded tool schemas based on agent profile.
    
    This function dynamically loads tool schemas from the MCP server based on 
    the current agent profile and embeds them following Anthropic best practices.
    
    Args:
        session_id: Session ID for tool context
        agent_profile: Agent profile type (coding, lifestyle, general, or None for disabled)
        tools_enabled: Whether tools are enabled
        
    Returns:
        Tool prompt with embedded schemas in Anthropic format
    """
    if not tools_enabled or agent_profile == "disabled":
        return ""
    
    try:
        # Import tool manager to get schemas
        from backend.infrastructure.llm.providers.anthropic.tool_manager import AnthropicToolManager
        
        # Create temporary tool manager to fetch schemas
        tool_manager = AnthropicToolManager(tools_enabled=True)
        
        # Get tool schemas based on agent profile
        tool_schemas = await tool_manager.get_function_call_schemas(
            session_id=session_id,
            agent_profile=agent_profile,
            debug=False
        )
        
        if tool_schemas:
            # Build tool section with embedded schemas
            return build_tool_section(tool_schemas)
        else:
            # No tools available for this profile
            return ""
            
    except Exception as e:
        logger.error(f"Failed to load tool schemas: {e}")
        # Fallback to basic tool prompt without schemas
        return _load_prompt_file("tool_prompt.md")


def build_tool_section(tool_schemas: List[Dict[str, Any]]) -> str:
    """
    Build tool section following Anthropic's recommended format.
    
    Format:
    In this environment you have access to a set of tools...
    
    [Formatting Instructions]
    
    Here are the functions available in JSONSchema format:
    <functions>
    <function>{"name": "tool_name", "description": "...", "parameters": {...}}</function>
    ...
    </functions>
    
    Args:
        tool_schemas: List of tool schema dictionaries
        
    Returns:
        Formatted tool section string
    """
    if not tool_schemas:
        return ""
    
    sections = []
    
    # Tool access declaration
    sections.append(
        "In this environment you have access to a set of tools you can use to answer the user's question."
    )
    
    # Formatting instructions (Anthropic requirement)
    sections.append(
        "String and scalar parameters should be specified as is, while lists and objects should use JSON format."
    )
    
    # Tool definitions in JSON Schema format
    sections.append("Here are the functions available in JSONSchema format:")
    sections.append("<functions>")
    
    for tool_schema in tool_schemas:
        # Format each tool as a compact JSON object
        tool_json = json.dumps(tool_schema, separators=(',', ':'))
        sections.append(f'<function>{tool_json}</function>')
    
    sections.append("</functions>")
    
    return "\n".join(sections)