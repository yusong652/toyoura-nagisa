"""Command document adapter for PFC search system.

This module converts PFC command documentation (including model properties)
from the CommandLoader format into unified SearchDocument models for search.
"""

from typing import List
from backend.infrastructure.pfc.commands.loader import CommandLoader
from backend.infrastructure.pfc.shared.models.document import SearchDocument, DocumentType


class CommandDocumentAdapter:
    """Adapter for PFC command documentation.

    Converts command and model property data from CommandLoader into
    unified SearchDocument format. This enables:
    - Unified search across commands and model properties
    - Consistent interface for search engines
    - Separation of data loading and search logic

    Design:
    - Commands + Model Properties loaded together (unified search)
    - Each document type has appropriate DocumentType enum value
    - Metadata preserves original loader information

    Usage:
        >>> # Load all command documents (commands + model properties)
        >>> documents = CommandDocumentAdapter.load_all()
        >>> len(documents)
        120  # 115 commands + 5 model properties

        >>> # Filter by type
        >>> commands = [d for d in documents if d.doc_type == DocumentType.COMMAND]
        >>> models = [d for d in documents if d.doc_type == DocumentType.MODEL_PROPERTY]
    """

    @staticmethod
    def load_all() -> List[SearchDocument]:
        """Load all command documents (commands + model properties).

        Returns:
            List of SearchDocument instances for all commands and model properties

        Example:
            >>> docs = CommandDocumentAdapter.load_all()
            >>> doc = docs[0]
            >>> doc.id
            'ball create'
            >>> doc.doc_type
            <DocumentType.COMMAND: 'command'>
            >>> doc.keywords
            ['create', 'ball', 'generate']
        """
        documents = []

        # 1. Load regular commands
        documents.extend(CommandDocumentAdapter._load_commands())

        # 2. Load model properties
        documents.extend(CommandDocumentAdapter._load_model_properties())

        return documents

    @staticmethod
    def _load_commands() -> List[SearchDocument]:
        """Load regular PFC commands.

        Returns:
            List of SearchDocument instances for commands
        """
        documents = []
        all_commands = CommandLoader.get_all_commands()

        for cmd_meta in all_commands:
            category = cmd_meta["category"]
            cmd_name = cmd_meta["name"]

            # Load full command documentation
            cmd_doc = CommandLoader.load_command_doc(category, cmd_name)
            if not cmd_doc:
                continue

            # Convert to SearchDocument
            doc = SearchDocument(
                id=f"{category} {cmd_name}",
                doc_type=DocumentType.COMMAND,
                title=cmd_doc.get("command", f"{category} {cmd_name}"),
                description=cmd_doc.get("description", ""),
                keywords=cmd_doc.get("search_keywords", []),
                category=category,
                syntax=cmd_doc.get("syntax"),
                examples=cmd_doc.get("examples", []),
                metadata={
                    "python_available": cmd_doc.get("python_sdk_alternative", {}).get("available", False),
                    "file": cmd_meta.get("file"),
                    "short_description": cmd_meta.get("short_description", "")
                }
            )
            documents.append(doc)

        return documents

    @staticmethod
    def _load_model_properties() -> List[SearchDocument]:
        """Load contact model property documents.

        Returns:
            List of SearchDocument instances for model properties
        """
        documents = []
        all_models = CommandLoader.get_all_model_properties()

        for model_meta in all_models:
            model_name = model_meta["name"]

            # Load full model documentation
            model_doc = CommandLoader.load_model_property_doc(model_name)
            if not model_doc:
                continue

            # Build description from model doc
            description = model_doc.get("description", "")

            # Add property groups information to description
            property_groups = model_doc.get("property_groups", [])
            if property_groups:
                property_names = []
                for group in property_groups:
                    for prop in group.get("properties", []):
                        property_names.append(prop.get("keyword", ""))

                if property_names:
                    description += f"\n\nProperties: {', '.join(property_names)}"

            # Convert to SearchDocument
            doc = SearchDocument(
                id=model_name,
                doc_type=DocumentType.MODEL_PROPERTY,
                title=model_doc.get("full_name", model_name),
                description=description,
                keywords=model_doc.get("search_keywords", []),
                category="contact",  # All model properties are under contact category
                syntax=None,  # Model properties don't have command syntax
                examples=None,  # Examples are in property descriptions
                metadata={
                    "file": model_meta.get("file"),
                    "priority": model_meta.get("priority", "medium"),
                    "common_use": model_meta.get("common_use", ""),
                    "property_count": sum(
                        len(group.get("properties", []))
                        for group in property_groups
                    ),
                    "typical_applications": model_doc.get("typical_applications", [])
                }
            )
            documents.append(doc)

        return documents

    @staticmethod
    def load_by_id(doc_id: str) -> SearchDocument:
        """Load a specific document by ID.

        Args:
            doc_id: Document ID (e.g., "ball create", "linear")

        Returns:
            SearchDocument instance or None if not found

        Example:
            >>> doc = CommandDocumentAdapter.load_by_id("ball create")
            >>> doc.title
            'ball create'

            >>> model_doc = CommandDocumentAdapter.load_by_id("linear")
            >>> model_doc.doc_type
            <DocumentType.MODEL_PROPERTY: 'model_property'>
        """
        # Try to parse as command (category + name)
        if " " in doc_id:
            category, cmd_name = doc_id.split(" ", 1)
            cmd_doc = CommandLoader.load_command_doc(category, cmd_name)
            if cmd_doc:
                # Build SearchDocument from command
                return SearchDocument(
                    id=doc_id,
                    doc_type=DocumentType.COMMAND,
                    title=cmd_doc.get("command", doc_id),
                    description=cmd_doc.get("description", ""),
                    keywords=cmd_doc.get("search_keywords", []),
                    category=category,
                    syntax=cmd_doc.get("syntax"),
                    examples=cmd_doc.get("examples", []),
                    metadata={
                        "python_available": cmd_doc.get("python_sdk_alternative", {}).get("available", False)
                    }
                )

        # Try as model property
        model_doc = CommandLoader.load_model_property_doc(doc_id)
        if model_doc:
            property_groups = model_doc.get("property_groups", [])
            description = model_doc.get("description", "")

            if property_groups:
                property_names = []
                for group in property_groups:
                    for prop in group.get("properties", []):
                        property_names.append(prop.get("keyword", ""))

                if property_names:
                    description += f"\n\nProperties: {', '.join(property_names)}"

            return SearchDocument(
                id=doc_id,
                doc_type=DocumentType.MODEL_PROPERTY,
                title=model_doc.get("full_name", doc_id),
                description=description,
                keywords=model_doc.get("search_keywords", []),
                category="contact",
                metadata={
                    "priority": model_doc.get("priority", "medium"),
                    "property_count": sum(
                        len(group.get("properties", []))
                        for group in property_groups
                    )
                }
            )

        return None
