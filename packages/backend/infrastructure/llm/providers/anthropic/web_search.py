"""Anthropic web search provider."""

from __future__ import annotations

from typing import Dict, Any

from ..web_search.common import perform_search


async def perform_anthropic_search(
    llm_client,
    query: str,
    *,
    max_uses: int,
) -> Dict[str, Any]:
    tool_schemas = [
        {
            "type": "web_search_20250305",
            "name": "web_search",
            "max_uses": max_uses,
        }
    ]
    return await perform_search(llm_client, query, tool_schemas)
