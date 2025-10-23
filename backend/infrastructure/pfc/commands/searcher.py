"""Command search orchestrator for PFC command documentation.

This module provides keyword-based search for PFC commands with optional
model properties integration.

Features:
- Keyword matching against command names, syntax, and descriptions
- Optional model properties search (controlled by include_model_properties)
- Scoring based on relevance (exact match > keyword match)
- Configurable result limit
"""

from typing import List, Set
from backend.infrastructure.pfc.commands.models import CommandSearchResult, DocumentType
from backend.infrastructure.pfc.commands.loader import CommandLoader


class CommandSearcher:
    """Search PFC command documentation using keyword matching.

    This class provides a simple but effective keyword search that:
    1. Searches command names, syntax, and descriptions
    2. Optionally includes contact model properties
    3. Scores results based on match quality
    4. Returns top-N results sorted by score
    """

    def search(
        self,
        query: str,
        top_n: int = 10,
        include_model_properties: bool = True
    ) -> List[CommandSearchResult]:
        """Search for commands and optionally model properties.

        Args:
            query: Search query (e.g., "ball create", "kn property", "contact model")
            top_n: Maximum number of results to return (default: 10)
            include_model_properties: Whether to search model properties (default: True)

        Returns:
            List of CommandSearchResult objects sorted by score (highest first)

        Scoring:
            - Exact command name match: 1000
            - Command name substring: 800-900
            - Syntax match: 700
            - Description keyword match: 500-600
            - Model property exact: 950
            - Model property partial: 700-800

        Example:
            >>> searcher = CommandSearcher()
            >>> results = searcher.search("ball create")
            >>> results[0].name
            "ball create"
            >>> results[0].doc_type
            DocumentType.COMMAND

            >>> results = searcher.search("kn stiffness", include_model_properties=True)
            >>> results[0].name
            "linear.kn"
            >>> results[0].doc_type
            DocumentType.MODEL_PROPERTY
        """
        query_lower = query.lower().strip()
        query_words = set(query_lower.split())

        matches = []

        # Search commands
        commands = CommandLoader.get_all_commands()
        for cmd in commands:
            score = self._score_command(cmd, query_lower, query_words)
            if score > 0:
                matches.append(CommandSearchResult(
                    name=f"{cmd['category']} {cmd['name']}",
                    score=score,
                    doc_type=DocumentType.COMMAND,
                    category=cmd['category'],
                    metadata={
                        "file": cmd.get("file"),
                        "short_description": cmd.get("short_description"),
                        "syntax": cmd.get("syntax"),
                        "python_available": cmd.get("python_available")
                    }
                ))

        # Search model properties if enabled
        if include_model_properties:
            models = CommandLoader.get_all_model_properties()
            for model in models:
                # Load full model doc to search properties
                model_doc = CommandLoader.load_model_property_doc(model["name"])
                if not model_doc:
                    continue

                # Search each property in the model
                for group in model_doc.get("property_groups", []):
                    for prop in group.get("properties", []):
                        score = self._score_model_property(
                            model["name"],
                            prop,
                            query_lower,
                            query_words
                        )
                        if score > 0:
                            matches.append(CommandSearchResult(
                                name=f"{model['name']}.{prop['keyword']}",
                                score=score,
                                doc_type=DocumentType.MODEL_PROPERTY,
                                category=model["name"],
                                metadata={
                                    "file": model.get("file"),
                                    "property_keyword": prop["keyword"],
                                    "symbol": prop.get("symbol"),
                                    "description": prop.get("description"),
                                    "type": prop.get("type"),
                                    "default": prop.get("default"),
                                    "model_full_name": model.get("full_name")
                                }
                            ))

        # Sort by score (descending) and return top-N
        matches.sort(key=lambda x: x.score, reverse=True)
        return matches[:top_n]

    def _score_command(
        self,
        cmd: dict,
        query_lower: str,
        query_words: Set[str]
    ) -> int:
        """Calculate relevance score for a command.

        Args:
            cmd: Command metadata dict
            query_lower: Lowercase query string
            query_words: Set of query words

        Returns:
            Score (0-1000), 0 if no match

        Scoring logic:
            - Exact command name match: 1000
            - Command name contains query: 900
            - Query contains command name: 800
            - Syntax contains all query words: 700
            - Short description keyword match: 500-600 (based on coverage)
        """
        cmd_name = cmd["name"].lower()
        cmd_full = f"{cmd['category']} {cmd_name}".lower()
        syntax = cmd.get("syntax", "").lower()
        description = cmd.get("short_description", "").lower()

        # Exact match (command name or full name)
        if query_lower == cmd_name or query_lower == cmd_full:
            return 1000

        # Command name substring match
        if query_lower in cmd_full:
            return 900
        if cmd_full in query_lower:
            return 800

        # Syntax match (all query words appear in syntax)
        syntax_words = set(syntax.split())
        if query_words and query_words.issubset(syntax_words):
            return 700

        # Description keyword match
        description_words = set(description.split())
        matching_words = query_words & description_words
        if matching_words:
            # Score based on coverage: what percentage of query is matched?
            coverage = len(matching_words) / len(query_words) if query_words else 0
            return int(500 + coverage * 100)

        return 0  # No match

    def _score_model_property(
        self,
        model_name: str,
        prop: dict,
        query_lower: str,
        query_words: Set[str]
    ) -> int:
        """Calculate relevance score for a model property.

        Args:
            model_name: Model name (e.g., "linear")
            prop: Property dict with keyword, description, symbol
            query_lower: Lowercase query string
            query_words: Set of query words

        Returns:
            Score (0-950), 0 if no match

        Scoring logic:
            - Exact property keyword match: 950
            - Property keyword in query: 900
            - Symbol match: 850
            - Description keyword match: 700-800 (based on coverage)
            - Model name + keyword match: 950
        """
        keyword = prop["keyword"].lower()
        description = prop.get("description", "").lower()
        symbol = prop.get("symbol", "").lower()
        full_path = f"{model_name}.{keyword}".lower()

        # Exact matches (highest priority)
        if query_lower == keyword:
            return 950
        if query_lower == full_path:
            return 950

        # Keyword substring match
        if keyword in query_lower:
            return 900

        # Symbol match (e.g., "k_n", "μ")
        if symbol and symbol in query_lower:
            return 850

        # Description keyword match
        description_words = set(description.split())
        matching_words = query_words & description_words
        if matching_words:
            # Score based on coverage
            coverage = len(matching_words) / len(query_words) if query_words else 0
            return int(700 + coverage * 100)

        return 0  # No match
