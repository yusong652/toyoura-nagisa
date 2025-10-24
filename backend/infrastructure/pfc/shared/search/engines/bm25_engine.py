"""BM25-based search engine for PFC documentation.

This module implements a complete search engine using BM25 algorithm with
keyword boosting, providing a high-level interface for document search.
"""

from typing import List, Dict, Any, Optional, Callable
from backend.infrastructure.pfc.shared.models.document import SearchDocument
from backend.infrastructure.pfc.shared.models.search_result import SearchResult
from backend.infrastructure.pfc.shared.search.engines.base_engine import BaseSearchEngine
from backend.infrastructure.pfc.shared.search.indexing.bm25_indexer import BM25Indexer
from backend.infrastructure.pfc.shared.search.scoring.bm25_scorer import BM25Scorer


class BM25SearchEngine(BaseSearchEngine):
    """BM25 search engine with keyword boosting.

    This engine provides a complete search solution using BM25 algorithm:
    - Automatic index building on first query
    - Keyword boost for curated terms (default: 3.0x)
    - Partial matching support (abbreviations)
    - Multi-field indexing (description + boosted keywords)

    Features:
    - Pure Python implementation (no NumPy dependency)
    - Optimized for ~200 documents (commands + APIs)
    - Fast indexing (<100ms) and query (<10ms)
    - Automatic result ranking and filtering

    Algorithm Details:
    - BM25 parameters: K1=1.5, B=0.75
    - KEYWORD_BOOST: 3.0 (tunable, range: 2.0-5.0)
    - IDF formula: Robertson-Spärck Jones
    - Saturation prevents keyword stuffing

    Usage:
        >>> from backend.infrastructure.pfc.shared.adapters.command_adapter import CommandDocumentAdapter
        >>> engine = BM25SearchEngine(document_loader=CommandDocumentAdapter.load_all)
        >>> engine.build()
        >>> results = engine.search("ball porosity", top_k=5)
        >>> for result in results:
        ...     print(f"{result.document.title}: {result.score:.3f}")
    """

    def __init__(
        self,
        document_loader: Callable[[], List[SearchDocument]],
        keyword_boost: float = 3.0
    ):
        """Initialize BM25 search engine.

        Args:
            document_loader: Callable that returns list of SearchDocument objects
            keyword_boost: Keyword boost factor (default: 3.0, range: 2.0-5.0)
                          Higher values give more weight to curated keywords

        Example:
            >>> engine = BM25SearchEngine(
            ...     document_loader=CommandDocumentAdapter.load_all,
            ...     keyword_boost=5.0  # Boost keyword importance
            ... )
        """
        super().__init__(document_loader)
        self.indexer = BM25Indexer()
        self.indexer.KEYWORD_BOOST = keyword_boost
        self.scorer: Optional[BM25Scorer] = None

    def build(self) -> None:
        """Build BM25 index from loaded documents.

        This method:
        1. Loads documents using document_loader()
        2. Builds BM25 inverted index with keyword boosting
        3. Creates BM25 scorer with partial matching support

        Raises:
            Exception: If document loading or indexing fails

        Example:
            >>> engine.build()
            >>> stats = engine.indexer.get_stats()
            >>> stats['doc_count']
            120
            >>> stats['keyword_boost']
            3.0
        """
        # Load documents
        self.documents = self.document_loader()

        if not self.documents:
            raise ValueError("Document loader returned empty list")

        # Build BM25 index
        self.indexer.build(self.documents)

        # Create scorer
        self.scorer = BM25Scorer(self.indexer)

        # Mark as built
        self._is_built = True

    def search(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[SearchResult]:
        """Execute BM25 search with optional filtering.

        Args:
            query: Search query string
                  Examples: "ball porosity", "contact gap", "pos"
            top_k: Maximum number of results to return (default: 10)
            filters: Optional filters:
                    - doc_type: Filter by DocumentType
                    - category: Filter by category
                    - min_score: Minimum score threshold

        Returns:
            List of SearchResult objects sorted by score (highest first)

        Raises:
            ValueError: If engine not built (call build() first)

        Example:
            >>> engine.build()
            >>> results = engine.search("ball create", top_k=5)
            >>> results[0].document.title
            "ball create"
            >>> results[0].score
            15.234

            >>> # With filters
            >>> results = engine.search(
            ...     "contact",
            ...     top_k=10,
            ...     filters={"doc_type": "command", "min_score": 5.0}
            ... )
        """
        # Auto-build on first query
        if not self._is_built:
            self.build()

        # Validate query
        query = query.strip()
        if not query:
            return []

        # Score all documents using BM25
        scored_results = self.scorer.batch_score(query, self.documents)

        # Convert to SearchResult objects with ranks
        search_results = []
        for rank, (document, score, match_info) in enumerate(scored_results, start=1):
            search_results.append(SearchResult(
                document=document,
                score=score,
                match_info=match_info,
                rank=rank
            ))

        # Apply filters if provided
        if filters:
            search_results = self._apply_filters(search_results, filters)

        # Sort by score (descending) and return top_k
        search_results.sort(key=lambda r: r.score, reverse=True)

        return search_results[:top_k]

    def get_index_stats(self) -> Dict[str, Any]:
        """Get BM25 index statistics.

        Returns:
            Dictionary with index statistics:
            - doc_count: Number of indexed documents
            - avg_doc_len: Average document length (tokens)
            - vocab_size: Vocabulary size (unique terms)
            - total_terms: Total terms in index
            - keyword_boost: Current keyword boost factor

        Raises:
            ValueError: If engine not built

        Example:
            >>> engine.build()
            >>> stats = engine.get_index_stats()
            >>> stats
            {
                'doc_count': 120,
                'avg_doc_len': 49.09,
                'vocab_size': 1159,
                'total_terms': 5891,
                'keyword_boost': 3.0
            }
        """
        if not self._is_built:
            raise ValueError("Engine not built. Call build() first.")

        return self.indexer.get_stats()

    def set_keyword_boost(self, boost: float) -> None:
        """Update keyword boost factor and rebuild index.

        Args:
            boost: New keyword boost factor (recommended: 2.0-5.0)

        Example:
            >>> engine.set_keyword_boost(5.0)  # Stronger keyword weighting
            >>> engine.search("packing")  # Re-indexed with new boost
        """
        self.indexer.KEYWORD_BOOST = boost
        self.rebuild()
