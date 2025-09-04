"""
Main prompt builder functions combining all components.
"""

import logging
from typing import List, Dict, Any, Optional

from .core import get_base_prompt, get_expression_prompt
from .tools import get_tool_prompt_with_schemas, build_tool_section
from .memory import build_memory_section

logger = logging.getLogger(__name__)


def build_system_prompt(
    tools_enabled: bool = True,
    tool_schemas: Optional[List[Dict[str, Any]]] = None,
    memory_context: Optional[str] = None,
    workspace_root: Optional[str] = None
) -> str:
    """
    Build complete system prompt following Anthropic best practices.
    
    This is the main entry point for creating system prompts with support for:
    - Base identity and instructions
    - Tool definitions embedded in prompt (Anthropic best practice)
    - Memory context injection
    - Expression/Live2D instructions
    
    Args:
        tools_enabled: Whether to include tool-related prompts
        tool_schemas: List of tool schemas to embed in system prompt (required if tools_enabled)
        memory_context: Optional memory context to inject
        workspace_root: Optional workspace root path override (unused, kept for compatibility)
        
    Returns:
        Complete system prompt string following Anthropic format
    """
    components = []
    
    # 1. Base identity and instructions
    base = get_base_prompt()
    if base:
        components.append(base)
    
    # 2. Tool access declaration and schemas (Anthropic best practice)
    # Always embed tool schemas when tools are enabled - no fallback
    if tools_enabled and tool_schemas:
        tool_section = build_tool_section(tool_schemas)
        if tool_section:
            components.append(tool_section)
    
    # 3. Memory context (if provided)
    if memory_context:
        memory_section = build_memory_section(memory_context)
        components.append(memory_section)
    
    # 4. Expression/Live2D instructions
    expression = get_expression_prompt()
    if expression:
        components.append(expression)
    
    # Join all components with separators
    return "\n\n---\n\n".join(filter(None, components))


async def build_system_prompt_async(
    session_id: str,
    agent_profile: Optional[str] = None,
    tools_enabled: bool = True,
    memory_context: Optional[str] = None,
    workspace_root: Optional[str] = None
) -> str:
    """
    Build complete system prompt with dynamic tool loading based on agent profile.
    
    This async version automatically loads tool schemas from MCP based on the agent profile,
    eliminating the need to pass tool_schemas manually.
    
    Args:
        session_id: Session ID for tool context (required)
        agent_profile: Agent profile type (coding, lifestyle, general, or None for disabled)
        tools_enabled: Whether to include tool-related prompts
        memory_context: Optional memory context to inject
        workspace_root: Optional workspace root path override (unused, kept for compatibility)
        
    Returns:
        Complete system prompt string with embedded tool schemas
    """
    components = []
    
    # 1. Base identity and instructions
    base = get_base_prompt()
    if base:
        components.append(base)
    
    # 2. Tool access declaration and schemas (dynamically loaded)
    if tools_enabled and agent_profile != "disabled":
        tool_section = await get_tool_prompt_with_schemas(
            session_id=session_id,
            agent_profile=agent_profile,
            tools_enabled=tools_enabled
        )
        if tool_section:
            components.append(tool_section)
    
    # 3. Memory context (if provided)
    if memory_context:
        memory_section = build_memory_section(memory_context)
        components.append(memory_section)
    
    # 4. Expression/Live2D instructions
    expression = get_expression_prompt()
    if expression:
        components.append(expression)
    
    # Join all components with separators
    return "\n\n---\n\n".join(filter(None, components))


async def build_enhanced_system_prompt(
    tools_enabled: bool = True,
    tool_schemas: Optional[List[Dict[str, Any]]] = None,
    user_message: Optional[Any] = None,  # BaseMessage type
    session_id: Optional[str] = None,
    user_id: str = "default",
    enable_memory: bool = True,
    workspace_root: Optional[str] = None
) -> tuple[str, Dict[str, Any]]:
    """
    Build enhanced system prompt with memory injection following Anthropic best practices.
    
    This is the main entry point for creating system prompts with full feature support:
    - Base identity and instructions
    - Tool definitions embedded in prompt (Anthropic best practice)
    - Memory context injection from conversation history
    - Expression/Live2D instructions
    
    Args:
        tools_enabled: Whether to include tool-related prompts
        tool_schemas: List of tool schemas to embed in system prompt
        user_message: Latest user message for memory context retrieval
        session_id: Session ID for memory retrieval
        user_id: User ID for memory operations
        enable_memory: Whether to enable memory injection
        workspace_root: Optional workspace root path override
        
    Returns:
        Tuple of (enhanced_system_prompt, memory_injection_result)
    """
    # Build base system prompt
    base_prompt = build_system_prompt(
        tools_enabled=tools_enabled,
        tool_schemas=tool_schemas,
        workspace_root=workspace_root
    )
    
    # Memory injection result metadata
    memory_result = {
        "success": True,
        "injected_count": 0,
        "context_tokens": 0,
        "formatted_context": "",
        "error": None
    }
    
    # Skip memory injection if disabled or no user message
    if not enable_memory or not user_message or not session_id:
        return base_prompt, memory_result
    
    try:
        # Import memory injection components
        from backend.infrastructure.memory.memory_injection import MemoryInjectionMiddleware
        from backend.config.memory import MemoryConfig
        
        # Initialize memory injection middleware
        memory_config = MemoryConfig()
        
        # Skip if memory injection is disabled in config
        if not memory_config.should_inject_memory():
            memory_result["error"] = "Memory injection disabled in config"
            return base_prompt, memory_result
        
        memory_middleware = MemoryInjectionMiddleware(config=memory_config)
        
        # Get enhanced system prompt with memory context
        enhanced_prompt, injection_result = await memory_middleware.get_enhanced_system_prompt(
            base_system_prompt=base_prompt,
            user_message=user_message,
            session_id=session_id,
            user_id=user_id
        )
        
        # Update memory result with injection details
        memory_result.update({
            "success": injection_result.success,
            "injected_count": injection_result.injected_count,
            "context_tokens": getattr(injection_result, 'context_tokens', 0),
            "formatted_context": getattr(injection_result, 'formatted_context', ''),
            "error": injection_result.error
        })
        
        return enhanced_prompt, memory_result
        
    except Exception as e:
        logger.error(f"Memory injection failed in prompt builder: {e}")
        memory_result.update({
            "success": False,
            "error": f"Memory injection error: {str(e)}"
        })
        return base_prompt, memory_result