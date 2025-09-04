"""System prompt builder utilities following Anthropic best practices.

This module centralizes system prompt construction for LLM interactions,
implementing Anthropic's recommended format for tool-enabled conversations.

Key features:
- Dynamic tool schema embedding in system prompt (Anthropic best practice)
- Proper prompt component ordering per official documentation
- Support for base, tool, expression, and memory prompts
- Environment context injection (workspace, date, platform)
- Tool definition formatting in JSON Schema format

Architecture follows Anthropic's recommended structure:
1. Base system instructions
2. Tool access declaration and formatting rules
3. Tool definitions in JSON Schema format
4. Additional context (memory, expression rules)
"""

from __future__ import annotations

import os
import json
from pathlib import Path
from functools import lru_cache
from typing import Optional, List, Dict, Any
from datetime import datetime
import logging

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------

# Base path configuration
BASE_DIR = Path(__file__).parent.parent.parent
CHAT_DIR = BASE_DIR / "chat"
TOOL_DB_PATH = BASE_DIR / "tool_db"
LOCATION_DB_PATH = BASE_DIR / "location_data"
PROMPTS_DIR = BASE_DIR / "config" / "prompts"

# Environment variable overrides
ENV_BASE_PROMPT = "NAGISA_BASE_PROMPT"
ENV_SYSTEM_MD = "NAGISA_SYSTEM_MD"  # Legacy support

# Prompt file paths
DEFAULT_BASE_PROMPT = PROMPTS_DIR / "base_prompt.md"
DEFAULT_TOOL_PROMPT = PROMPTS_DIR / "tool_prompt.md"
DEFAULT_EXPRESSION_PROMPT = PROMPTS_DIR / "expression_prompt.md"
DEFAULT_MEMORY_TEMPLATE = PROMPTS_DIR / "memory_context_template.md"


# -----------------------------------------------------------------------------
# Core Prompt Loading Functions (Migrated from config/__init__.py)
# -----------------------------------------------------------------------------

def _load_prompt_file(filename: str) -> str:
    """Load specified prompt file from config/prompts directory"""
    prompt_path = PROMPTS_DIR / filename
    try:
        return prompt_path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return ""

@lru_cache(maxsize=1)
def get_base_prompt() -> str:
    """
    Load base system prompt.
    Priority: environment variable NAGISA_BASE_PROMPT, then base_prompt.md file.
    """
    base_prompt_from_env = os.getenv("NAGISA_BASE_PROMPT")
    if base_prompt_from_env is not None:
        return base_prompt_from_env.strip()
    
    return _load_prompt_file("base_prompt.md")

@lru_cache(maxsize=1)
def get_expression_prompt() -> str:
    """Load expression/keyword instruction prompt"""
    return _load_prompt_file("expression_prompt.md")

def get_tool_prompt() -> str:
    """Load tool usage guide prompt with workspace root substitution"""
    try:
        from backend.infrastructure.mcp.tools.coding.utils.path_security import WORKSPACE_ROOT
        workspace_root = str(WORKSPACE_ROOT)
    except ImportError:
        # Fallback if import fails
        workspace_root = str(BASE_DIR)
    
    prompt = _load_prompt_file("tool_prompt.md")
    if prompt:
        # Replace {workspace_root} placeholder with actual workspace path
        prompt = prompt.replace("{workspace_root}", workspace_root)
    return prompt


# -----------------------------------------------------------------------------
# System Prompt Assembly Functions
# -----------------------------------------------------------------------------

def get_system_prompt(tools_enabled: bool = True) -> str:
    """
    Get complete system prompt.
    Dynamically combines different prompt modules based on tools_enabled flag.
    """
    base = get_base_prompt()
    expression = get_expression_prompt()
    
    components = [base]
    
    if tools_enabled:
        tool_prompt = get_tool_prompt()
        if tool_prompt:
            components.append(tool_prompt)
            
    components.append(expression)

    # Use separator to join all parts, filtering out empty strings
    full_prompt = "\n\n---\n\n".join(filter(None, components))
    return full_prompt

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
        tool_schemas: List of tool schemas to embed in system prompt
        memory_context: Optional memory context to inject
        workspace_root: Optional workspace root path override
        
    Returns:
        Complete system prompt string following Anthropic format
    """
    components = []
    
    # 1. Base identity and instructions
    base = get_base_prompt()
    if base:
        components.append(base)
    
    # 2. Tool access declaration and schemas (Anthropic best practice)
    if tools_enabled and tool_schemas:
        tool_section = _build_tool_section(tool_schemas)
        if tool_section:
            components.append(tool_section)
    elif tools_enabled:
        # Fallback to traditional tool prompt without embedded schemas
        tool_prompt = get_tool_prompt()
        if tool_prompt:
            components.append(tool_prompt)
    
    # 3. Memory context (if provided)
    if memory_context:
        memory_section = _build_memory_section(memory_context)
        components.append(memory_section)
    
    # 4. Expression/Live2D instructions
    expression = get_expression_prompt()
    if expression:
        components.append(expression)
    
    # Join all components with separators
    return "\n\n---\n\n".join(filter(None, components))


# -----------------------------------------------------------------------------
# Tool Schema Embedding (Anthropic Best Practice)
# -----------------------------------------------------------------------------

def _build_tool_section(tool_schemas: List[Dict[str, Any]]) -> str:
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


# -----------------------------------------------------------------------------
# Memory Context Integration
# -----------------------------------------------------------------------------

def _build_memory_section(memory_context: str) -> str:
    """
    Build memory context section for system prompt.
    
    Args:
        memory_context: Formatted memory context string
        
    Returns:
        Memory section with proper formatting
    """
    if not memory_context or not memory_context.strip():
        return ""
    
    return f"## Relevant Context from Memory\n\n{memory_context.strip()}"


# -----------------------------------------------------------------------------
# Advanced System Prompt Builder with Memory Integration
# -----------------------------------------------------------------------------

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
    logger = logging.getLogger(__name__)
    
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


async def save_conversation_to_memory(
    user_message: Any,  # BaseMessage type
    assistant_message: Any,  # BaseMessage type
    session_id: str,
    user_id: str = "default",
    metadata: Optional[Dict[str, Any]] = None
) -> None:
    """
    Save conversation turn to memory.
    
    This function provides a centralized way to save conversations to memory
    from the prompt builder context.
    
    Args:
        user_message: User's BaseMessage object
        assistant_message: Assistant's BaseMessage object
        session_id: Session ID
        user_id: User ID
        metadata: Additional metadata
    """
    logger = logging.getLogger(__name__)
    
    try:
        from backend.infrastructure.memory.memory_injection import MemoryInjectionMiddleware
        from backend.config.memory import MemoryConfig
        
        memory_config = MemoryConfig()
        
        # Skip if memory saving is disabled
        if not memory_config.should_save_memory():
            return
        
        memory_middleware = MemoryInjectionMiddleware(config=memory_config)
        
        await memory_middleware.save_conversation_turn(
            user_message=user_message,
            assistant_message=assistant_message,
            session_id=session_id,
            user_id=user_id,
            metadata=metadata
        )
        
    except Exception as e:
        logger.error(f"Failed to save conversation to memory: {e}")


# -----------------------------------------------------------------------------
# Legacy Compatibility (Deprecated - use build_system_prompt instead)
# -----------------------------------------------------------------------------

@lru_cache(maxsize=1)
def load_base_prompt() -> str:
    """Legacy function - use get_base_prompt() instead."""
    return get_base_prompt() 