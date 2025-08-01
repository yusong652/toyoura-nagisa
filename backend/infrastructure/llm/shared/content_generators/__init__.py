"""
Shared content generators for LLM infrastructure.

This module contains common content generation implementations that can be shared
across different LLM provider implementations, reducing code duplication.
"""

from .web_search_generator import SharedWebSearchGenerator

__all__ = [
    "SharedWebSearchGenerator"
]