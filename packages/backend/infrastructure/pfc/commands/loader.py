"""Data loading layer for PFC command documentation.

This module loads command documentation and model properties from JSON files
with caching for performance.

Responsibilities:
- Load index.json (command catalog with 115 commands across 7 categories)
- Load individual command documentation files
- Load contact model properties (integrated support for 5 models)
- Cache loaded data to avoid repeated I/O
"""

from typing import Dict, Any, Optional, List
from functools import lru_cache
from pathlib import Path
import json

from backend.infrastructure.pfc.config import PFC_COMMAND_DOCS_ROOT, PFC_CONTACT_MODELS_ROOT, PFC_REFERENCES_ROOT


class CommandLoader:
    """Loads and caches PFC command documentation data.

    This class provides static methods for loading command docs and model
    properties. All methods use caching to avoid repeated file I/O.
    """

    @staticmethod
    @lru_cache(maxsize=1)
    def load_index() -> Dict[str, Any]:
        """Load the main command index file with caching.

        The index file contains:
        - categories: 7 categories (ball, wall, clump, contact, model, fragment, measure)
        - commands: 115 commands total with metadata
        - python_sdk_alternatives: Command to Python SDK mappings
        - command_patterns: Common command patterns

        Returns:
            Dict containing index data structure

        Raises:
            FileNotFoundError: If index.json doesn't exist

        Example:
            >>> index = CommandLoader.load_index()
            >>> categories = index["categories"]
            >>> len(categories)
            7
            >>> "ball" in categories
            True
        """
        index_path = PFC_COMMAND_DOCS_ROOT / "index.json"
        if not index_path.exists():
            raise FileNotFoundError(f"Command index file not found: {index_path}")

        with open(index_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    @staticmethod
    def load_command_doc(category: str, command_name: str) -> Optional[Dict[str, Any]]:
        """Load documentation for a specific command.

        Args:
            category: Command category (e.g., "ball", "contact", "model")
            command_name: Command name (e.g., "create", "property", "cycle")

        Returns:
            Command documentation dict with fields:
                - command: Full command name
                - syntax: Command syntax
                - description: Detailed description
                - parameters: Parameter definitions
                - examples: Usage examples
                - notes: Additional notes
                - related_commands: Related commands
                - python_alternative: Python SDK alternative (if available)

            Returns None if command not found.

        Example:
            >>> doc = CommandLoader.load_command_doc("ball", "create")
            >>> doc["syntax"]
            "ball create <keyword> ..."
            >>> "description" in doc
            True
        """
        index = CommandLoader.load_index()

        # Find command file path from index
        categories = index.get("categories", {})
        if category not in categories:
            return None

        category_data = categories[category]
        commands = category_data.get("commands", [])

        # Find matching command
        command_file = None
        for cmd in commands:
            if cmd["name"] == command_name:
                command_file = cmd.get("file")
                break

        if not command_file:
            return None

        # Load command documentation
        doc_path = PFC_COMMAND_DOCS_ROOT / command_file
        if not doc_path.exists():
            return None

        with open(doc_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    @staticmethod
    @lru_cache(maxsize=1)
    def load_model_properties_index() -> Dict[str, Any]:
        """Load contact model properties index.

        Returns:
            Model properties index with:
                - models: List of 5 available models (linear, linearcbond,
                         linearpbond, hertz, rrlinear)
                - property_metadata_fields: Field descriptions
                - usage_contexts: When to use model properties
                - related_documentation: Links to command docs

        Example:
            >>> index = CommandLoader.load_model_properties_index()
            >>> models = index["models"]
            >>> len(models)
            5
            >>> models[0]["name"]
            'linear'
        """
        index_path = PFC_CONTACT_MODELS_ROOT / "index.json"
        if not index_path.exists():
            return {}

        with open(index_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    @staticmethod
    def load_model_property_doc(model_name: str) -> Optional[Dict[str, Any]]:
        """Load documentation for a specific contact model's properties.

        Args:
            model_name: Model name (e.g., "linear", "linearpbond", "hertz")

        Returns:
            Model properties documentation dict with fields:
                - model: Model name
                - full_name: Full model name (e.g., "Linear Model")
                - description: Model description
                - property_groups: List of property groups with properties
                  Each property has: keyword, symbol, description, type,
                  range, default, modifiable, inheritable
                - typical_applications: Common use cases

            Returns None if model not found.

        Example:
            >>> doc = CommandLoader.load_model_property_doc("linear")
            >>> doc["full_name"]
            "Linear Model"
            >>> len(doc["property_groups"])
            2  # Linear Group, Dashpot Group
            >>> doc["property_groups"][0]["properties"][0]["keyword"]
            'kn'
        """
        index = CommandLoader.load_model_properties_index()
        if not index:
            return None

        # Find model file path
        models = index.get("models", [])
        model_file = None
        for model in models:
            if model["name"] == model_name:
                model_file = model.get("file")
                break

        if not model_file:
            return None

        # Load model properties documentation
        doc_path = PFC_CONTACT_MODELS_ROOT / model_file
        if not doc_path.exists():
            return None

        with open(doc_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    @staticmethod
    def get_all_commands() -> List[Dict[str, Any]]:
        """Get all commands from all categories.

        Returns:
            List of command metadata dicts, each containing:
                - name: Command name
                - category: Category name
                - file: File path
                - short_description: Brief description
                - syntax: Command syntax
                - python_available: Python SDK availability

        Example:
            >>> commands = CommandLoader.get_all_commands()
            >>> len(commands)
            115  # Total across all 7 categories
            >>> commands[0]["category"] in ["ball", "wall", "clump", ...]
            True
        """
        index = CommandLoader.load_index()
        categories = index.get("categories", {})

        all_commands = []
        for category_name, category_data in categories.items():
            for cmd in category_data.get("commands", []):
                all_commands.append({
                    **cmd,
                    "category": category_name
                })

        return all_commands

    @staticmethod
    def get_all_model_properties() -> List[Dict[str, Any]]:
        """Get all contact model properties metadata.

        Returns:
            List of model metadata dicts, each containing:
                - name: Model name (e.g., "linear")
                - file: File path
                - full_name: Full model name
                - description: Model description
                - common_use: Common use cases
                - priority: Importance ("high", "medium")

        Example:
            >>> models = CommandLoader.get_all_model_properties()
            >>> len(models)
            5  # linear, linearcbond, linearpbond, hertz, rrlinear
            >>> [m["name"] for m in models]
            ['linear', 'linearcbond', 'linearpbond', 'hertz', 'rrlinear']
        """
        index = CommandLoader.load_model_properties_index()
        return index.get("models", [])

    @staticmethod
    @lru_cache(maxsize=1)
    def load_references_index() -> Dict[str, Any]:
        """Load the main references index file.

        Returns:
            References index with:
                - categories: Available reference categories
                - navigation: Navigation hints
                - notes: Usage notes

        Example:
            >>> index = CommandLoader.load_references_index()
            >>> categories = index["categories"]
            >>> "contact-models" in categories
            True
        """
        index_path = PFC_REFERENCES_ROOT / "index.json"
        if not index_path.exists():
            return {}

        with open(index_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    @staticmethod
    def load_reference_category_index(category: str) -> Optional[Dict[str, Any]]:
        """Load index for a specific reference category.

        Args:
            category: Category name (e.g., "contact-models")

        Returns:
            Category index dict or None if not found

        Example:
            >>> index = CommandLoader.load_reference_category_index("contact-models")
            >>> len(index["models"])
            5
        """
        refs_index = CommandLoader.load_references_index()
        categories = refs_index.get("categories", {})

        if category not in categories:
            return None

        cat_data = categories[category]
        index_file = cat_data.get("index_file")
        if not index_file:
            return None

        index_path = PFC_REFERENCES_ROOT / index_file
        if not index_path.exists():
            return None

        with open(index_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    @staticmethod
    def clear_cache():
        """Clear all cached data.

        Useful for testing or when documentation files are updated.
        """
        CommandLoader.load_index.cache_clear()
        CommandLoader.load_model_properties_index.cache_clear()
        CommandLoader.load_references_index.cache_clear()
