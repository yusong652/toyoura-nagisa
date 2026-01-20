"""
Shared constants for LLM infrastructure.

This module contains common constants and configuration values that can be shared
across different LLM provider implementations.
"""

from .defaults import *
from .prompts import *

__all__ = [
    # Default values
    "DEFAULT_TITLE_MAX_LENGTH",
    "DEFAULT_TITLE_GENERATION_MAX_TOKENS",
    
    # System prompts
    "DEFAULT_TITLE_GENERATION_SYSTEM_PROMPT",
    "DEFAULT_WEB_SEARCH_SYSTEM_PROMPT", 
    
    # Temperature settings
    "DEFAULT_TITLE_GENERATION_TEMPERATURE",
    "DEFAULT_WEB_SEARCH_TEMPERATURE",
    
    # Prompt text
    "TITLE_GENERATION_REQUEST_TEXT",
    
    # Patterns
    "TITLE_PROMPT_PATTERN",
]
