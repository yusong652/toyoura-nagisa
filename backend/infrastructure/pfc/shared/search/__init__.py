"""Shared search infrastructure for PFC documentation systems.

This module provides unified search components used by both command search
and Python API search systems.
"""

from backend.infrastructure.pfc.shared.search.base import SearchStrategy
from backend.infrastructure.pfc.shared.search.models import (
    SearchResult,
    DocumentType,
    SearchStrategy as SearchStrategyEnum,
    CommandSearchResult  # Backward compatibility alias
)

__all__ = [
    "SearchStrategy",
    "SearchResult",
    "DocumentType",
    "SearchStrategyEnum",
    "CommandSearchResult",
]
