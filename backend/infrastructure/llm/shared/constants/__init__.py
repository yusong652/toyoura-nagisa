"""
Shared constants for LLM infrastructure.

This module contains common constants and configuration values that can be shared
across different LLM provider implementations.
"""

from .defaults import *
from .prompts import *

__all__ = [
    # Default values
    "DEFAULT_FEW_SHOT_MAX_LENGTH",
    "DEFAULT_CONTEXT_MESSAGE_COUNT", 
    "DEFAULT_TITLE_MAX_LENGTH",
    "DEFAULT_MAX_HISTORY_LENGTH",
    "TEXT_TO_IMAGE_HISTORY_FILENAME",
    
    # System prompts
    "DEFAULT_TITLE_GENERATION_SYSTEM_PROMPT",
    "DEFAULT_WEB_SEARCH_SYSTEM_PROMPT", 
    
    # Temperature settings
    "DEFAULT_TITLE_GENERATION_TEMPERATURE",
    "DEFAULT_WEB_SEARCH_TEMPERATURE",
    
    # Prompt text
    "TITLE_GENERATION_REQUEST_TEXT",
    "CONVERSATION_TEXT_PROMPT_PREFIX",
    "CONVERSATION_VIDEO_PROMPT_PREFIX",
    
    # Patterns
    "TEXT_TO_IMAGE_PROMPT_PATTERN",
    "NEGATIVE_PROMPT_PATTERN",
    "TITLE_PROMPT_PATTERN",
]