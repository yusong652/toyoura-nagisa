"""BM25 inverted index builder for PFC search system.

This module implements BM25 indexing using only Python standard library
(no NumPy dependency), optimized for technical documentation search.
"""

import math
from collections import Counter
from typing import List, Dict, Set
from backend.infrastructure.pfc.shared.models.document import SearchDocument
from backend.infrastructure.pfc.shared.search.preprocessing.tokenizer import TextTokenizer


class BM25Indexer:
    """BM25 inverted index builder with keyword boosting.

    Builds and maintains BM25 index structures for efficient scoring:
    - Document tokens (name + title + description + boosted keywords)
    - Term frequencies per document
    - Document frequencies per term
    - Average document length

    Indexing Strategy:
    - Document name (API paths, command names) → Tokenized, boosted, and indexed
    - Title (if different from name) → Tokenized and indexed
    - Description (main content) → Tokenized and indexed
    - Keywords (curated terms) → Tokenized, boosted, and indexed

    Name Boosting:
    - Name field receives higher weight for exact path matching
    - Controlled by NAME_BOOST parameter (default: 2.0)
    - Ensures "Ball.vel" ranks higher than "Ball.vel_y"
    - Name tokens repeated N times to increase term frequency

    Keyword Boosting:
    - Keywords field receives higher weight than description
    - Controlled by KEYWORD_BOOST parameter (default: 3.0)
    - Keywords tokens are repeated N times to increase term frequency
    - BM25 saturation prevents over-amplification

    Path-Based Search:
    - With improved tokenizer, API paths are split properly
    - "itasca.ball.Ball.vel" → ["itasca", "ball", "ball", "vel"]
    - Enables partial path matching: "Ball.vel" matches "itasca.ball.Ball.vel"

    Design:
    - Pure Python implementation (no NumPy)
    - Optimized for ~1000 documents (commands + APIs)
    - Supports incremental updates

    Usage:
        >>> indexer = BM25Indexer()
        >>> indexer.build(documents)
        >>> idf = indexer.get_idf("porosity")
        >>> idf
        2.345  # Example IDF value

        >>> # Adjust keyword boost
        >>> indexer.KEYWORD_BOOST = 5.0
        >>> indexer.build(documents)  # Rebuild with new boost
    """

    # Name boost factor (tunable parameter)
    # Higher values prioritize exact name/path matches
    # Recommended range: 2.0-5.0, default: 4.0
    # Should be > KEYWORD_BOOST to ensure name matching takes priority
    # Example: "BallBallContact" should rank higher than "Ball" with contact keywords
    NAME_BOOST = 4.0

    # Keyword boost factor (tunable parameter)
    # Higher values give more weight to curated keywords
    # Recommended range: 1.0-3.0, default: 2.0
    # Note: Too high values can cause length penalty issues
    # (documents with many keywords become too long and get penalized)
    KEYWORD_BOOST = 2.0

    def __init__(self):
        """Initialize empty BM25 index."""
        self.documents: Dict[str, List[str]] = {}  # doc_id → tokens
        self.doc_count: int = 0
        self.avg_doc_len: float = 0.0
        self.term_doc_freq: Dict[str, int] = {}  # term → document frequency
        self.term_freq: Dict[str, Dict[str, int]] = {}  # doc_id → {term → count}
        self.tokenizer = TextTokenizer()

    def build(self, documents: List[SearchDocument]) -> None:
        """Build BM25 index from documents with keyword boosting.

        Indexing Strategy:
        1. Tokenize description field (base content)
        2. Tokenize keywords field (curated terms)
        3. Boost keywords by repeating tokens KEYWORD_BOOST times
        4. Combine description + boosted keywords for final index

        This approach:
        - Gives higher weight to human-curated keywords
        - Enables matching on keyword-only terms (e.g., "packing")
        - Preserves description-based natural language search
        - Uses BM25 saturation to prevent over-amplification

        Args:
            documents: List of SearchDocument instances to index

        Example:
            >>> indexer = BM25Indexer()
            >>> indexer.build([doc1, doc2, doc3])
            >>> indexer.doc_count
            3
            >>> indexer.avg_doc_len
            62.5  # Longer due to boosted keywords
        """
        # Clear existing index
        self.clear()

        # 1. Tokenize all documents (name + description + boosted keywords)
        for doc in documents:
            doc_id = doc.name

            # Tokenize document name (API path or command name)
            # Critical for path-based queries like "Ball.vel" or "itasca.ball.create"
            # With improved tokenizer, paths are split properly:
            # "itasca.ball.Ball.vel" → ["itasca", "ball", "ball", "vel"]
            name_tokens = self.tokenizer.tokenize(doc.name)

            # Boost name tokens for exact path matching
            # Example: NAME_BOOST=2.0 → name tokens appear 2 times in index
            # This ensures "Ball.vel" ranks higher than "Ball.vel_y"
            name_boost_count = int(self.NAME_BOOST)
            boosted_name_tokens = name_tokens * name_boost_count

            # Tokenize title if different from name
            # Some documents have more descriptive titles
            title_tokens = []
            if doc.title and doc.title != doc.name:
                title_tokens = self.tokenizer.tokenize(doc.title)

            # Tokenize description (base content)
            desc_tokens = self.tokenizer.tokenize(doc.description)

            # Tokenize keywords (curated terms)
            kw_tokens = self.tokenizer.tokenize(" ".join(doc.keywords))

            # Boost keywords by repeating tokens
            # Example: KEYWORD_BOOST=3.0 → keywords appear 3 times in index
            # This increases term frequency: tf(keyword) += 3
            kw_boost_count = int(self.KEYWORD_BOOST)
            boosted_kw_tokens = kw_tokens * kw_boost_count

            # Combine boosted name + title + description + boosted keywords
            # Boosted name tokens come first for path-based queries
            all_tokens = boosted_name_tokens + title_tokens + desc_tokens + boosted_kw_tokens

            self.documents[doc_id] = all_tokens

            # Calculate term frequencies (includes boosted keywords)
            term_counts = Counter(all_tokens)
            self.term_freq[doc_id] = dict(term_counts)

            # Update document frequencies
            for term in set(all_tokens):
                self.term_doc_freq[term] = self.term_doc_freq.get(term, 0) + 1

        # 2. Calculate statistics
        self.doc_count = len(self.documents)
        if self.doc_count > 0:
            total_len = sum(len(tokens) for tokens in self.documents.values())
            self.avg_doc_len = total_len / self.doc_count
        else:
            self.avg_doc_len = 0.0

    def get_idf(self, term: str) -> float:
        """Calculate IDF (Inverse Document Frequency) for a term.

        Uses BM25 IDF formula (Robertson-Spärck Jones):
        IDF(t) = log((N - df(t) + 0.5) / (df(t) + 0.5) + 1)

        where:
        - N = total number of documents
        - df(t) = number of documents containing term t

        Args:
            term: Term to calculate IDF for

        Returns:
            IDF score (>= 0)

        Example:
            >>> indexer.doc_count = 100
            >>> indexer.term_doc_freq = {"ball": 30, "porosity": 5}
            >>> indexer.get_idf("ball")
            1.203  # Common term → lower IDF
            >>> indexer.get_idf("porosity")
            2.944  # Rare term → higher IDF
        """
        df = self.term_doc_freq.get(term, 0)
        N = self.doc_count

        if N == 0 or df == 0:
            return 0.0

        # BM25 IDF formula
        idf = math.log((N - df + 0.5) / (df + 0.5) + 1)
        return max(0.0, idf)  # Ensure non-negative

    def get_term_freq(self, doc_id: str, term: str) -> int:
        """Get term frequency in a specific document.

        Args:
            doc_id: Document ID
            term: Term to look up

        Returns:
            Term frequency (0 if not found)

        Example:
            >>> indexer.get_term_freq("ball create", "ball")
            2  # "ball" appears twice
            >>> indexer.get_term_freq("ball create", "xyz")
            0  # Not found
        """
        return self.term_freq.get(doc_id, {}).get(term, 0)

    def get_doc_length(self, doc_id: str) -> int:
        """Get document length (number of tokens).

        Args:
            doc_id: Document ID

        Returns:
            Document length

        Example:
            >>> indexer.get_doc_length("ball create")
            45  # Document has 45 tokens
        """
        return len(self.documents.get(doc_id, []))

    def get_all_doc_ids(self) -> Set[str]:
        """Get all document IDs in the index.

        Returns:
            Set of document IDs

        Example:
            >>> indexer.get_all_doc_ids()
            {'ball create', 'wall create', 'contact property', ...}
        """
        return set(self.documents.keys())

    def clear(self) -> None:
        """Clear all index data.

        Example:
            >>> indexer.clear()
            >>> indexer.doc_count
            0
        """
        self.documents.clear()
        self.term_doc_freq.clear()
        self.term_freq.clear()
        self.doc_count = 0
        self.avg_doc_len = 0.0

    def get_stats(self) -> Dict:
        """Get index statistics for debugging.

        Returns:
            Dictionary with index statistics including boost parameters

        Example:
            >>> stats = indexer.get_stats()
            >>> stats
            {
                'doc_count': 115,
                'avg_doc_len': 72.5,  # Increased due to name and keyword boost
                'vocab_size': 1234,
                'total_terms': 8322,  # Increased due to name and keyword boost
                'name_boost': 2.0,
                'keyword_boost': 3.0
            }
        """
        return {
            'doc_count': self.doc_count,
            'avg_doc_len': round(self.avg_doc_len, 2),
            'vocab_size': len(self.term_doc_freq),
            'total_terms': sum(len(tokens) for tokens in self.documents.values()),
            'name_boost': self.NAME_BOOST,
            'keyword_boost': self.KEYWORD_BOOST
        }
