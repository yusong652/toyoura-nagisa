"""
Google content generators module.

Provides specialized content generation utilities for the Google API,
including title generation, web search, web fetch, image prompts, and video prompts.

This module maintains backward compatibility - all generators can be imported
directly from this package:

    from backend.infrastructure.llm.providers.google.content_generators import (
        GoogleTitleGenerator,
        GoogleWebSearchGenerator,
        GoogleWebFetchGenerator,
        GoogleImagePromptGenerator,
        GoogleVideoPromptGenerator,
    )
"""

from .title import GoogleTitleGenerator
from .web_search import GoogleWebSearchGenerator
from .web_fetch import GoogleWebFetchGenerator
from .image_prompt import GoogleImagePromptGenerator
from .video_prompt import GoogleVideoPromptGenerator

__all__ = [
    'GoogleTitleGenerator',
    'GoogleWebSearchGenerator',
    'GoogleWebFetchGenerator',
    'GoogleImagePromptGenerator',
    'GoogleVideoPromptGenerator',
]
