"""
Tool schema embedding and management for prompt system.
"""

import json
import logging
from typing import List, Dict, Any, Optional

from .core import _load_prompt_file

logger = logging.getLogger(__name__)


async def get_tool_prompt_with_schemas(
    agent_profile: Optional[str] = None,
    tool_schemas: Optional[List[Dict[str, Any]]] = None
) -> str:
    """
    Build complete tool prompt with base context and embedded tool schemas.
    
    Loads the base tool prompt template with workspace_root context, then 
    embeds provided tool schemas following Anthropic best practices.
    
    Args:
        agent_profile: Agent profile type (coding, lifestyle, general, or "disabled")
        tool_schemas: Pre-fetched tool schemas from appropriate LLM provider
        
    Returns:
        Complete tool prompt with workspace context and embedded schemas
    """
    if agent_profile == "disabled" or agent_profile is None:
        return ""
    
    # Load base tool prompt with workspace_root substitution
    try:
        from backend.infrastructure.mcp.tools.coding.utils.path_security import WORKSPACE_ROOT
        workspace_root = str(WORKSPACE_ROOT)
    except ImportError:
        from .config import BASE_DIR
        workspace_root = str(BASE_DIR)
    
    base_prompt = _load_prompt_file("tool_prompt.md")
    if base_prompt:
        base_prompt = base_prompt.replace("{workspace_root}", workspace_root)
    
    # Build tool schemas section if provided
    if tool_schemas:
        # Build tool schemas section
        sections = [
            "\nIn this environment you have access to a set of tools you can use to answer the user's question.",
            "String and scalar parameters should be specified as is, while lists and objects should use JSON format.",
            "Here are the functions available in JSONSchema format:",
            "<functions>"
        ]
        
        for tool_schema in tool_schemas:
            tool_json = json.dumps(tool_schema, separators=(',', ':'))
            sections.append(f'<function>{tool_json}</function>')
        
        sections.append("</functions>")
        tool_section = "\n".join(sections)
        
        # Replace {tool_schemas} placeholder with actual schemas
        if base_prompt:
            return base_prompt.replace("{tool_schemas}", tool_section)
        else:
            return tool_section
    
    # Return base prompt with workspace context (remove tool_schemas placeholder)
    if base_prompt:
        return base_prompt.replace("{tool_schemas}", "")
    return ""


def build_tool_section(tool_schemas: List[Dict[str, Any]]) -> str:
    """
    Build tool section following Anthropic's recommended format.
    
    Legacy function for backwards compatibility.
    
    Args:
        tool_schemas: List of tool schema dictionaries
        
    Returns:
        Formatted tool section string
    """
    if not tool_schemas:
        return ""
    
    sections = [
        "In this environment you have access to a set of tools you can use to answer the user's question.",
        "String and scalar parameters should be specified as is, while lists and objects should use JSON format.",
        "Here are the functions available in JSONSchema format:",
        "<functions>"
    ]
    
    for tool_schema in tool_schemas:
        tool_json = json.dumps(tool_schema, separators=(',', ':'))
        sections.append(f'<function>{tool_json}</function>')
    
    sections.append("</functions>")
    return "\n".join(sections)