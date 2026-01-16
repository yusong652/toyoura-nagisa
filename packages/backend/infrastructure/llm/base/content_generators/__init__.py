"""
Base content generators module.

Provides abstract base classes for specialized content generation utilities.
"""

from .web_search import BaseWebSearchGenerator
from .web_fetch import BaseWebFetchGenerator, WebFetchResult

__all__ = [
    'BaseWebSearchGenerator',
    'BaseWebFetchGenerator',
    'WebFetchResult',
]
