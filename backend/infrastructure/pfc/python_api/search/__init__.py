"""Search strategies for PFC SDK documentation.

This package provides pluggable search strategies for finding APIs:
- PathSearchStrategy: Exact path matching (used for API path queries)

Note:
    Natural language search now uses the unified BM25 engine:
    - backend.infrastructure.pfc.shared.query.APISearch (BM25-based search)
"""

from backend.infrastructure.pfc.shared.search.base import SearchStrategy
from .path_search import PathSearchStrategy

__all__ = [
    "SearchStrategy",
    "PathSearchStrategy"
]
