"""Web Search Tool Factory for Multi-LLM Support."""

from typing import Dict, Any, Optional
from backend.infrastructure.llm.base.client import LLMClientBase
from backend.application.services.contents.web_search_service import perform_web_search


class WebSearchToolFactory:
    """Factory class to handle web search across different LLM providers."""

    @staticmethod
    async def perform_web_search(
        llm_client: LLMClientBase,
        llm_type: str,
        query: str,
        max_uses: Optional[int] = None,
    ) -> Dict[str, Any]:
        return await perform_web_search(
            llm_client=llm_client,
            query=query,
            max_uses=max_uses,
        )

    @staticmethod
    def detect_llm_type(llm_client) -> str:
        provider_name = getattr(llm_client, "provider_name", None)
        if not provider_name:
            raise ValueError("LLM client is missing provider_name")
        return provider_name.lower()
