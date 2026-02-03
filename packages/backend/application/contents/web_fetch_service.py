"""Web Fetch Service - Application layer URL content retrieval."""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from backend.infrastructure.web_fetch.client import fetch_url_raw
from backend.infrastructure.web_fetch.formatter import format_web_content


@dataclass
class WebFetchResult:
    status: str
    url: str
    content: str
    sources: List[Dict[str, str]]
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


def _format_fetch_error(url: str, error_message: str, metadata: Optional[Dict[str, Any]] = None) -> WebFetchResult:
    return WebFetchResult(
        status="error",
        url=url,
        content="",
        sources=[],
        error=error_message,
        metadata=metadata,
    )


async def fetch_url_content(
    url: str,
    output_format: str = "markdown",
    timeout: Optional[float] = None,
) -> WebFetchResult:
    raw_result = await fetch_url_raw(url, format_hint=output_format, timeout=timeout)
    if raw_result.status == "error":
        return _format_fetch_error(raw_result.url, raw_result.error or "Fetch failed", raw_result.metadata)

    formatted = format_web_content(raw_result.content, raw_result.content_type, output_format)
    metadata: Dict[str, Any] = {}
    if raw_result.metadata:
        metadata.update(raw_result.metadata)
    if formatted.metadata:
        metadata.update(formatted.metadata)
    if formatted.title:
        metadata["title"] = formatted.title

    return WebFetchResult(
        status="success",
        url=raw_result.url,
        content=formatted.content,
        sources=[],
        metadata=metadata or None,
    )
