"""High-level query interfaces for PFC documentation search.

This module provides user-facing search APIs that abstract away
the complexity of search engines and adapters.
"""

from backend.infrastructure.pfc.shared.query.command_search import CommandSearch
from backend.infrastructure.pfc.shared.query.api_search import APISearch

__all__ = [
    'CommandSearch',
    'APISearch',
]
