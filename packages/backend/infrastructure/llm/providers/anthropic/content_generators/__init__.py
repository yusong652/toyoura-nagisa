"""
Anthropic content generators module.

Provides specialized content generation utilities for the Anthropic API,
including title generation and web search.
"""

from .web_search import AnthropicWebSearchGenerator

__all__ = [
    'AnthropicWebSearchGenerator',
]
