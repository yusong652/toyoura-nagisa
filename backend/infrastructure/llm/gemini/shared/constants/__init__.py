"""
Constants for Gemini API operations.

This package contains organized constants for different aspects of Gemini API operations,
making it easier to manage and maintain constants across the codebase.
"""

from .pydantic import PYDANTIC_METADATA_ATTRS
from .text_to_image import (
    DEFAULT_NEGATIVE_PROMPT,
    TEXT_TO_IMAGE_PROMPT_PATTERN,
    NEGATIVE_PROMPT_PATTERN,
    TEXT_TO_IMAGE_HISTORY_FILENAME,
    DEFAULT_FEW_SHOT_MAX_LENGTH,
    DEFAULT_CONTEXT_MESSAGE_COUNT,
    DEFAULT_MAX_HISTORY_LENGTH
)

__all__ = [
    # Pydantic constants
    'PYDANTIC_METADATA_ATTRS',
    
    # Text-to-image constants
    'DEFAULT_NEGATIVE_PROMPT',
    'TEXT_TO_IMAGE_PROMPT_PATTERN',
    'NEGATIVE_PROMPT_PATTERN', 
    'TEXT_TO_IMAGE_HISTORY_FILENAME',
    'DEFAULT_FEW_SHOT_MAX_LENGTH',
    'DEFAULT_CONTEXT_MESSAGE_COUNT',
    'DEFAULT_MAX_HISTORY_LENGTH'
]