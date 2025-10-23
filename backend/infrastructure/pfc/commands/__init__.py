"""PFC Command Documentation Query System.

This module provides command documentation search and loading capabilities
for PFC commands, including integrated contact model properties support.

Components:
    - CommandLoader: Load command docs and model properties from JSON files
    - CommandSearcher: Search commands using keyword matching
    - CommandFormatter: Format command documentation as markdown

Data Models:
    - CommandSearchResult: Search result with score and metadata
    - DocumentType: Enum for command vs model_property distinction
"""

from backend.infrastructure.pfc.commands.loader import CommandLoader
from backend.infrastructure.pfc.commands.searcher import CommandSearcher
from backend.infrastructure.pfc.commands.formatter import CommandFormatter
from backend.infrastructure.pfc.commands.models import (
    CommandSearchResult,
    DocumentType
)

__all__ = [
    # Core components
    "CommandLoader",
    "CommandSearcher",
    "CommandFormatter",
    # Data models
    "CommandSearchResult",
    "DocumentType"
]
