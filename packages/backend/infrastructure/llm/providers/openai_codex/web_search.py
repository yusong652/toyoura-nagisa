"""OpenAI Codex web search provider."""

from __future__ import annotations

from typing import Dict, Any

from ..web_search.common import perform_search


async def perform_openai_codex_search(
    llm_client,
    query: str,
    *,
    max_uses: int,
    thinking_level: str | None = None,
    session_id: str | None = None,
) -> Dict[str, Any]:
    # Codex supports web_search tool type just like standard OpenAI
    tool_schemas = [{"type": "web_search"}]
    return await perform_search(llm_client, query, tool_schemas, thinking_level=thinking_level, session_id=session_id)
