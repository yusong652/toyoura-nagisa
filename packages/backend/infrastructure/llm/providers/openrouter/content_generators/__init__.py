"""
OpenRouter content generators module.

Provides specialized content generation utilities for the OpenRouter API,
including title generation, image prompts, and video prompts.

Note: OpenRouter does not support provider-specific features like Kimi's $web_search.
For web search capabilities, use native provider implementations.

This module maintains backward compatibility - all generators can be imported
directly from this package:

    from backend.infrastructure.llm.providers.openrouter.content_generators import (
        OpenRouterTitleGenerator,
        OpenRouterImagePromptGenerator,
        OpenRouterVideoPromptGenerator,
    )
"""

from .title import OpenRouterTitleGenerator
from .image_prompt import OpenRouterImagePromptGenerator
from .video_prompt import OpenRouterVideoPromptGenerator

__all__ = [
    'OpenRouterTitleGenerator',
    'OpenRouterImagePromptGenerator',
    'OpenRouterVideoPromptGenerator',
]
