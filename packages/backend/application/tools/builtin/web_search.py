"""Universal Web Search tool supporting multiple LLM providers."""

from typing import Dict, Any, cast
from backend.application.tools.registrar import ToolRegistrar
from backend.application.tools.context import ToolContext
# from fastmcp.server.context import Context
from pydantic import Field
from backend.shared.utils.tool_result import success_response, error_response
from .web_search_factory import WebSearchToolFactory

__all__ = ["web_search", "register_web_search_tool"]

async def web_search(
    context: ToolContext,
    query: str = Field(..., description="Search query to find current information on the web (e.g., 'latest AI developments', 'Python 3.12 features', 'current news about climate change')"),
    max_uses: int = Field(5, description="Maximum number of search tool uses (ignored for Gemini due to API limitations)"),
) -> Dict[str, Any]:
    """
    Search the web for current information using appropriate LLM provider.
    
    Automatically detects the LLM client type (Gemini or Anthropic) and uses
    the appropriate web search implementation. Retrieves up-to-date information
    from the web with source citations and comprehensive response text.
    """
    try:
        # Get LLM client from session context or fallback to global
        from backend.infrastructure.llm.session_client import get_session_llm_client
        
        session_id = cast(str, context.session_id)
        
        try:
            llm_client = get_session_llm_client(session_id)
        except Exception as e:
            return error_response(f"Failed to create LLM client: {e}")
        
        if not llm_client:
            return error_response(
                "LLM client not available"
            )
        
        # Auto-detect LLM type
        try:
            llm_type = WebSearchToolFactory.detect_llm_type(llm_client)
        except ValueError as e:
            return error_response(
                f"Unable to detect LLM type: {str(e)}"
            )
        
        # Use WebSearchToolFactory to perform search with detected client type
        search_result = await WebSearchToolFactory.perform_web_search(
            llm_client=llm_client,
            llm_type=llm_type,
            query=query,
            max_uses=max_uses
        )
        
        # Check if search was successful - only treat as error if error field has actual content
        error_msg = search_result.get("error")
        if search_result.get("status") == "error" or (error_msg is not None and error_msg != ""):
            return error_response(
                f"Web search failed: {error_msg}"
            )
        
        # Extract search results
        sources = search_result.get("sources", [])
        response_text = search_result.get("response_text", "")

        text_content = response_text if response_text else f"No results found for query: {query}"

        # Get LLM type for message
        llm_type = WebSearchToolFactory.detect_llm_type(llm_client)
        message = f"Found {len(sources)} sources for '{query}'"

        # Store full search result in data for reference
        return success_response(
            message=message,
            llm_content={
                "parts": [
                    {"type": "text", "text": text_content}
                ]
            },
            **search_result  # Full result with sources, response_text, etc.
        )
        
    except Exception as e:
        return error_response(
            f"Web search error: {str(e)}"
        )

def register_web_search_tool(registrar: ToolRegistrar):
    """Register the Web Search tool with the registrar."""
    registrar.tool(
        tags={"builtin", "web_search", "google", "search"},
        annotations={"category": "builtin", "tags": ["builtin", "web_search", "google", "search"]}
        )(web_search)
