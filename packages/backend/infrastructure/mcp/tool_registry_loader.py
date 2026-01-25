"""Load FastMCP tools into the internal registry."""

from __future__ import annotations

from fastmcp import FastMCP

from backend.application.tools.base import ToolDefinition
from backend.application.tools.registry import TOOL_REGISTRY


def _extract_tags(annotations: object | None) -> set[str]:
    if annotations is None:
        return set()
    tags = getattr(annotations, "tags", None)
    if not tags:
        return set()
    return set(tags)


def _extract_category(annotations: object | None) -> str | None:
    if annotations is None:
        return None
    return getattr(annotations, "category", None)


async def load_tool_registry(mcp: FastMCP) -> None:
    """Populate internal registry with FastMCP tool metadata."""
    tools = await mcp.get_tools()
    TOOL_REGISTRY.clear()

    for tool in tools.values():
        annotations = getattr(tool, "annotations", None)
        tool_def = ToolDefinition(
            name=tool.name,
            description=tool.description or "No description available",
            input_schema=getattr(tool, "parameters", None) or {},
            handler=getattr(tool, "fn", None),
            tags=_extract_tags(annotations),
            category=_extract_category(annotations),
            metadata={"source": "fastmcp"},
        )
        TOOL_REGISTRY.register(tool_def, overwrite=True)
