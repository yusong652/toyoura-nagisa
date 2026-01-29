"""Zhipu web search provider."""

from __future__ import annotations

from typing import Dict, Any

from ..web_search.common import perform_search


async def perform_zhipu_search(
    llm_client,
    query: str,
    *,
    max_uses: int,
) -> Dict[str, Any]:
    tool_schemas = [
        {
            "type": "web_search",
            "web_search": {
                "search_query": query,
                "search_result": True,
            },
        }
    ]
    return await perform_search(
        llm_client,
        query,
        tool_schemas,
        thinking_level="default",
    )
