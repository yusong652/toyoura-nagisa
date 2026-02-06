"""Web Search Tool Factory for Multi-LLM Support."""

from typing import Dict, Any, Optional
from backend.infrastructure.llm.base.client import LLMClientBase
from backend.application.contents.web_search_service import perform_web_search


class WebSearchToolFactory:
    """Factory class to handle web search across different LLM providers."""

    @staticmethod
    async def perform_web_search(
        llm_client: LLMClientBase,
        query: str,
        thinking_level: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        return await perform_web_search(
            llm_client=llm_client,
            query=query,
            thinking_level=thinking_level,
            session_id=session_id,
        )
