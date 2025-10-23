"""Command search orchestrator for PFC command documentation.

This module provides keyword-based search for PFC commands with optional
model properties integration using unified search algorithms.

Features:
- BM25-inspired keyword matching with partial matching support
- Unified search algorithm shared with Python API search
- Multi-factor scoring (keyword coverage + query precision + match count)
- Optional model properties search (controlled by include_model_properties)
- Configurable result limit
"""

from typing import List, Set, Tuple
from backend.infrastructure.pfc.shared.search.models import SearchResult, DocumentType, SearchStrategy as SearchStrategyEnum
from backend.infrastructure.pfc.shared.search.keyword_matcher import (
    calculate_relevance_score,
    find_partial_matches,
    word_match_quality
)
from backend.infrastructure.pfc.commands.loader import CommandLoader

# Backward compatibility alias
CommandSearchResult = SearchResult


class CommandSearcher:
    """Search PFC command documentation using unified keyword matching.

    This class uses the same BM25-inspired search algorithm as Python API search,
    providing consistent behavior across all PFC documentation systems.

    Algorithm:
    1. Build keyword index from search_keywords fields
    2. Match query words against keywords (exact + partial matching)
    3. Score based on multi-factor ranking:
       - Keyword coverage (primary): How much of keyword is covered
       - Query precision (secondary): How focused is the match
       - Match count (tie-breaker): Exact matches > partial matches
    4. Return top-N results sorted by score
    """

    def search(
        self,
        query: str,
        top_n: int = 10,
        include_model_properties: bool = True
    ) -> List[SearchResult]:
        """Search for commands and optionally model properties using unified algorithm.

        This method uses the same search algorithm as Python API search for consistency.
        The algorithm supports:
        - Exact keyword matching
        - Partial matching (abbreviations like "pos" → "position")
        - Multi-factor BM25-inspired scoring

        Args:
            query: Search query (e.g., "ball create", "contact model", "linear")
            top_n: Maximum number of results to return (default: 10)
            include_model_properties: Whether to search model properties (default: True)

        Returns:
            List of SearchResult objects sorted by score (highest first)

        Scoring (multi-factor):
            - Keyword coverage (0-1000): Primary factor
            - Query precision (0-100): Secondary factor
            - Match count (1-10): Tie-breaker
            Total score range: 0-1100+

        Example:
            >>> searcher = CommandSearcher()
            >>> results = searcher.search("ball create")
            >>> results[0].name
            "ball create"
            >>> results[0].doc_type
            DocumentType.COMMAND
            >>> results[0].strategy
            SearchStrategyEnum.KEYWORD

            >>> results = searcher.search("linear model")
            >>> results[0].name
            "linear"
            >>> results[0].doc_type
            DocumentType.MODEL_PROPERTY
        """
        query_lower = query.lower().strip()
        query_words = set(query_lower.split())

        # Load keyword index (cached)
        keywords = CommandLoader.load_all_keywords()

        matches = []  # List of (name, score, doc_type, category, metadata) tuples

        # Match each keyword against query using unified algorithm
        for keyword, names in keywords.items():
            keyword_words = set(keyword.split())
            matching_words = keyword_words & query_words

            # Calculate potential partial matches
            unmatched_query = query_words - matching_words
            unmatched_keyword = keyword_words - matching_words
            partial_matches, _ = find_partial_matches(unmatched_query, unmatched_keyword)

            # Match if there's either exact or partial overlap
            if len(matching_words) > 0 or len(partial_matches) > 0:
                # Calculate multi-factor score using shared algorithm
                score = calculate_relevance_score(
                    keyword_words,
                    query_words,
                    matching_words
                )

                # Add all items associated with this keyword
                for name in names:
                    # Determine doc_type and build metadata
                    doc_type, category, metadata = self._get_item_info(name)

                    # Skip model properties if not included
                    if not include_model_properties and doc_type == DocumentType.MODEL_PROPERTY:
                        continue

                    matches.append((name, score, doc_type, category, metadata))

        # Sort by score (descending), then by name (for stability)
        matches.sort(key=lambda x: (-x[1], x[0]))

        # Convert to SearchResult objects
        results = []
        for name, score, doc_type, category, metadata in matches[:top_n]:
            results.append(SearchResult(
                name=name,
                score=score,
                doc_type=doc_type,
                category=category,
                strategy=SearchStrategyEnum.KEYWORD,
                metadata=metadata
            ))

        return results

    def _get_item_info(self, name: str) -> Tuple[DocumentType, str, dict]:
        """Get document type, category, and metadata for a command or model.

        Args:
            name: Command name (e.g., "ball create") or model name (e.g., "linear")

        Returns:
            Tuple of (doc_type, category, metadata)

        Example:
            >>> self._get_item_info("ball create")
            (DocumentType.COMMAND, "ball", {...})

            >>> self._get_item_info("linear")
            (DocumentType.MODEL_PROPERTY, "linear", {...})
        """
        # Check if this is a model property (single word, matches known models)
        models = CommandLoader.get_all_model_properties()
        model_names = {m["name"] for m in models}

        if name in model_names:
            # This is a model property
            model_meta = next(m for m in models if m["name"] == name)
            return (
                DocumentType.MODEL_PROPERTY,
                name,
                {
                    "file": model_meta.get("file"),
                    "full_name": model_meta.get("full_name"),
                    "description": model_meta.get("description"),
                    "common_use": model_meta.get("common_use"),
                    "priority": model_meta.get("priority")
                }
            )
        else:
            # This is a command (format: "category name")
            parts = name.split(maxsplit=1)
            if len(parts) == 2:
                category, cmd_name = parts
            else:
                # Fallback if format is unexpected
                category = "unknown"
                cmd_name = name

            # Find command metadata
            commands = CommandLoader.get_all_commands()
            cmd_meta = next(
                (c for c in commands if c["category"] == category and c["name"] == cmd_name),
                None
            )

            metadata = {}
            if cmd_meta:
                metadata = {
                    "file": cmd_meta.get("file"),
                    "short_description": cmd_meta.get("short_description"),
                    "syntax": cmd_meta.get("syntax"),
                    "python_available": cmd_meta.get("python_available")
                }

            return (DocumentType.COMMAND, category, metadata)
