"""PFC SDK Documentation System - Direct Access Interface.

This module provides direct access to the PFC Python SDK documentation
components without wrapper layers.

Usage:
    from backend.infrastructure.pfc.python_api import (
        DocumentationLoader,
        APIDocFormatter
    )

    # For API search, use the unified search system:
    from backend.infrastructure.pfc.shared.query import APISearch
    results = APISearch.search("create ball")

    # Load and format documentation
    for result in results:
        doc = DocumentationLoader.load_api_doc(result.document.name)
        markdown = APIDocFormatter.format_full_doc(
            doc,
            api_name=result.document.name,
            metadata=result.document.metadata
        )

Core Components:
    - DocumentationLoader: Load documentation for specific APIs
    - APIDocFormatter: Format documentation as markdown

Data Models:
    - SearchResult: Search result with score and metadata (legacy format)
    - APIDocumentation: Structured API documentation
    - SearchStrategy: Search strategy enumeration

Note:
    For API search functionality, use the unified search system:
    - backend.infrastructure.pfc.shared.query.APISearch (BM25-based search)
"""

from backend.infrastructure.pfc.python_api.formatter import APIDocFormatter
from backend.infrastructure.pfc.python_api.loader import DocumentationLoader
from backend.infrastructure.pfc.python_api.models import SearchResult, APIDocumentation, SearchStrategy

# Aliases for browse tool (more intuitive names)
APILoader = DocumentationLoader
APIFormatter = APIDocFormatter


# Public API exports
__all__ = [
    # Core components
    "DocumentationLoader",
    "APIDocFormatter",
    # Aliases for browse tool
    "APILoader",
    "APIFormatter",
    # Data models
    "SearchResult",
    "APIDocumentation",
    "SearchStrategy"
]
