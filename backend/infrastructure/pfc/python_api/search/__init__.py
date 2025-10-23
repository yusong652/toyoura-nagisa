"""Search strategies for PFC SDK documentation.

This package provides pluggable search strategies for finding APIs:
- PathSearchStrategy: Exact path matching
- KeywordSearchStrategy: Natural language keyword search
- Future: SemanticSearchStrategy for embedding-based search
"""

from backend.infrastructure.pfc.shared.search.base import SearchStrategy
from .path_search import PathSearchStrategy
from .keyword_search import KeywordSearchStrategy

__all__ = [
    "SearchStrategy",
    "PathSearchStrategy",
    "KeywordSearchStrategy"
]
