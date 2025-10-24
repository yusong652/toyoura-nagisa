"""High-level Python API search interface.

This module provides a simple, user-friendly API for searching PFC Python SDK
documentation, abstracting away the complexity of search engines.
"""

from typing import List, Optional, Dict, Any
from backend.infrastructure.pfc.shared.models.document import DocumentType
from backend.infrastructure.pfc.shared.models.search_result import SearchResult
from backend.infrastructure.pfc.shared.adapters.api_adapter import APIDocumentAdapter
from backend.infrastructure.pfc.shared.search.engines.bm25_engine import BM25SearchEngine


class APISearch:
    """Python SDK API search interface.

    This class provides a high-level API for searching PFC Python SDK
    documentation using BM25 algorithm with keyword boosting.

    Search Scope:
    - Module functions: itasca.ball.create, itasca.wall.create, etc.
    - Object methods: itasca.ball.Ball.vel, itasca.wall.Wall.pos, etc.
    - Contact types: itasca.BallBallContact.gap, itasca.BallFacetContact.gap, etc.
    - All 1006 API documents in unified index

    Features:
    - Unified search for all API types (functions + methods)
    - Automatic index initialization (lazy loading)
    - Singleton pattern for efficient memory usage
    - Contact type expansion (Contact.gap → all 5 specific types)
    - Object method expansion (Ball.vel → itasca.ball.Ball.vel)
    - Abbreviation support (pos → position)

    Design Decisions:
    - BM25 with keyword boost (KEYWORD_BOOST=3.0) for quality results
    - Single search() method handles all API types
    - Category filter for module-specific searches
    - Thread-safe singleton pattern

    Usage:
        >>> # Basic search (works for all API types)
        >>> results = APISearch.search("ball create", top_k=5)
        >>> results[0].document.title
        "itasca.ball.create"

        >>> # Search object methods
        >>> results = APISearch.search("Ball.vel", top_k=5)
        >>> results[0].document.title
        "itasca.ball.Ball.vel"

        >>> # Search Contact types
        >>> results = APISearch.search("contact gap", top_k=5)
        >>> any("Contact" in r.document.title for r in results)
        True

        >>> # With category filter
        >>> results = APISearch.search(
        ...     "position",
        ...     top_k=10,
        ...     category="ball"
        ... )

        >>> # Search abbreviations (partial matching)
        >>> results = APISearch.search("pos")  # Matches "position"
    """

    # Singleton instance
    _engine: Optional[BM25SearchEngine] = None

    @classmethod
    def _get_engine(cls) -> BM25SearchEngine:
        """Get or create BM25 search engine (singleton pattern).

        Returns:
            BM25SearchEngine instance (shared across all calls)

        Example:
            >>> engine = APISearch._get_engine()
            >>> engine.is_built()
            True
        """
        if cls._engine is None:
            cls._engine = BM25SearchEngine(
                document_loader=APIDocumentAdapter.load_all,
                keyword_boost=3.0  # Optimal balance based on testing
            )
            cls._engine.build()

        return cls._engine

    @classmethod
    def search(
        cls,
        query: str,
        top_k: int = 10,
        category: Optional[str] = None,
        min_score: Optional[float] = None
    ) -> List[SearchResult]:
        """Search for Python SDK APIs.

        This is the main entry point for API search. It uses BM25 algorithm
        with keyword boosting for high-quality results.

        Args:
            query: Search query string
                  Examples: "ball create", "Ball.vel", "contact gap", "pos"
            top_k: Maximum number of results to return (default: 10)
            category: Optional category filter
                     Examples: "ball", "wall", "contact"
            min_score: Optional minimum score threshold

        Returns:
            List of SearchResult objects sorted by score (highest first)
            Empty list if no matches found

        Example:
            >>> # Basic search
            >>> results = APISearch.search("ball position")
            >>> len(results)
            3
            >>> results[0].document.title
            "itasca.ball.Ball.pos"

            >>> # Filter by category
            >>> results = APISearch.search(
            ...     "velocity",
            ...     category="ball"
            ... )
            >>> results[0].document.category
            "ball"

            >>> # Abbreviation matching
            >>> results = APISearch.search("vel")
            >>> "velocity" in results[0].document.description.lower()
            True

            >>> # Contact type search
            >>> results = APISearch.search("contact gap")
            >>> any("Contact" in r.document.title for r in results)
            True

            >>> # With minimum score
            >>> results = APISearch.search(
            ...     "create",
            ...     min_score=10.0
            ... )
        """
        # Get singleton engine
        engine = cls._get_engine()

        # Build filter dictionary
        filters: Dict[str, Any] = {}

        if category is not None:
            filters["category"] = category

        if min_score is not None:
            filters["min_score"] = min_score

        # Execute search
        results = engine.search(
            query=query,
            top_k=top_k,
            filters=filters if filters else None
        )

        return results

    @classmethod
    def rebuild_index(cls) -> None:
        """Rebuild search index from scratch.

        Use this when:
        - Documentation files have been updated
        - Index parameters need to be changed
        - Troubleshooting index issues

        Example:
            >>> APISearch.rebuild_index()
        """
        if cls._engine is not None:
            cls._engine.rebuild()

    @classmethod
    def get_index_stats(cls) -> Dict[str, Any]:
        """Get search index statistics.

        Returns:
            Dictionary with index statistics:
            - doc_count: Number of indexed documents (1006 APIs)
            - avg_doc_len: Average document length
            - vocab_size: Vocabulary size
            - total_terms: Total terms in index
            - keyword_boost: Current keyword boost factor

        Example:
            >>> stats = APISearch.get_index_stats()
            >>> stats['doc_count']
            1006  # All Python SDK APIs
        """
        engine = cls._get_engine()
        return engine.get_index_stats()
