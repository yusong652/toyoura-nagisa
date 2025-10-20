"""PFC SDK Documentation System - Unified Interface.

This module provides the high-level API for searching and formatting
PFC Python SDK documentation. It's the main entry point for all SDK
documentation operations.

Architecture:
    This module implements the Facade pattern, hiding the complexity
    of the underlying search strategies, loaders, and formatters behind
    a simple, easy-to-use interface.

Usage:
    from backend.infrastructure.pfc.sdk import search_api, format_api_doc

    # Search for APIs
    results = search_api("create ball")

    # Load and format documentation
    for result in results:
        doc = load_api_doc(result.api_name)
        markdown = format_api_doc(doc, result)

Public API:
    - search_api(): Smart search with automatic strategy selection
    - load_api_doc(): Load documentation for specific API
    - format_api_signature(): Format brief one-liner signature
    - format_api_doc(): Format complete documentation as markdown

Data Models:
    - SearchResult: Search result with score and metadata
    - APIDocumentation: Structured API documentation
"""

from typing import List, Dict, Any, Optional

from backend.infrastructure.pfc.sdk.searcher import APISearcher
from backend.infrastructure.pfc.sdk.formatter import APIDocFormatter
from backend.infrastructure.pfc.sdk.loader import DocumentationLoader
from backend.infrastructure.pfc.sdk.models import SearchResult, APIDocumentation, SearchStrategy


# Singleton instances for performance
# These are created once and reused across all calls
_searcher = APISearcher()


def search_api(query: str, top_n: int = 3) -> List[SearchResult]:
    """Smart API search with automatic strategy selection.

    This is the main search entry point. It automatically selects
    the appropriate search strategy based on the query format:
    - Queries with dots (.) use path matching
    - Other queries use keyword matching

    Args:
        query: API path or natural language query
               Examples:
               - "itasca.ball.create" (path)
               - "BallBallContact.gap" (path with Contact type)
               - "create ball" (natural language)
               - "measure count" (natural language)
        top_n: Maximum number of results to return (default: 3)

    Returns:
        List of SearchResult objects sorted by score (highest first)
        Empty list if no matches found

    Example:
        >>> results = search_api("create ball")
        >>> results[0].api_name
        "itasca.ball.create"
        >>> results[0].score
        2

        >>> results = search_api("BallBallContact.gap")
        >>> results[0].api_name
        "Contact.gap"
        >>> results[0].metadata["contact_type"]
        "BallBallContact"
    """
    return _searcher.search(query, top_n)


def load_api_doc(api_name: str) -> Optional[Dict[str, Any]]:
    """Load documentation for a specific API.

    Args:
        api_name: Full API name (e.g., "itasca.ball.create", "Ball.vel")

    Returns:
        Documentation dict with fields:
        - signature: Function signature
        - description: Detailed description
        - parameters: List of parameter definitions
        - returns: Return value information
        - examples: Usage examples
        - limitations: Known limitations (optional)
        - fallback_commands: Alternative commands (optional)
        - best_practices: Recommended practices (optional)
        - notes: Additional notes (optional)
        - see_also: Related APIs (optional)

        Returns None if API not found

    Example:
        >>> doc = load_api_doc("itasca.ball.create")
        >>> doc["signature"]
        "itasca.ball.create(radius, pos=None)"
        >>> doc["parameters"]
        [{"name": "radius", "type": "float", "required": True, ...}]
    """
    return DocumentationLoader.load_api_doc(api_name)


def format_api_signature(api_name: str) -> Optional[str]:
    """Format brief API signature for quick reference.

    Args:
        api_name: Full API name (e.g., "itasca.ball.create")

    Returns:
        Brief signature string with return type and description
        Format: "`signature` -> return_type - brief description"
        Returns None if API not found

    Example:
        >>> sig = format_api_signature("Ball.vel")
        >>> print(sig)
        `Ball.vel() -> tuple[float, float, float]` - Get ball velocity vector
    """
    return APIDocFormatter.format_signature(api_name)


def format_api_doc(api_doc: Dict[str, Any], result: SearchResult) -> str:
    """Format complete API documentation as LLM-friendly markdown.

    Args:
        api_doc: Documentation dict from load_api_doc()
        result: SearchResult with api_name and metadata

    Returns:
        Formatted markdown string with sections:
        - Official API path
        - Signature
        - Description
        - Parameters
        - Returns
        - Examples
        - Limitations
        - Best practices
        - Notes
        - See also

    Example:
        >>> results = search_api("BallBallContact.gap")
        >>> doc = load_api_doc(results[0].api_name)
        >>> markdown = format_api_doc(doc, results[0])
        >>> print(markdown)
        # itasca.BallBallContact.gap

        **Available for**: BallBallContact, BallFacetContact, ...

        **Signature**: `contact.gap() -> float`
        ...
    """
    return APIDocFormatter.format_full_doc(api_doc, result)


# Public API exports
__all__ = [
    # Main functions
    "search_api",
    "load_api_doc",
    "format_api_signature",
    "format_api_doc",
    # Data models
    "SearchResult",
    "APIDocumentation",
    "SearchStrategy"
]
