"""OpenAI Codex web search provider."""

from __future__ import annotations

from typing import Dict, Any

from ..web_search.common import perform_search


async def perform_openai_codex_search(
    llm_client,
    query: str,
    *,
    thinking_level: str | None = None,
    session_id: str | None = None,
) -> Dict[str, Any]:
    # Codex endpoint requires the `external_web_access` extension field on the
    # web_search tool, unlike the public OpenAI Responses API. Without it the
    # request is rejected and the stream ends empty. See codex-rs reference:
    # https://github.com/openai/codex/blob/main/codex-rs/tools/src/tool_spec.rs
    # true = live internet search; false = cached content only.
    tool_schemas = [{"type": "web_search", "external_web_access": True}]
    return await perform_search(llm_client, query, tool_schemas, thinking_level=thinking_level, session_id=session_id)
