"""Data loading layer for PFC SDK documentation.

This module is responsible for loading documentation data from JSON files
and providing cached access to avoid repeated I/O operations.

Responsibilities:
- Load index.json (quick reference and metadata)
- Load keywords.json files (from all modules)
- Load individual API documentation files
- Cache loaded data for performance
"""

from typing import Dict, Any, Optional
from functools import lru_cache
import json

from backend.infrastructure.pfc.config import PFC_DOCS_SOURCE


class DocumentationLoader:
    """Loads and caches SDK documentation data.

    This class provides static methods for loading various documentation
    resources. All methods use caching to avoid repeated file I/O.
    """

    @staticmethod
    @lru_cache(maxsize=1)
    def load_index() -> Dict[str, Any]:
        """Load the main index file with caching.

        The index file contains:
        - quick_ref: Direct API name to file reference mapping
        - keywords: Keyword to API list mapping (if present)
        - fallback_hints: Suggestions when SDK doesn't support operation

        Returns:
            Dict containing index data structure

        Raises:
            FileNotFoundError: If index.json doesn't exist

        Example:
            >>> index = DocumentationLoader.load_index()
            >>> quick_ref = index["quick_ref"]
            >>> "itasca.ball.create" in quick_ref
            True
        """
        index_path = PFC_DOCS_SOURCE / "index.json"
        if not index_path.exists():
            raise FileNotFoundError(f"Index file not found: {index_path}")

        with open(index_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    @staticmethod
    @lru_cache(maxsize=1)
    def load_all_keywords() -> Dict[str, list]:
        """Load keywords from all modules with caching.

        Aggregates keywords from:
        - itasca_keywords.json (top-level module)
        - modules/*/keywords.json (sub-modules like ball, contact, etc.)

        Returns:
            Dict mapping keywords to list of API names

        Example:
            >>> keywords = DocumentationLoader.load_all_keywords()
            >>> keywords["create ball"]
            ["itasca.ball.create"]
            >>> keywords["ball velocity"]
            ["Ball.vel", "Ball.vel_set", "Ball.vel_spin"]
        """
        all_keywords = {}

        # Load itasca top-level keywords
        itasca_keywords_path = PFC_DOCS_SOURCE / "itasca_keywords.json"
        if itasca_keywords_path.exists():
            with open(itasca_keywords_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                all_keywords.update(data.get("keywords", {}))

        # Load keywords from all sub-modules
        modules_dir = PFC_DOCS_SOURCE / "modules"
        if modules_dir.exists():
            for module_dir in modules_dir.iterdir():
                if module_dir.is_dir():
                    keywords_file = module_dir / "keywords.json"
                    if keywords_file.exists():
                        with open(keywords_file, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            all_keywords.update(data.get("keywords", {}))

        return all_keywords

    @staticmethod
    def load_api_doc(api_name: str) -> Optional[Dict[str, Any]]:
        """Load documentation for a specific API.

        Args:
            api_name: Full API name like "itasca.ball.create" or "Ball.vel"

        Returns:
            API documentation dict with fields:
                - signature: Function signature
                - description: Detailed description
                - parameters: List of parameter definitions
                - returns: Return value information
                - examples: Usage examples
                - limitations: Known limitations (optional)
                - fallback_commands: Alternative commands (optional)
                - best_practices: Recommended practices (optional)
                - notes: Additional notes (optional)
                - see_also: Related APIs (optional)

            Returns None if API not found.

        Example:
            >>> doc = DocumentationLoader.load_api_doc("itasca.ball.create")
            >>> doc["signature"]
            "itasca.ball.create(radius, pos=None)"
            >>> doc["description"]
            "Create a new ball in the simulation..."
        """
        index = DocumentationLoader.load_index()

        # Get file reference from index
        ref = index["quick_ref"].get(api_name)
        if not ref:
            return None

        # Parse file path and anchor
        # Format: "file_name.json#function_name"
        file_name, anchor = ref.split('#')
        doc_path = PFC_DOCS_SOURCE / file_name

        if not doc_path.exists():
            return None

        with open(doc_path, 'r', encoding='utf-8') as f:
            doc = json.load(f)

        # Find the specific function or method
        # Object method files contain "methods" key
        # Module function files contain "functions" key
        if "methods" in doc:
            for method in doc["methods"]:
                if method["name"] == anchor:
                    return method
        elif "functions" in doc:
            for func in doc["functions"]:
                if func["name"] == anchor:
                    return func

        return None

    @staticmethod
    def clear_cache():
        """Clear all cached data.

        Useful for testing or when documentation files are updated.
        """
        DocumentationLoader.load_index.cache_clear()
        DocumentationLoader.load_all_keywords.cache_clear()
