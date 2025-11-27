"""Document adapters for PFC search system.

This package provides adapters to convert raw documentation data from loaders
into unified SearchDocument models. Each adapter handles a specific document
source (commands, Python API, etc.).
"""

from backend.infrastructure.pfc.shared.adapters.command_adapter import (
    CommandDocumentAdapter
)
from backend.infrastructure.pfc.shared.adapters.api_adapter import (
    APIDocumentAdapter
)

__all__ = [
    "CommandDocumentAdapter",
    "APIDocumentAdapter"
]
