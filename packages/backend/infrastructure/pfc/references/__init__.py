"""PFC Reference Documentation System.

This module provides reference documentation loading and formatting capabilities
for PFC reference items (contact models, range elements).

Components:
    - ReferenceLoader: Load reference docs from JSON files
    - ReferenceFormatter: Format reference documentation as markdown
"""

from backend.infrastructure.pfc.references.loader import ReferenceLoader
from backend.infrastructure.pfc.references.formatter import ReferenceFormatter

__all__ = [
    "ReferenceLoader",
    "ReferenceFormatter",
]
