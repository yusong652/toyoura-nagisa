"""Google Web Search tool using Gemini SDK."""

from typing import Dict, Any
from fastmcp import FastMCP
from fastmcp.server.context import Context
from pydantic import Field
from backend.nagisa_mcp.utils.tool_result import ToolResult
from backend.chat.gemini.content_generators import WebSearchGenerator
from backend.config import get_llm_specific_config

__all__ = ["google_web_search", "register_google_web_search_tool"]

def google_web_search(
    query: str = Field(..., description="Search query to find current information on the web (e.g., 'latest AI developments', 'Python 3.12 features', 'current news about climate change')"),
    context: Context = None
) -> Dict[str, Any]:
    """
    Search the web for current information using Google Search.
    
    Retrieves up-to-date information from the web with source citations
    and comprehensive response text for the given query.
    """
    try:
        # Get Gemini client from FastAPI app state via MCP context
        fastapi_app = getattr(getattr(context, "fastmcp", None), "app", None)
        llm_client = None
        if fastapi_app is not None and hasattr(fastapi_app.state, "llm_client"):
            llm_client = fastapi_app.state.llm_client
        
        if not llm_client:
            return ToolResult(
                status="error",
                message="LLM client not available",
                error="Cannot access Gemini client from application context",
                data={"query": query}
            ).model_dump()
        
        # Get debug setting from configuration
        gemini_config = get_llm_specific_config("gemini")
        debug = gemini_config.get("debug", False)
        
        # Use WebSearchGenerator to perform search with existing client
        search_result = WebSearchGenerator.perform_web_search(
            client=llm_client.client,  # Use the raw Gemini client
            query=query,
            debug=debug
        )
        
        # Check if search was successful
        if search_result.get("status") == "error" or "error" in search_result:
            error_msg = search_result.get("error", "Unknown search error")
            return ToolResult(
                status="error",
                message=f"Web search failed: {error_msg}",
                error=error_msg,
                data={"query": query}
            ).model_dump()
        
        # Extract search results
        sources = search_result.get("sources", [])
        response_text = search_result.get("response_text", "")
        
        # Build structured response for LLM
        llm_content = {
            "operation": {
                "type": "web_search",
                "query": query
            },
            "result": {
                "response_text": response_text,
                "sources": sources,
                "total_sources": len(sources)
            },
            "summary": {
                "operation_type": "web_search",
                "success": True
            }
        }
        
        message = f"Found {len(sources)} sources for query: '{query}'"
        if response_text:
            message += f" (Response: {len(response_text)} chars)"
        
        return ToolResult(
            status="success",
            message=message,
            llm_content=llm_content,
            data=search_result
        ).model_dump()
        
    except Exception as e:
        return ToolResult(
            status="error",
            message=f"Web search error: {str(e)}",
            error=str(e),
            data={"query": query}
        ).model_dump()

def register_google_web_search_tool(mcp: FastMCP):
    """Register the Google Web Search tool with MCP server."""
    common = dict(
        tags={"builtin", "web_search", "google", "search"},
        annotations={"category": "builtin", "tags": ["builtin", "web_search", "google", "search"]}
    )
    mcp.tool(**common)(google_web_search)
