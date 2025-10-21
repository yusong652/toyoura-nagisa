"""PFC SDK Documentation System - Direct Access Interface.

This module provides direct access to the PFC Python SDK documentation
components without wrapper layers.

Usage:
    from backend.infrastructure.pfc.sdk import (
        APISearcher,
        DocumentationLoader,
        APIDocFormatter
    )

    # Search for APIs
    searcher = APISearcher()
    results = searcher.search("create ball")

    # Load and format documentation
    for result in results:
        doc = DocumentationLoader.load_api_doc(result.api_name)
        markdown = APIDocFormatter.format_full_doc(doc, result)

Core Components:
    - APISearcher: Smart search with automatic strategy selection
    - DocumentationLoader: Load documentation for specific APIs
    - APIDocFormatter: Format documentation as markdown

Data Models:
    - SearchResult: Search result with score and metadata
    - APIDocumentation: Structured API documentation
    - SearchStrategy: Search strategy enumeration
"""

from backend.infrastructure.pfc.sdk.searcher import APISearcher
from backend.infrastructure.pfc.sdk.formatter import APIDocFormatter
from backend.infrastructure.pfc.sdk.loader import DocumentationLoader
from backend.infrastructure.pfc.sdk.models import SearchResult, APIDocumentation, SearchStrategy


# Public API exports
__all__ = [
    # Core components
    "APISearcher",
    "DocumentationLoader",
    "APIDocFormatter",
    # Data models
    "SearchResult",
    "APIDocumentation",
    "SearchStrategy"
]
