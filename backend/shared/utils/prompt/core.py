"""
Core prompt loading and management functions.
"""

import os
from functools import lru_cache

from .config import PROMPTS_DIR, BASE_DIR


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
    """
    DEPRECATED: Use get_tool_prompt_with_schemas() for dynamic tool loading.
    Load basic tool usage guide prompt with workspace root substitution.
    """
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


# Legacy compatibility
@lru_cache(maxsize=1)
def load_base_prompt() -> str:
    """Legacy function - use get_base_prompt() instead."""
    return get_base_prompt()