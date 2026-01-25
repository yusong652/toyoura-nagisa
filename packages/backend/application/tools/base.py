"""Tool definition model for internal registry."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping


@dataclass(frozen=True)
class ToolDefinition:
    """Internal tool definition metadata."""

    name: str
    description: str
    input_schema: Mapping[str, Any]
    handler: Callable[..., Any] | None = None
    tags: set[str] = field(default_factory=set)
    category: str | None = None
    metadata: dict[str, Any] | None = None
