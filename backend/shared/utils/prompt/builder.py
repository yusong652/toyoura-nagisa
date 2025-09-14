"""
Main prompt builder functions combining all components.
"""

import logging
from typing import Optional, List, Dict, Any

from .core import get_base_prompt, get_expression_prompt
from .tools import get_tool_prompt_with_schemas
from .memory import build_memory_section_from_session

logger = logging.getLogger(__name__)


async def build_system_prompt(
    agent_profile: str = "general",
    session_id: Optional[str] = None,
    user_id: Optional[str] = None,
    enable_memory: bool = True,
    tool_schemas: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """
    Build complete system prompt following Anthropic best practices.
    
    This is the main entry point for creating system prompts with support for:
    - Base identity and instructions
    - Tool prompt with workspace context and embedded schemas
    - Automatic memory context injection from conversation history
    - Expression/Live2D instructions
    
    Args:
        agent_profile: Agent profile type ("general", "coding", "lifestyle", "disabled", etc.)
        session_id: Session ID for memory retrieval
        user_id: User ID for memory operations
        enable_memory: Whether to enable memory injection (controlled by frontend)
        tool_schemas: Pre-fetched tool schemas from LLM provider's tool manager
        
    Returns:
        Complete system prompt string following Anthropic format with memory context
    """
    components = []
    
    # 1. Base identity and instructions
    base = get_base_prompt()
    if base:
        components.append(base)
    
    # 2. Tool access declaration and schemas (Anthropic best practice)
    # Use complete tool prompt with workspace context and embedded schemas
    if agent_profile != "disabled":
        tool_section = await get_tool_prompt_with_schemas(
            agent_profile=agent_profile,
            tool_schemas=tool_schemas
        )
        if tool_section:
            components.append(tool_section)
    
    # 3. Memory context injection (if enabled)
    if enable_memory and session_id:
        memory_content = await build_memory_section_from_session(session_id, user_id)
        if memory_content:
            components.append(f"## Relevant Context from Memory\n\n{memory_content}")
        else:
            components.append("## Relevant Context from Memory\n\n(No relevant memories found for current query)")
    
    # 4. Expression/Live2D instructions
    expression = get_expression_prompt()
    if expression:
        components.append(expression)
    
    # Join all components with separators
    return "\n\n---\n\n".join(filter(None, components))




