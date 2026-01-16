"""
OpenAI content generators module.

Provides specialized content generation utilities for the OpenAI API,
including title generation and web search.
"""

from .title import OpenAITitleGenerator
from .web_search import OpenAIWebSearchGenerator

__all__ = [
    'OpenAITitleGenerator',
    'OpenAIWebSearchGenerator',
]
