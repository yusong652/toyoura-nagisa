"""High-level Python API search interface.

This module provides a simple, user-friendly API for searching PFC Python SDK
documentation using BM25 algorithm with keyword boosting.

Features:
- Natural language queries (e.g., "ball velocity", "contact force")
- API path queries (e.g., "Ball.vel", "BallBallContact.gap") via tokenization
- Automatic index initialization (lazy loading)
- Abbreviation support through partial matching
"""

from typing import List, Optional, Dict, Any
from backend.infrastructure.pfc.shared.models.document import DocumentType
from backend.infrastructure.pfc.shared.models.search_result import SearchResult
from backend.infrastructure.pfc.shared.adapters.api_adapter import APIDocumentAdapter
from backend.infrastructure.pfc.shared.search.engines.bm25_engine import BM25SearchEngine
from backend.infrastructure.pfc.shared.search.postprocessing import (
    consolidate_contact_apis,
    consolidate_component_apis
)


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
    - Unified BM25 search for all API types
    - Automatic index initialization (lazy loading)
    - Singleton pattern for efficient memory usage
    - Smart tokenization handles API paths (Ball.vel → ["ball", "vel"])
    - Abbreviation support through partial matching (pos → position)
    - Name boosting for better path matching

    Design Decisions:
    - BM25 with keyword boost (KEYWORD_BOOST=3.0) for quality results
    - BM25 with name boost (NAME_BOOST=2.0) for path queries
    - Single search() method handles all query types
    - Category filter for module-specific searches
    - Thread-safe singleton pattern

    Usage:
        >>> # Natural language search
        >>> results = APISearch.search("ball create", top_k=5)
        >>> results[0].document.title
        "itasca.ball.create"

        >>> # API path search (handled by tokenizer + name boost)
        >>> results = APISearch.search("Ball.vel", top_k=5)
        >>> results[0].document.title
        "itasca.ball.Ball.vel"

        >>> # Contact type search
        >>> results = APISearch.search("contact gap", top_k=5)
        >>> any("Contact" in r.document.title for r in results)
        True

        >>> # With category filter
        >>> results = APISearch.search(
        ...     "position",
        ...     top_k=10,
        ...     category="ball"
        ... )

        >>> # Abbreviations (partial matching)
        >>> results = APISearch.search("pos")  # Matches "position"
    """

    # Singleton BM25 engine instance
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
                document_loader=APIDocumentAdapter.load_all
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
        """Search for Python SDK APIs using BM25 algorithm.

        This method uses BM25 with smart tokenization to handle both
        natural language queries and API path queries:
        - Natural language: "ball velocity", "contact gap"
        - API paths: "Ball.vel", "BallBallContact.gap" (tokenized by dots/underscores)

        Args:
            query: Search query string
                  Examples: "ball create", "Ball.vel", "contact gap", "position"
            top_k: Maximum number of results to return (default: 10)
            category: Optional category filter
                     Examples: "ball", "wall", "contact"
            min_score: Optional minimum score threshold

        Returns:
            List of SearchResult objects sorted by score (highest first)
            Empty list if no matches found

        Example:
            >>> # Natural language query
            >>> results = APISearch.search("ball position")
            >>> results[0].document.name
            "itasca.ball.Ball.pos"

            >>> # API path query (handled by tokenizer)
            >>> results = APISearch.search("Ball.vel")
            >>> results[0].document.name
            "itasca.ball.Ball.vel"

            >>> # Contact type query
            >>> results = APISearch.search("BallBallContact.gap")
            >>> "Contact" in results[0].document.name
            True

            >>> # With filters
            >>> results = APISearch.search(
            ...     "velocity",
            ...     category="ball",
            ...     min_score=5.0
            ... )
        """
        # Get BM25 engine (lazy initialization)
        engine = cls._get_engine()

        # Build filter dictionary
        filters: Dict[str, Any] = {}

        if category is not None:
            filters["category"] = category

        if min_score is not None:
            filters["min_score"] = min_score

        # Execute BM25 search with over-fetching to account for Contact API consolidation
        # Contact API consolidation can reduce result count significantly (5 types → 1 result)
        # Strategy: Fetch 3x top_k results, consolidate, then return top_k
        # This balances performance (single search call) with accuracy (enough unique results)

        # Calculate search limit: 3x for Contact consolidation, capped at 100
        search_limit = min(top_k * 3, 100)

        results = engine.search(
            query=query,
            top_k=search_limit,
            filters=filters if filters else None
        )

        # Consolidate Contact API duplicates
        # This reduces redundancy (e.g., BallBallContact.gap, BallFacetContact.gap → single result)
        # while preserving type information in metadata['all_contact_types']
        consolidated = consolidate_contact_apis(results)

        # Consolidate component APIs (_x, _y, _z variants)
        # This reduces redundancy (e.g., force_global, force_global_x/y/z → single result)
        # while preserving component information in metadata['has_components']
        consolidated = consolidate_component_apis(consolidated)

        # Return final top_k results after consolidation
        return consolidated[:top_k]

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
