"""Global registry for internal tool definitions with session-scoped overrides."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable, Dict, Mapping, Optional

from backend.application.tools.base import ToolDefinition
from backend.domain.models.agent_profiles import get_tools_for_agent


def build_tool_override(
    base_tool: ToolDefinition,
    *,
    name: Optional[str] = None,
    description: Optional[str] = None,
    input_schema: Optional[Mapping[str, Any]] = None,
    handler: Optional[Callable[..., Any]] = None,
    tags: Optional[set[str]] = None,
    category: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> ToolDefinition:
    """Create a ToolDefinition override based on an existing tool.

    This helper lets callers replace specific fields (handler/schema/metadata)
    while inheriting all other attributes from the original tool definition.
    """
    merged_metadata: Optional[dict[str, Any]]
    if metadata is None:
        merged_metadata = deepcopy(base_tool.metadata) if base_tool.metadata is not None else None
    else:
        merged_metadata = deepcopy(base_tool.metadata) if base_tool.metadata is not None else {}
        merged_metadata.update(metadata)

    return ToolDefinition(
        name=name or base_tool.name,
        description=description or base_tool.description,
        input_schema=input_schema or base_tool.input_schema,
        handler=handler or base_tool.handler,
        tags=set(tags) if tags is not None else set(base_tool.tags),
        category=category if category is not None else base_tool.category,
        metadata=merged_metadata,
    )


class ToolRegistry:
    """Registry for tool definitions loaded at startup.
    
    Supports session-scoped tool overrides for tools that need per-session
    customization (e.g., trigger_skill with session-specific skill enum).
    
    Architecture:
    - Global tools: Registered at startup, shared across all sessions
    - Session overrides: Per-session tool definitions that take precedence
    - Lookup priority: session override > global tool
    """

    def __init__(self) -> None:
        self._tools: Dict[str, ToolDefinition] = {}
        # Session-scoped tool overrides: {session_id: {tool_name: ToolDefinition}}
        self._session_tools: Dict[str, Dict[str, ToolDefinition]] = {}

    def register(self, tool_def: ToolDefinition, *, overwrite: bool = False) -> None:
        """Register a global tool definition."""
        if not overwrite and tool_def.name in self._tools:
            raise ValueError(f"Tool already registered: {tool_def.name}")
        self._tools[tool_def.name] = tool_def

    def register_for_session(
        self, session_id: str, tool_def: ToolDefinition, *, overwrite: bool = True
    ) -> None:
        """Register a session-specific tool override.
        
        This tool definition will take precedence over the global one
        when fetching tools for this session.
        
        Args:
            session_id: Session identifier
            tool_def: Tool definition to register for this session
            overwrite: Whether to overwrite existing session override (default True)
        """
        if session_id not in self._session_tools:
            self._session_tools[session_id] = {}
        
        if not overwrite and tool_def.name in self._session_tools[session_id]:
            raise ValueError(f"Tool already registered for session {session_id}: {tool_def.name}")
        
        self._session_tools[session_id][tool_def.name] = tool_def

    def clear_session(self, session_id: str) -> None:
        """Clear all session-specific tool overrides for a session."""
        if session_id in self._session_tools:
            del self._session_tools[session_id]

    def clear(self) -> None:
        """Clear all registered tools (global and session-scoped)."""
        self._tools.clear()
        self._session_tools.clear()

    def get(self, name: str, session_id: Optional[str] = None) -> ToolDefinition | None:
        """Get a tool definition by name.
        
        Args:
            name: Tool name
            session_id: Optional session ID to check for session overrides
            
        Returns:
            Session override if exists, otherwise global tool, or None if not found
        """
        # Check session override first
        if session_id and session_id in self._session_tools:
            session_tool = self._session_tools[session_id].get(name)
            if session_tool is not None:
                return session_tool
        
        return self._tools.get(name)

    def all(self) -> Dict[str, ToolDefinition]:
        """Return all global tool definitions."""
        return self._tools.copy()

    def get_by_agent_profile(self, profile: str) -> Dict[str, ToolDefinition]:
        """Get tools allowed for an agent profile (global only, no session overrides)."""
        allowed = set(get_tools_for_agent(profile))
        return {name: tool for name, tool in self._tools.items() if name in allowed}

    def get_by_agent_profile_for_session(
        self, profile: str, session_id: str
    ) -> Dict[str, ToolDefinition]:
        """Get tools for an agent profile with session-specific overrides.
        
        This is the primary method for fetching tools for LLM API calls.
        Session overrides take precedence over global tools.
        
        Args:
            profile: Agent profile name
            session_id: Session identifier
            
        Returns:
            Dict of tool name -> ToolDefinition (with session overrides applied)
        """
        # Start with global tools filtered by profile
        allowed = set(get_tools_for_agent(profile))
        tools = {name: tool for name, tool in self._tools.items() if name in allowed}
        
        # Apply session overrides (only for tools in the allowed set)
        if session_id in self._session_tools:
            for name, tool in self._session_tools[session_id].items():
                if name in allowed:
                    tools[name] = tool
        
        return tools


TOOL_REGISTRY = ToolRegistry()
