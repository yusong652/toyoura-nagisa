"""Search result post-processing utilities.

This module provides utilities for post-processing search results,
including Contact API consolidation, component API consolidation,
result filtering, and metadata enrichment.
"""

from backend.infrastructure.pfc.shared.search.postprocessing.contact_consolidation import (
    consolidate_contact_apis
)
from backend.infrastructure.pfc.shared.search.postprocessing.component_consolidation import (
    consolidate_component_apis
)

__all__ = [
    "consolidate_contact_apis",
    "consolidate_component_apis"
]
