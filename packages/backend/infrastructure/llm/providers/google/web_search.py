"""Google web search provider."""

from __future__ import annotations

from typing import Dict, Any

from ..web_search.common import perform_search


async def perform_google_search(
    llm_client,
    query: str,
    *,
    max_uses: int,
    thinking_level: str | None = None,
    session_id: str | None = None,
) -> Dict[str, Any]:
    from google.genai import types

    tool_schemas = [types.Tool(google_search=types.GoogleSearch())]
    return await perform_search(llm_client, query, tool_schemas, thinking_level=thinking_level, session_id=session_id)
