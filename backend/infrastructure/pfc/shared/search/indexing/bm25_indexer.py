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
    """BM25 inverted index builder.

    Builds and maintains BM25 index structures for efficient scoring:
    - Document tokens (preprocessed)
    - Term frequencies per document
    - Document frequencies per term
    - Average document length

    Design:
    - Pure Python implementation (no NumPy)
    - Optimized for ~200 documents (commands + APIs)
    - Supports incremental updates

    Usage:
        >>> indexer = BM25Indexer()
        >>> indexer.build(documents)
        >>> idf = indexer.get_idf("porosity")
        >>> idf
        2.345  # Example IDF value
    """

    def __init__(self):
        """Initialize empty BM25 index."""
        self.documents: Dict[str, List[str]] = {}  # doc_id → tokens
        self.doc_count: int = 0
        self.avg_doc_len: float = 0.0
        self.term_doc_freq: Dict[str, int] = {}  # term → document frequency
        self.term_freq: Dict[str, Dict[str, int]] = {}  # doc_id → {term → count}
        self.tokenizer = TextTokenizer()

    def build(self, documents: List[SearchDocument]) -> None:
        """Build BM25 index from documents.

        Args:
            documents: List of SearchDocument instances to index

        Example:
            >>> indexer = BM25Indexer()
            >>> indexer.build([doc1, doc2, doc3])
            >>> indexer.doc_count
            3
            >>> indexer.avg_doc_len
            45.2
        """
        # Clear existing index
        self.clear()

        # 1. Tokenize all documents
        for doc in documents:
            doc_id = doc.id
            # Tokenize description field for BM25
            tokens = self.tokenizer.tokenize(doc.description)
            self.documents[doc_id] = tokens

            # Calculate term frequencies
            term_counts = Counter(tokens)
            self.term_freq[doc_id] = dict(term_counts)

            # Update document frequencies
            for term in set(tokens):
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
            Dictionary with index statistics

        Example:
            >>> stats = indexer.get_stats()
            >>> stats
            {
                'doc_count': 115,
                'avg_doc_len': 45.2,
                'vocab_size': 1234,
                'total_terms': 5198
            }
        """
        return {
            'doc_count': self.doc_count,
            'avg_doc_len': round(self.avg_doc_len, 2),
            'vocab_size': len(self.term_doc_freq),
            'total_terms': sum(len(tokens) for tokens in self.documents.values())
        }
