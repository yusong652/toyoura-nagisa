"""
Prompt utilities for toyoura-nagisa - Centralized prompt construction following Anthropic best practices.

This module provides a modular and extensible prompt building system with:
- Core prompt loading (no caching - always fresh)
- Tool schema embedding (Anthropic best practice)
- Dynamic tool loading based on agent configuration
"""

from .core import get_base_prompt, get_expression_prompt

from .builder import build_system_prompt

__all__ = [
    # Core prompt functions
    "get_base_prompt",
    "get_expression_prompt",
    # Builder functions
    "build_system_prompt",
]
