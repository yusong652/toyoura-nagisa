"""Global registry for internal tool definitions."""

from __future__ import annotations

from typing import Dict

from backend.application.tools.base import ToolDefinition
from backend.domain.models.agent_profiles import get_tools_for_agent


class ToolRegistry:
    """Registry for tool definitions loaded at startup."""

    def __init__(self) -> None:
        self._tools: Dict[str, ToolDefinition] = {}

    def register(self, tool_def: ToolDefinition, *, overwrite: bool = False) -> None:
        """Register a tool definition."""
        if not overwrite and tool_def.name in self._tools:
            raise ValueError(f"Tool already registered: {tool_def.name}")
        self._tools[tool_def.name] = tool_def

    def clear(self) -> None:
        """Clear all registered tools."""
        self._tools.clear()

    def get(self, name: str) -> ToolDefinition | None:
        """Get a tool definition by name."""
        return self._tools.get(name)

    def all(self) -> Dict[str, ToolDefinition]:
        """Return all tool definitions."""
        return self._tools.copy()

    def get_by_agent_profile(self, profile: str) -> Dict[str, ToolDefinition]:
        """Get tools allowed for an agent profile."""
        allowed = set(get_tools_for_agent(profile))
        return {name: tool for name, tool in self._tools.items() if name in allowed}


TOOL_REGISTRY = ToolRegistry()
