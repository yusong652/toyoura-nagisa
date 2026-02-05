"""
Web Search Service - Application layer web search orchestration.
"""

from typing import Dict, Any, Optional

from backend.infrastructure.llm.providers.web_search.common import get_default_max_uses
from backend.infrastructure.llm.providers.anthropic.web_search import perform_anthropic_search
from backend.infrastructure.llm.providers.google.web_search import perform_google_search
from backend.infrastructure.llm.providers.moonshot.web_search import perform_moonshot_search
from backend.infrastructure.llm.providers.openai.web_search import perform_openai_search
from backend.infrastructure.llm.providers.openai_codex.web_search import perform_openai_codex_search
from backend.infrastructure.llm.providers.zhipu.web_search import perform_zhipu_search


async def perform_web_search(
    llm_client,
    query: str,
    max_uses: Optional[int] = None,
) -> Dict[str, Any]:
    provider_name = _get_provider_name(llm_client)
    max_uses_value: int = max_uses if max_uses is not None else get_default_max_uses(provider_name)

    if provider_name in ["google", "google-gemini-cli"]:
        return await perform_google_search(llm_client, query, max_uses=max_uses_value)
    if provider_name == "anthropic":
        return await perform_anthropic_search(llm_client, query, max_uses=max_uses_value)
    if provider_name == "openai":
        return await perform_openai_search(llm_client, query, max_uses=max_uses_value)
    if provider_name == "openai-codex":
        return await perform_openai_codex_search(llm_client, query, max_uses=max_uses_value)
    if provider_name == "moonshot":
        return await perform_moonshot_search(llm_client, query, max_uses=max_uses_value)
    if provider_name == "zhipu":
        return await perform_zhipu_search(llm_client, query, max_uses=max_uses_value)

    return {
        "error": f"Unsupported LLM type: {provider_name}",
        "query": query,
    }


def _get_provider_name(llm_client) -> str:
    provider_name = getattr(llm_client, "provider_name", None)
    if not provider_name:
        raise ValueError("LLM client is missing provider_name")
    return provider_name.lower()
