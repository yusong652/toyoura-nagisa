"""MCP data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from backend.infrastructure.llm.shared.utils.tool_schema import ToolSchema


@dataclass
class MCPServerConfig:
    """Configuration for an MCP server."""

    name: str
    command: str
    args: list[str] = field(default_factory=list)
    cwd: str | None = None
    env: dict[str, str] | None = None
    enabled: bool = True
    description: str = ""
    missing_env_vars: list[str] = field(default_factory=list)


@dataclass
class MCPTool:
    """Representation of a tool from an MCP server."""

    name: str
    description: str
    input_schema: dict[str, Any]
    server_name: str

    @property
    def inputSchema(self) -> dict[str, Any]:
        """Alias for input_schema (MCP protocol uses camelCase)."""
        return self.input_schema

    def to_llm_schema(self) -> dict[str, Any]:
        """Convert to LLM function calling format."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.input_schema,
        }

    def to_tool_schema(self) -> "ToolSchema":
        """Convert to ToolSchema for LLM integration."""
        from backend.infrastructure.llm.shared.utils.tool_schema import ToolSchema

        return ToolSchema.from_mcp_tool(self)
