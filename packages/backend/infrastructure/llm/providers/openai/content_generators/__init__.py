"""
OpenAI content generators module.

Provides specialized content generation utilities for the OpenAI API,
including title generation, web search, and image prompts.

This module maintains backward compatibility - all generators can be imported
directly from this package:

    from backend.infrastructure.llm.providers.openai.content_generators import (
        OpenAITitleGenerator,
        OpenAIWebSearchGenerator,
        OpenAIImagePromptGenerator,
    )
"""

from .title import OpenAITitleGenerator
from .web_search import OpenAIWebSearchGenerator
from .image_prompt import OpenAIImagePromptGenerator

__all__ = [
    'OpenAITitleGenerator',
    'OpenAIWebSearchGenerator',
    'OpenAIImagePromptGenerator',
]
