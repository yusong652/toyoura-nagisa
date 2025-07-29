"""
Shared utility functions for LLM infrastructure.

This module contains common utility functions that can be shared across
different LLM provider implementations.
"""

from .text_processing import (
    extract_text_content,
    parse_text_to_image_response,
    enhance_prompts_with_defaults,
    parse_title_response
)

from .text_to_image import (
    load_text_to_image_history,
    save_text_to_image_generation,
    get_text_to_image_history_file
)

from .prompt_templates import (
    apply_template_variables,
    format_conversation_context
)

from .response_parsing import (
    extract_json_from_response,
    parse_structured_response
)

__all__ = [
    # Text processing
    "extract_text_content",
    "parse_text_to_image_response", 
    "enhance_prompts_with_defaults",
    "parse_title_response",
    
    # Text-to-image utilities
    "load_text_to_image_history",
    "save_text_to_image_generation",
    "get_text_to_image_history_file",
    
    # Prompt templates
    "apply_template_variables",
    "format_conversation_context",
    
    # Response parsing
    "extract_json_from_response",
    "parse_structured_response"
]