"""Shared models for PFC search system.

This package provides unified data models for the search infrastructure,
enabling consistent handling of different document types (commands, APIs, etc.).
"""

from backend.infrastructure.pfc.shared.models.document import (
    DocumentType,
    SearchDocument
)
from backend.infrastructure.pfc.shared.models.search_result import (
    SearchResult
)

__all__ = [
    "DocumentType",
    "SearchDocument",
    "SearchResult"
]
