"""Load internal tool definitions into the registry without FastMCP."""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Iterable
from typing import Any, Callable, Dict, Optional, Set

from backend.application.tools.base import ToolDefinition
from backend.application.tools.registry import TOOL_REGISTRY
from backend.application.tools.schema_builder import build_input_schema, get_tool_description


@dataclass(frozen=True)
class CollectedTool:
    handler: Callable[..., Any]
    tags: Set[str]
    category: Optional[str]
    annotations: Dict[str, Any]


class ToolRegistryCollector:
    """Minimal FastMCP-like interface for tool registration."""

    def __init__(self) -> None:
        self._tools: list[CollectedTool] = []

    def tool(self, *, tags: Optional[Iterable[str]] = None, annotations: Optional[Dict[str, Any]] = None, **_: Any):
        def decorator(handler: Callable[..., Any]):
            annotation_tags: Set[str] = set()
            if annotations and isinstance(annotations.get("tags"), Iterable):
                annotation_tags = set(annotations.get("tags", []))

            combined_tags = set(tags or []) | annotation_tags
            category = annotations.get("category") if annotations else None

            self._tools.append(
                CollectedTool(
                    handler=handler,
                    tags=combined_tags,
                    category=category,
                    annotations=annotations or {},
                )
            )
            return handler

        return decorator

    @property
    def tools(self) -> list[CollectedTool]:
        return self._tools


def _register_all_tools(collector: ToolRegistryCollector) -> None:
    from backend.application.tools.builtin import register_builtin_tools
    from backend.application.tools.coding import register_coding_tools
    from backend.application.tools.planning import register_planning_tools
    from backend.application.tools.agent import register_agent_tools

    register_builtin_tools(collector)
    register_coding_tools(collector)
    register_planning_tools(collector)
    register_agent_tools(collector)


async def load_tool_registry() -> None:
    """Populate internal registry with tool definitions."""
    collector = ToolRegistryCollector()
    _register_all_tools(collector)

    TOOL_REGISTRY.clear()
    for entry in collector.tools:
        tool_def = ToolDefinition(
            name=entry.handler.__name__,
            description=get_tool_description(entry.handler),
            input_schema=build_input_schema(entry.handler),
            handler=entry.handler,
            tags=entry.tags,
            category=entry.category,
            metadata={"annotations": entry.annotations, "source": "internal"},
        )
        TOOL_REGISTRY.register(tool_def, overwrite=True)

