"""Web Fetch tool for retrieving and processing URL content."""

from typing import Any, Dict, Optional

from backend.application.tools.registrar import ToolRegistrar
from backend.application.tools.context import ToolContext
from pydantic import Field
from backend.shared.utils.tool_result import success_response, error_response
from backend.application.contents.web_fetch_service import fetch_url_content

__all__ = ["web_fetch", "register_web_fetch_tool"]


async def web_fetch(
    context: ToolContext,
    url: str = Field(..., description="The URL to fetch content from"),
    format: str = Field(
        "markdown",
        description="The format to return the content in (text, markdown, or html). Defaults to markdown.",
    ),
    timeout: Optional[float] = Field(None, description="Optional timeout in seconds (max 120)"),
) -> Dict[str, Any]:
    """
    Fetches content from a specified URL and converts it to the requested format.

    - Takes a URL and optional format as input
    - Fetches the URL content, converts to requested format (markdown by default)
    - Returns the content in the specified format

    Usage notes:
      - The URL must be a fully-formed valid URL
      - Format options: "markdown" (default), "text", or "html"
      - This tool is read-only and does not modify any files
      - Results may be summarized if the content is very large
    """
    try:
        _ = context
        normalized_format = (format or "markdown").lower()
        if normalized_format not in {"markdown", "text", "html"}:
            return error_response("Invalid format. Use 'markdown', 'text', or 'html'.")

        result = await fetch_url_content(url=url, output_format=normalized_format, timeout=timeout)

        # Check result status
        if result.status == "error":
            return error_response(f"Failed to fetch URL: {result.error}")

        # Build response
        sources_info = ""
        if result.sources:
            sources_list = "\n".join(f"- [{s['title']}]({s['url']})" for s in result.sources)
            sources_info = f"\n\n**Sources:**\n{sources_list}"

        content_with_sources = result.content + sources_info

        return success_response(
            message=f"Fetched content from {url}",
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
