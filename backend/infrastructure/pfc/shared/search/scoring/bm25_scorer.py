"""BM25 scoring algorithm for PFC search system.

This module implements BM25 ranking with support for partial matching,
using only Python standard library (no NumPy dependency).
"""

from typing import List, Dict, Any, Tuple
from backend.infrastructure.pfc.shared.models.document import SearchDocument
from backend.infrastructure.pfc.shared.search.indexing.bm25_indexer import BM25Indexer
from backend.infrastructure.pfc.shared.search.preprocessing.tokenizer import TextTokenizer
from backend.infrastructure.pfc.shared.search.keyword_matcher import find_partial_matches


class BM25Scorer:
    """BM25 scoring algorithm implementation.

    Implements BM25 ranking function with configurable parameters:
    - K1: Term frequency saturation parameter
    - B: Document length normalization parameter

    Supports partial matching for abbreviations (e.g., "pos" → "position")
    with quality-based score adjustment.

    Design:
    - Pure Python (no NumPy)
    - Optimized for ~200 documents
    - Compatible with keyword matching system

    Usage:
        >>> indexer = BM25Indexer()
        >>> indexer.build(documents)
        >>> scorer = BM25Scorer(indexer)
        >>> score, info = scorer.score("create ball porosity", doc)
        >>> score
        12.5  # BM25 score
    """

    # BM25 hyperparameters (tunable)
    K1 = 1.5  # Term frequency saturation (1.2-2.0 recommended)
    B = 0.75  # Document length normalization (0.5-0.8 recommended)

    def __init__(self, indexer: BM25Indexer):
        """Initialize BM25 scorer.

        Args:
            indexer: Built BM25 index
        """
        self.indexer = indexer
        self.tokenizer = TextTokenizer()

    def score(self, query: str, document: SearchDocument) -> Tuple[float, Dict[str, Any]]:
        """Calculate BM25 score for a query-document pair.

        Args:
            query: User query string
            document: Document to score

        Returns:
            Tuple of (score, match_info) where:
            - score: BM25 relevance score (higher = more relevant)
            - match_info: Dict with matched terms and their contributions

        Example:
            >>> score, info = scorer.score("ball porosity", doc)
            >>> score
            8.5
            >>> info
            {
                'matched_terms': ['ball', 'porosity'],
                'term_scores': {'ball': 3.2, 'porosity': 5.3},
                'exact_matches': ['ball'],
                'partial_matches': []
            }
        """
        # 1. Tokenize query
        query_tokens = self.tokenizer.tokenize(query)
        if not query_tokens:
            return 0.0, {}

        # 2. Get document tokens
        doc_id = document.name
        doc_tokens = set(self.indexer.documents.get(doc_id, []))
        query_set = set(query_tokens)

        # 3. Find exact matches
        exact_matches = query_set & doc_tokens

        # 4. Find partial matches for unmatched query terms
        unmatched_query = query_set - exact_matches
        unmatched_doc = doc_tokens - exact_matches
        partial_matches, quality = find_partial_matches(unmatched_query, unmatched_doc)

        # 5. Build list of terms to score
        matched_terms = list(exact_matches)
        term_scores = {}

        # Score exact matches
        for term in exact_matches:
            term_score = self._score_term(term, doc_id)
            matched_terms.append(term)
            term_scores[term] = round(term_score, 3)

        # Score partial matches (with quality discount)
        for q_term, d_term in partial_matches:
            term_score = self._score_term(d_term, doc_id) * quality
            matched_terms.append(f"{d_term} (← {q_term})")
            term_scores[d_term] = round(term_score, 3)

        # 6. Sum all term scores
        total_score = sum(term_scores.values())

        # 7. Build match info
        match_info = {
            'matched_terms': matched_terms,
            'term_scores': term_scores,
            'exact_matches': list(exact_matches),
            'partial_matches': [
                {'query': q, 'doc': d, 'quality': quality}
                for q, d in partial_matches
            ]
        }

        return total_score, match_info

    def _score_term(self, term: str, doc_id: str) -> float:
        """Calculate BM25 score contribution for a single term.

        BM25 formula:
        score(t, D) = IDF(t) × (f(t, D) × (k1 + 1)) / (f(t, D) + k1 × (1 - b + b × |D| / avgdl))

        where:
        - IDF(t): Inverse document frequency of term t
        - f(t, D): Frequency of term t in document D
        - |D|: Length of document D
        - avgdl: Average document length
        - k1, b: Tuning parameters

        Args:
            term: Term to score
            doc_id: Document ID

        Returns:
            BM25 score contribution for this term
        """
        # 1. Get IDF
        idf = self.indexer.get_idf(term)

        # 2. Get term frequency
        tf = self.indexer.get_term_freq(doc_id, term)

        if tf == 0:
            return 0.0

        # 3. Calculate length normalization factor
        doc_len = self.indexer.get_doc_length(doc_id)
        avg_len = self.indexer.avg_doc_len

        if avg_len == 0:
            norm_factor = 1.0
        else:
            norm_factor = 1 - self.B + self.B * (doc_len / avg_len)

        # 4. Calculate saturated term frequency
        saturated_tf = (tf * (self.K1 + 1)) / (tf + self.K1 * norm_factor)

        # 5. Final score
        score = idf * saturated_tf

        return score

    def batch_score(
        self,
        query: str,
        documents: List[SearchDocument]
    ) -> List[Tuple[SearchDocument, float, Dict[str, Any]]]:
        """Score multiple documents for a query.

        Args:
            query: User query
            documents: List of documents to score

        Returns:
            List of (document, score, match_info) tuples for documents with score > 0

        Example:
            >>> results = scorer.batch_score("create ball", documents)
            >>> len(results)
            15  # 15 documents matched
        """
        results = []

        for doc in documents:
            score, match_info = self.score(query, doc)
            if score > 0:
                results.append((doc, score, match_info))

        return results

    @classmethod
    def set_parameters(cls, k1: float | None = None, b: float | None = None):
        """Set BM25 hyperparameters.

        Args:
            k1: Term frequency saturation (default: 1.5, range: 1.2-2.0)
                If None, parameter is not changed
            b: Length normalization (default: 0.75, range: 0.5-0.8)
               If None, parameter is not changed

        Example:
            >>> BM25Scorer.set_parameters(k1=2.0)  # Only update k1
            >>> BM25Scorer.set_parameters(k1=2.0, b=0.5)  # Update both
        """
        if k1 is not None:
            cls.K1 = k1
        if b is not None:
            cls.B = b
