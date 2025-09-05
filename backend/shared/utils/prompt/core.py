"""
Core prompt loading and management functions.
"""

import os

from .config import PROMPTS_DIR, BASE_DIR


def _load_prompt_file(filename: str) -> str:
    """Load specified prompt file from config/prompts directory"""
    prompt_path = PROMPTS_DIR / filename
    try:
        return prompt_path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return ""


def get_base_prompt() -> str:
    """
    Load base system prompt.
    Priority: environment variable NAGISA_BASE_PROMPT, then base_prompt.md file.
    """
    base_prompt_from_env = os.getenv("NAGISA_BASE_PROMPT")
    if base_prompt_from_env is not None:
        return base_prompt_from_env.strip()
    
    return _load_prompt_file("base_prompt.md")


def get_expression_prompt() -> str:
    """Load expression/keyword instruction prompt"""
    return _load_prompt_file("expression_prompt.md")


def get_tool_prompt() -> str:
    """
    DEPRECATED: Use build_system_prompt() for modern tool schema embedding with memory injection.
    Load basic tool usage guide prompt with workspace root substitution.
    
    This function is kept for legacy compatibility only.
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

