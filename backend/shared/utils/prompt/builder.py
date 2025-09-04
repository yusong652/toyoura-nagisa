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
    agent_profile: str = "general",
    tool_schemas: Optional[List[Dict[str, Any]]] = None,
    session_id: Optional[str] = None,
    user_id: str = "default",
    enable_memory: bool = True,
) -> str:
    """
    Build complete system prompt following Anthropic best practices.
    
    This is the main entry point for creating system prompts with support for:
    - Base identity and instructions
    - Tool definitions embedded in prompt (Anthropic best practice)
    - Automatic memory context injection from conversation history
    - Expression/Live2D instructions
    
    Args:
        agent_profile: Agent profile type ("general", "coding", "lifestyle", "disabled", etc.)
        tool_schemas: List of tool schemas to embed in system prompt
        session_id: Session ID for memory retrieval (when provided, latest user message extracted automatically)
        user_id: User ID for memory operations
        enable_memory: Whether to enable memory injection
        
    Returns:
        Complete system prompt string following Anthropic format with memory context
    """
    components = []
    
    # 1. Base identity and instructions
    base = get_base_prompt()
    if base:
        components.append(base)
    
    # 2. Tool access declaration and schemas (Anthropic best practice)
    # Embed tool schemas when agent profile allows tools and schemas are provided
    if agent_profile != "disabled" and tool_schemas:
        tool_section = build_tool_section(tool_schemas)
        if tool_section:
            components.append(tool_section)
    
    # 3. Memory context injection (if enabled and session provided)
    if enable_memory and session_id:
        try:
            # Extract latest user message from session history
            from backend.infrastructure.storage.session_manager import load_history
            from backend.domain.models.message_factory import message_factory_no_thinking
            
            recent_history = load_history(session_id)
            recent_msgs = [message_factory_no_thinking(msg) if isinstance(msg, dict) else msg for msg in recent_history]
            
            # Find latest user message
            user_message = None
            for msg in reversed(recent_msgs):
                if hasattr(msg, 'role') and msg.role == 'user':
                    user_message = msg
                    break
            
            # Skip memory injection if no user message found
            if not user_message:
                logger.debug("No user message found in session history, skipping memory injection")
            else:
                # Import and run memory injection synchronously
                import asyncio
                from backend.infrastructure.memory.memory_injection import MemoryInjectionMiddleware
                from backend.config.memory import MemoryConfig
                
                memory_config = MemoryConfig()
                if memory_config.should_inject_memory():
                    memory_middleware = MemoryInjectionMiddleware(config=memory_config)
                    
                    # Build base prompt so far
                    base_prompt_so_far = "\n\n---\n\n".join(filter(None, components))
                    
                    # Create event loop for async operation
                    try:
                        loop = asyncio.get_event_loop()
                    except RuntimeError:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                    
                    # Run memory injection
                    enhanced_prompt, injection_result = loop.run_until_complete(
                        memory_middleware.get_enhanced_system_prompt(
                            base_system_prompt=base_prompt_so_far,
                            user_message=user_message,
                            session_id=session_id,
                            user_id=user_id
                        )
                    )
                    
                    if injection_result.success and enhanced_prompt != base_prompt_so_far:
                        # Memory was injected, add expression and return
                        expression = get_expression_prompt()
                        if expression:
                            return f"{enhanced_prompt}\n\n---\n\n{expression}"
                        return enhanced_prompt
                    
        except Exception as e:
            logger.error(f"Memory injection failed in build_system_prompt: {e}")
            # Continue without memory injection
    
    # 4. Expression/Live2D instructions
    expression = get_expression_prompt()
    if expression:
        components.append(expression)
    
    # Join all components with separators
    return "\n\n---\n\n".join(filter(None, components))




