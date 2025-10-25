"""PFC Command Documentation Query System.

This module provides command documentation loading and formatting capabilities
for PFC commands, including integrated contact model properties support.

Components:
    - CommandLoader: Load command docs and model properties from JSON files
    - CommandFormatter: Format command documentation as markdown

Data Models:
    - CommandSearchResult: Search result with score and metadata
    - DocumentType: Enum for command vs model_property distinction

Note:
    For command search functionality, use the unified search system:
    - backend.infrastructure.pfc.shared.query.CommandSearch (BM25-based search)
"""

from backend.infrastructure.pfc.commands.loader import CommandLoader
from backend.infrastructure.pfc.commands.formatter import CommandFormatter
from backend.infrastructure.pfc.commands.models import (
    CommandSearchResult,
    DocumentType
)

__all__ = [
    # Core components
    "CommandLoader",
    "CommandFormatter",
    # Data models
    "CommandSearchResult",
    "DocumentType"
]
