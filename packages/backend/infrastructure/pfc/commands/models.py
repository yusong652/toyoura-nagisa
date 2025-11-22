"""Data models for PFC command documentation system.

DEPRECATED: This module is kept for backward compatibility only.
New code should use backend.infrastructure.pfc.shared.search.models instead.
"""

# Import from unified models for backward compatibility
from backend.infrastructure.pfc.shared.search.models import (
    SearchResult as CommandSearchResult,
    DocumentType,
    SearchStrategy
)

# Re-export for backward compatibility
__all__ = [
    "CommandSearchResult",
    "DocumentType",
    "SearchStrategy"
]
