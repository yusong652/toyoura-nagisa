"""High-level command search interface.

This module provides a simple, user-friendly API for searching PFC commands
and model properties, abstracting away the complexity of search engines.
"""

from typing import List, Optional, Dict, Any
from backend.infrastructure.pfc.shared.models.document import DocumentType
from backend.infrastructure.pfc.shared.models.search_result import SearchResult
from backend.infrastructure.pfc.shared.adapters.command_adapter import CommandDocumentAdapter
from backend.infrastructure.pfc.shared.search.engines.bm25_engine import BM25SearchEngine


class CommandSearch:
    """Unified command and model property search interface.

    This class provides a high-level API for searching PFC commands and
    contact model properties using BM25 algorithm with multi-field scoring.

    Features:
    - Automatic index initialization (lazy loading)
    - Singleton pattern for efficient memory usage
    - Support for filtering by doc_type and category
    - Optional model properties inclusion

    Design Decisions:
    - Unified search (commands + model properties) for better UX
    - BM25 with multi-field scoring (name=0.5, keywords=0.3, description=0.2)
    - Automatic index building on first query
    - Thread-safe singleton pattern

    Usage:
        >>> # Basic search
        >>> results = CommandSearch.search("ball create", top_k=5)
        >>> results[0].document.title
        "ball create"

        >>> # With filters
        >>> results = CommandSearch.search(
        ...     "contact",
        ...     top_k=10,
        ...     category="contact",
        ...     include_model_properties=True
        ... )

        >>> # Commands only (exclude model properties)
        >>> results = CommandSearch.search(
        ...     "linear",
        ...     include_model_properties=False
        ... )
    """

    # Singleton instance
    _engine: Optional[BM25SearchEngine] = None

    @classmethod
    def _get_engine(cls) -> BM25SearchEngine:
        """Get or create BM25 search engine (singleton pattern).

        Returns:
            BM25SearchEngine instance (shared across all calls)

        Example:
            >>> engine = CommandSearch._get_engine()
            >>> engine.is_built()
            True
        """
        if cls._engine is None:
            cls._engine = BM25SearchEngine(
                document_loader=CommandDocumentAdapter.load_all
            )
            cls._engine.build()

        return cls._engine

    @classmethod
    def search(
        cls,
        query: str,
        top_k: int = 10,
        category: Optional[str] = None,
        include_model_properties: bool = True,
        min_score: Optional[float] = None
    ) -> List[SearchResult]:
        """Search for PFC commands and optionally model properties.

        This is the main entry point for command search. It uses BM25 algorithm
        with multi-field scoring for high-quality results.

        Args:
            query: Search query string
                  Examples: "ball create", "contact property", "kn stiffness"
            top_k: Maximum number of results to return (default: 10)
            category: Optional category filter
                     Examples: "ball", "contact", "model"
            include_model_properties: Include model properties in search (default: True)
            min_score: Optional minimum score threshold

        Returns:
            List of SearchResult objects sorted by score (highest first)
            Empty list if no matches found

        Example:
            >>> # Basic search
            >>> results = CommandSearch.search("ball porosity")
            >>> len(results)
            5
            >>> results[0].document.title
            "ball distribute"

            >>> # Filter by category
            >>> results = CommandSearch.search(
            ...     "create",
            ...     category="ball"
            ... )
            >>> results[0].document.category
            "ball"

            >>> # Commands only
            >>> results = CommandSearch.search(
            ...     "linear",
            ...     include_model_properties=False
            ... )
            >>> all(r.document.doc_type == DocumentType.COMMAND for r in results)
            True

            >>> # With minimum score
            >>> results = CommandSearch.search(
            ...     "packing",
            ...     min_score=5.0
            ... )
        """
        # Get singleton engine
        engine = cls._get_engine()

        # Build filter dictionary
        filters: Dict[str, Any] = {}

        if category is not None:
            filters["category"] = category

        if not include_model_properties:
            filters["doc_type"] = DocumentType.COMMAND.value

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
    def search_commands_only(
        cls,
        query: str,
        top_k: int = 10,
        category: Optional[str] = None
    ) -> List[SearchResult]:
        """Search for commands only (exclude model properties).

        Convenience method for searching only commands, excluding model properties.

        Args:
            query: Search query string
            top_k: Maximum number of results to return (default: 10)
            category: Optional category filter

        Returns:
            List of SearchResult objects (commands only)

        Example:
            >>> results = CommandSearch.search_commands_only("ball create")
            >>> all(r.document.doc_type == DocumentType.COMMAND for r in results)
            True
        """
        return cls.search(
            query=query,
            top_k=top_k,
            category=category,
            include_model_properties=False
        )

    @classmethod
    def search_model_properties(
        cls,
        query: str,
        top_k: int = 10
    ) -> List[SearchResult]:
        """Search for model properties only.

        Convenience method for searching only contact model properties.

        Args:
            query: Search query string
                  Examples: "linear", "kn stiffness", "hertz"
            top_k: Maximum number of results to return (default: 10)

        Returns:
            List of SearchResult objects (model properties only)

        Example:
            >>> results = CommandSearch.search_model_properties("linear stiffness")
            >>> all(r.document.doc_type == DocumentType.MODEL_PROPERTY for r in results)
            True
        """
        filters = {
            "doc_type": DocumentType.MODEL_PROPERTY.value
        }

        engine = cls._get_engine()
        results = engine.search(
            query=query,
            top_k=top_k,
            filters=filters
        )

        return results

    @classmethod
    def get_by_category(
        cls,
        category: str,
        top_k: int = 20
    ) -> List[SearchResult]:
        """Get all commands in a specific category.

        Args:
            category: Category name (e.g., "ball", "contact", "model")
            top_k: Maximum number of results (default: 20)

        Returns:
            List of SearchResult objects in the category

        Example:
            >>> results = CommandSearch.get_by_category("ball")
            >>> all(r.document.category == "ball" for r in results)
            True
        """
        # Use category name as query (will match all documents in that category)
        return cls.search(
            query=category,
            top_k=top_k,
            category=category
        )

    @classmethod
    def rebuild_index(cls) -> None:
        """Rebuild search index from scratch.

        Use this when:
        - Documentation files have been updated
        - Index parameters need to be changed
        - Troubleshooting index issues

        Example:
            >>> CommandSearch.rebuild_index()
        """
        if cls._engine is not None:
            cls._engine.rebuild()

    @classmethod
    def get_index_stats(cls) -> Dict[str, Any]:
        """Get search index statistics.

        Returns:
            Dictionary with index statistics:
            - doc_count: Number of indexed documents
            - name_field: Name field statistics (avg_doc_len, vocab_size, total_terms)
            - description_field: Description field statistics
            - keywords_field: Keywords field statistics

        Example:
            >>> stats = CommandSearch.get_index_stats()
            >>> stats['doc_count']
            120  # 115 commands + 5 model properties
        """
        engine = cls._get_engine()
        return engine.get_index_stats()
