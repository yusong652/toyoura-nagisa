"""High-level Python API search interface.

This module provides a simple, user-friendly API for searching PFC Python SDK
documentation, abstracting away the complexity of search engines.

Supports two search modes:
1. Path-based search: Exact API path matching (e.g., "Ball.vel", "BallBallContact.gap")
2. BM25 search: Natural language queries (e.g., "ball velocity", "contact force")

The system automatically detects query type and routes to appropriate search strategy.
"""

import re
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

    # Singleton instances
    _engine: Optional[BM25SearchEngine] = None
    _path_strategy = None  # Lazy loaded PathSearchStrategy

    # Contact type definitions (abstract Contact → concrete types)
    CONTACT_TYPES = [
        'BallBallContact',
        'BallFacetContact',
        'BallPebbleContact',
        'PebblePebbleContact',
        'PebbleFacetContact'
    ]

    @classmethod
    def _is_path_query(cls, query: str) -> bool:
        """Detect if query is an API path pattern.

        Path query characteristics:
        - Contains dot notation (e.g., "Ball.vel", "ball.Ball.pos", "clump.pos_z")
        - Follows API naming conventions (object.method pattern)
        - Not a natural language phrase or version number

        Examples of path queries:
        - "Ball.vel" → True (Class.method)
        - "ball.Ball.vel" → True (module.Class.method)
        - "BallBallContact.gap" → True (ContactType.method)
        - "clump.pos_z" → True (lowercase object.method)
        - "ball velocity" → False (natural language, no dot)
        - "3.14" → False (number)
        - "PFC 7.0" → False (version number)

        Args:
            query: User query string

        Returns:
            True if query looks like an API path, False otherwise
        """
        query = query.strip()

        # Must contain dot notation
        if '.' not in query:
            return False

        # Exclude pure numbers (version numbers, floating point)
        if re.match(r'^\d+\.[\d.]+$', query):
            return False

        # API path patterns:
        # 1. Class.method: Ball.vel, Wall.pos, Clump.pos_z
        # 2. module.Class.method: ball.Ball.vel, wall.Wall.pos
        # 3. ContactType.method: BallBallContact.gap, BallFacetContact.force_global
        # 4. Lowercase object.method: clump.pos_z, ball.vel (user shorthand)
        # 5. Full path: itasca.ball.Ball.vel

        # Relaxed pattern: accepts both capitalized and lowercase object names
        # Format: word.word or word.Word.word (with optional prefix)
        api_path_pattern = r'^([a-z]+\.)?[A-Za-z][a-zA-Z]*\.[a-z_]+$|^[a-z]+\.[A-Za-z][a-zA-Z]*\.[a-z_]+$'

        return bool(re.match(api_path_pattern, query))

    @classmethod
    def _is_contact_query(cls, query: str) -> bool:
        """Check if query uses abstract 'Contact' type.

        Examples:
            - "Contact.force_y" → True
            - "Contact.gap" → True
            - "BallBallContact.gap" → False (concrete type)
            - "ball contact" → False (not path query)

        Args:
            query: User query string

        Returns:
            True if query starts with "Contact.", False otherwise
        """
        return query.strip().startswith("Contact.")

    @classmethod
    def _expand_contact_query(cls, query: str, top_n: int) -> List[SearchResult]:
        """Expand abstract Contact query to all concrete contact types.

        Transforms "Contact.force_y" into searches for:
        - BallBallContact.force_y
        - BallFacetContact.force_y
        - BallPebbleContact.force_y
        - PebblePebbleContact.force_y
        - PebbleFacetContact.force_y

        Then aggregates and deduplicates results.

        Args:
            query: Original query (e.g., "Contact.force_y")
            top_n: Maximum results to return

        Returns:
            List of SearchResult objects from all contact types

        Example:
            >>> results = APISearch._expand_contact_query("Contact.gap", 5)
            >>> results[0].document.name
            "itasca.BallBallContact.gap"
        """
        # Extract method name from "Contact.method"
        method_name = query.split('.', 1)[1]

        path_strategy = cls._get_path_strategy()
        all_results = []

        # Search each concrete contact type
        for contact_type in cls.CONTACT_TYPES:
            concrete_query = f"{contact_type}.{method_name}"
            results = path_strategy.search(concrete_query, top_n=top_n)

            if results:
                # Convert to new format
                converted = cls._convert_old_to_new_format(results)
                all_results.extend(converted)

        # Deduplicate by document ID
        seen_ids = set()
        unique_results = []
        for result in all_results:
            if result.document.name not in seen_ids:
                seen_ids.add(result.document.name)
                unique_results.append(result)

        # Sort by score (descending) and return top_n
        unique_results.sort(key=lambda r: r.score, reverse=True)
        return unique_results[:top_n]

    @classmethod
    def _get_path_strategy(cls):
        """Get or create PathSearchStrategy (lazy loading).

        Returns:
            PathSearchStrategy instance

        Example:
            >>> strategy = APISearch._get_path_strategy()
            >>> strategy.can_handle("Ball.vel")
            True
        """
        if cls._path_strategy is None:
            from backend.infrastructure.pfc.python_api.search.path_search import PathSearchStrategy
            cls._path_strategy = PathSearchStrategy()

        return cls._path_strategy

    @classmethod
    def _convert_old_to_new_format(cls, old_results: List) -> List[SearchResult]:
        """Convert old SearchResult format to new SearchResult format.

        Old format (from PathSearchStrategy):
        - SearchResult with fields: name, score, doc_type, category, strategy, metadata

        New format (BM25 SearchResult):
        - SearchResult with fields: document, score, match_info, rank

        Args:
            old_results: List of old-format SearchResult objects

        Returns:
            List of new-format SearchResult objects
        """
        from backend.infrastructure.pfc.shared.models.document import SearchDocument

        new_results = []
        for rank, old_result in enumerate(old_results, start=1):
            # Load full document
            doc = APIDocumentAdapter.load_by_id(old_result.name)
            if not doc:
                continue

            # Preserve metadata from old result (especially for Contact types)
            if old_result.metadata:
                if not doc.metadata:
                    doc.metadata = {}
                doc.metadata.update(old_result.metadata)

            # Create new SearchResult
            new_result = SearchResult(
                document=doc,
                score=float(old_result.score),
                match_info={'strategy': 'path', 'original_metadata': old_result.metadata},
                rank=rank
            )
            new_results.append(new_result)

        return new_results

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
        """Search for Python SDK APIs with automatic mode detection.

        This method automatically detects the query type and routes to the
        appropriate search strategy:
        - Path queries (e.g., "Ball.vel") → PathSearchStrategy (exact matching)
        - Natural language (e.g., "ball velocity") → BM25 (semantic matching)

        Args:
            query: Search query string
                  Path examples: "Ball.vel", "BallBallContact.gap", "ball.Ball.pos"
                  Natural examples: "ball create", "contact gap", "ball velocity"
            top_k: Maximum number of results to return (default: 10)
            category: Optional category filter
                     Examples: "ball", "wall", "contact"
            min_score: Optional minimum score threshold

        Returns:
            List of SearchResult objects sorted by score (highest first)
            Empty list if no matches found

        Example:
            >>> # Path query (automatic detection)
            >>> results = APISearch.search("Ball.vel")
            >>> results[0].document.name
            "itasca.ball.Ball.vel"
            >>> results[0].score
            999.0  # High score from path matching

            >>> # Natural language query
            >>> results = APISearch.search("ball position")
            >>> results[0].document.name
            "itasca.ball.Ball.pos"
            >>> results[0].score
            10.0  # BM25 score

            >>> # Contact type path query
            >>> results = APISearch.search("BallBallContact.gap")
            >>> results[0].document.metadata.get("contact_type")
            "BallBallContact"

            >>> # With filters
            >>> results = APISearch.search(
            ...     "velocity",
            ...     category="ball",
            ...     min_score=8.0
            ... )
        """
        # ===== Step 1: Contact Type Expansion =====
        # Handle abstract "Contact" queries by expanding to all concrete types
        if cls._is_contact_query(query):
            contact_results = cls._expand_contact_query(query, top_n=top_k)
            if contact_results:
                # Contact expansion successful, return results
                return contact_results
            # No results from expansion, fall through to BM25

        # ===== Step 2: Path Query Detection =====
        if cls._is_path_query(query):
            # Use path-based search for exact API path matching
            path_strategy = cls._get_path_strategy()
            old_format_results = path_strategy.search(query, top_n=top_k)

            if old_format_results:
                # Convert to new format
                path_results = cls._convert_old_to_new_format(old_format_results)

                # Check if path match is high confidence (score >= 850)
                # 999 = exact match, 850 = partial match
                if path_results and path_results[0].score >= 850:
                    # High confidence path match, return immediately
                    return path_results[:top_k]

                # Low confidence path match, fall through to BM25

        # ===== Step 3: BM25 Search (fallback or primary) =====
        engine = cls._get_engine()

        # Build filter dictionary
        filters: Dict[str, Any] = {}

        if category is not None:
            filters["category"] = category

        if min_score is not None:
            filters["min_score"] = min_score

        # Execute BM25 search
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
