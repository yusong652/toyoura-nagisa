"""
OpenRouter content generators module.

Provides specialized content generation utilities for the OpenRouter API,
including title generation.

Note: OpenRouter does not support provider-specific features like web search.
For web search capabilities, use native provider implementations.
"""

from .title import OpenRouterTitleGenerator

__all__ = [
    'OpenRouterTitleGenerator',
]
