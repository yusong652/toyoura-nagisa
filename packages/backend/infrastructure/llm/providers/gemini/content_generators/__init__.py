"""
Gemini content generators module.

Provides specialized content generation utilities for the Gemini API,
including title generation, web search, image prompts, and video prompts.

This module maintains backward compatibility - all generators can be imported
directly from this package:

    from backend.infrastructure.llm.providers.gemini.content_generators import (
        GeminiTitleGenerator,
        GeminiWebSearchGenerator,
        GeminiImagePromptGenerator,
        GeminiVideoPromptGenerator,
    )
"""

from .title import GeminiTitleGenerator
from .web_search import GeminiWebSearchGenerator
from .image_prompt import GeminiImagePromptGenerator
from .video_prompt import GeminiVideoPromptGenerator

__all__ = [
    'GeminiTitleGenerator',
    'GeminiWebSearchGenerator',
    'GeminiImagePromptGenerator',
    'GeminiVideoPromptGenerator',
]
