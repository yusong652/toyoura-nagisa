"""
Prompt utilities for aiNagisa - Centralized prompt construction following Anthropic best practices.

This module provides a modular and extensible prompt building system with:
- Core prompt loading (no caching - always fresh)
- Tool schema embedding (Anthropic best practice)
- Memory context integration
- Dynamic tool loading based on agent profiles
"""

from .core import (
    get_base_prompt,
    get_expression_prompt,
    get_tool_prompt
)

from .builder import (
    build_system_prompt
)

from .tools import (
    get_tool_prompt_with_schemas,
    build_tool_section
)

from .memory import (
    build_memory_section_from_session
)

__all__ = [
    # Core prompt functions
    'get_base_prompt',
    'get_expression_prompt',
    'get_tool_prompt',
    
    # Builder functions
    'build_system_prompt',
    
    # Tool functions
    'get_tool_prompt_with_schemas',
    'build_tool_section',
    
    # Memory functions
    'build_memory_section_from_session'
]