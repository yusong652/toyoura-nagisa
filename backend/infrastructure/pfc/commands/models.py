"""Data models for PFC command documentation system."""

from dataclasses import dataclass
from typing import Optional, Dict, Any
from enum import Enum


class DocumentType(Enum):
    """Type of documentation item."""
    COMMAND = "command"              # PFC command (e.g., ball create, contact property)
    MODEL_PROPERTY = "model_property"  # Contact model property (e.g., linear.kn, linearpbond.pb_kn)


@dataclass
class CommandSearchResult:
    """Search result for a PFC command or model property.

    Attributes:
        name: Command name (e.g., "ball create") or property path (e.g., "linear.kn")
        score: Relevance score (0-1000, higher is better)
        doc_type: Type of document (command or model_property)
        category: Command category (e.g., "ball", "contact") or model name (e.g., "linear")
        metadata: Additional context (file path, short description, syntax, etc.)

    Example - Command:
        CommandSearchResult(
            name="ball create",
            score=950,
            doc_type=DocumentType.COMMAND,
            category="ball",
            metadata={
                "file": "commands/ball/create.json",
                "short_description": "Create a single ball with specified attributes",
                "syntax": "ball create <keyword> ..."
            }
        )

    Example - Model Property:
        CommandSearchResult(
            name="linear.kn",
            score=900,
            doc_type=DocumentType.MODEL_PROPERTY,
            category="linear",
            metadata={
                "file": "commands/contact/model-properties/linear.json",
                "property_keyword": "kn",
                "description": "Normal stiffness [force/length]"
            }
        )
    """
    name: str
    score: int
    doc_type: DocumentType
    category: str
    metadata: Optional[Dict[str, Any]] = None
