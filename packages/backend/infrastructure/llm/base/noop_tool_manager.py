"""
No-operation tool manager for LLM providers that don't support tool calling.

This manager provides empty implementations for all tool-related methods,
allowing providers like LocalLLM to work without tool support.
"""

from typing import Dict, List, Optional, Any
from backend.infrastructure.llm.base.tool_manager import BaseToolManager


class NoOpToolManager(BaseToolManager):
    """Tool manager that returns empty results for providers without tool support."""

    async def get_standardized_tools(self, session_id: str, agent_profile = 'pfc_expert') -> Dict[str, Any]:
        """Return empty tool dictionary."""
        return {}

    async def get_function_call_schemas(self, session_id: str, agent_profile = "pfc_expert") -> List[Any]:
        """Return empty schemas list."""
        return []

    async def get_schemas_for_system_prompt(self, session_id: str, agent_profile = "pfc_expert") -> Optional[List[Dict[str, Any]]]:
        """Return None for system prompt schemas."""
        return None

    async def handle_function_call(self, tool_call: Dict[str, Any], session_id: str) -> Dict[str, Any]:
        """Return error for any tool call attempt."""
        return {
            'status': 'error',
            'message': 'Tool calling not supported by this provider',
            'error': 'This LLM provider does not support tool calling'
        }