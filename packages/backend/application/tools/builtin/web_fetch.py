"""Web Fetch tool for retrieving and processing URL content."""

from typing import Dict, Any

from backend.application.tools.registrar import ToolRegistrar
from backend.application.tools.context import ToolContext
from pydantic import Field
from backend.shared.utils.tool_result import success_response, error_response
from backend.infrastructure.llm.providers.google import GoogleClient, GoogleConfig
from backend.application.contents.web_fetch_service import fetch_url_content

__all__ = ["web_fetch", "register_web_fetch_tool"]


async def web_fetch(
    context: ToolContext,
    url: str = Field(..., description="The URL to fetch content from"),
    prompt: str = Field(..., description="The prompt to run on the fetched content"),
) -> Dict[str, Any]:
    """
    Fetches content from a specified URL and processes it using an AI model.

    - Takes a URL and a prompt as input
    - Fetches the URL content and processes it
    - Processes the content with the prompt using a small, fast model
    - Returns the model's response about the content

    Usage notes:
      - The URL must be a fully-formed valid URL
      - The prompt should describe what information you want to extract from the page
      - This tool is read-only and does not modify any files
      - Results may be summarized if the content is very large
    """
    try:
        try:
            google_config = GoogleConfig()
            # Use GoogleClient wrapper instead of raw genai.Client
            google_client = GoogleClient(config=google_config)
        except Exception as e:
            return error_response(f"Gemini API not configured. web_fetch requires GOOGLE_API_KEY: {e}")

        result = await fetch_url_content(google_client, url=url, prompt=prompt)

        # Check result status
        if result.status == "error":
            return error_response(f"Failed to fetch URL: {result.error}")

        # Build response
        sources_info = ""
        if result.sources:
            sources_list = "\n".join(f"- [{s['title']}]({s['url']})" for s in result.sources)
            sources_info = f"\n\n**Sources:**\n{sources_list}"

        content_with_sources = result.content + sources_info

        # Token usage info for message
        token_info = ""
        if result.metadata and "token_usage" in result.metadata:
            total = result.metadata["token_usage"].get("total_tokens", 0)
            token_info = f" ({total} tokens)"

        return success_response(
            message=f"Fetched content from {url}{token_info}",
            llm_content={"parts": [{"type": "text", "text": content_with_sources}]},
            url=result.url,
            sources=result.sources,
            metadata=result.metadata,
        )

    except Exception as e:
        return error_response(f"Web fetch error: {str(e)}")


def register_web_fetch_tool(registrar: ToolRegistrar):
    """Register the Web Fetch tool with the registrar."""
    registrar.tool(
        tags={"builtin", "web_fetch", "url", "fetch"},
        annotations={"category": "builtin", "tags": ["builtin", "web_fetch", "url", "fetch"]},
    )(web_fetch)
