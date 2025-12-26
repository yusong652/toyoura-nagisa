"""PFC Command Documentation Query System.

This module provides command documentation loading and formatting capabilities
for PFC commands and reference documentation.

Components:
    - DocLoader: Load command docs, model properties, and references from JSON files
    - CommandFormatter: Format command documentation as markdown
    - ReferenceFormatter: Format reference documentation (contact models, range elements)

Data Models:
    - CommandSearchResult: Search result with score and metadata
    - DocumentType: Enum for command vs model_property distinction

Note:
    For command search functionality, use the unified search system:
    - backend.infrastructure.pfc.shared.query.CommandSearch (BM25-based search)
"""

from backend.infrastructure.pfc.commands.loader import DocLoader
from backend.infrastructure.pfc.commands.command_formatter import CommandFormatter
from backend.infrastructure.pfc.commands.reference_formatter import ReferenceFormatter
from backend.infrastructure.pfc.commands.models import (
    CommandSearchResult,
    DocumentType
)

__all__ = [
    # Core components
    "DocLoader",
    "CommandFormatter",
    "ReferenceFormatter",
    # Data models
    "CommandSearchResult",
    "DocumentType"
]
