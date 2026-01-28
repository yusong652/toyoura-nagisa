"""
Web Fetch Service - Application layer URL content retrieval.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from backend.infrastructure.llm.providers.google.config import GoogleConfig
from backend.infrastructure.llm.providers.google.response_processor import GoogleResponseProcessor


@dataclass
class WebFetchResult:
    status: str
    url: str
    content: str
    sources: List[Dict[str, str]]
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


def _validate_url(url: str) -> tuple[bool, Optional[str]]:
    if not url or not url.strip():
        return False, "URL cannot be empty"

    if not url.startswith(("http://", "https://")):
        return False, "URL must start with http:// or https://"

    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        if not parsed.netloc:
            return False, "URL must have a valid domain"
    except Exception as exc:
        return False, f"Invalid URL format: {str(exc)}"

    return True, None


def _format_fetch_result(
    url: str,
    content: str,
    sources: List[Dict[str, str]],
    metadata: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None,
) -> WebFetchResult:
    return WebFetchResult(
        status="error" if error else "success",
        url=url,
        content=content,
        sources=sources,
        error=error,
        metadata=metadata,
    )


def _format_fetch_error(url: str, error_message: str) -> WebFetchResult:
    return WebFetchResult(
        status="error",
        url=url,
        content="",
        sources=[],
        error=error_message,
        metadata=None,
    )


def _log_fetch_start(url: str) -> None:
    print(f"[WebFetch] Fetching: {url}")


def _log_fetch_complete(url: str, content_length: int, sources_count: int) -> None:
    print(f"[WebFetch] Complete: {url} ({content_length} chars, {sources_count} sources)")


def _log_fetch_error(url: str, error: str) -> None:
    print(f"[WebFetch] Error fetching {url}: {error}")


def _extract_sources(candidate) -> List[Dict[str, str]]:
    sources: List[Dict[str, str]] = []
    grounding_meta = getattr(candidate, "grounding_metadata", None)
    if not grounding_meta:
        return sources

    grounding_chunks = getattr(grounding_meta, "grounding_chunks", None)
    if not grounding_chunks:
        return sources

    for chunk in grounding_chunks:
        web_info = getattr(chunk, "web", None)
        if web_info:
            sources.append({
                "title": getattr(web_info, "title", "Untitled"),
                "url": getattr(web_info, "uri", ""),
            })

    return sources


def _build_metadata(response, url_context_meta) -> Dict[str, Any]:
    metadata: Dict[str, Any] = {}
    usage_meta = getattr(response, "usage_metadata", None)
    if usage_meta:
        metadata["token_usage"] = {
            "prompt_tokens": getattr(usage_meta, "prompt_token_count", 0),
            "tool_use_tokens": getattr(usage_meta, "tool_use_prompt_token_count", 0),
            "output_tokens": getattr(usage_meta, "candidates_token_count", 0),
            "total_tokens": getattr(usage_meta, "total_token_count", 0),
        }

    if url_context_meta and url_context_meta.url_metadata:
        metadata["url_retrieval"] = []
        for meta in url_context_meta.url_metadata:
            metadata["url_retrieval"].append({
                "retrieved_url": getattr(meta, "retrieved_url", ""),
                "status": getattr(meta, "url_retrieval_status", "unknown"),
            })

    return metadata


async def fetch_url_content(llm_client, url: str, prompt: str) -> WebFetchResult:
    is_valid, error_msg = _validate_url(url)
    if not is_valid:
        return _format_fetch_error(url, error_msg or "Invalid URL")

    _log_fetch_start(url)

    from backend.infrastructure.llm.providers.google.config import GoogleConfig
    google_config = GoogleConfig()

    from google.genai import types

    model = google_config.secondary_model
    user_prompt = f"{prompt}\n\nURL: {url}"

    fetch_config = types.GenerateContentConfig(
        tools=[types.Tool(url_context=types.UrlContext())],
        safety_settings=google_config.safety_settings.to_gemini_format(),
    )

    response = await llm_client.client.aio.models.generate_content(
        model=model,
        contents=user_prompt,
        config=fetch_config,
    )

    if not response.candidates:
        return _format_fetch_error(url, "No response candidates")

    candidate = response.candidates[0]
    url_context_meta = getattr(candidate, "url_context_metadata", None)
    if url_context_meta and url_context_meta.url_metadata:
        for meta in url_context_meta.url_metadata:
            status = getattr(meta, "url_retrieval_status", None)
            if status and status != "URL_RETRIEVAL_STATUS_SUCCESS":
                return _format_fetch_error(url, f"URL retrieval failed with status: {status}")

    response_text = GoogleResponseProcessor.extract_text_content(response)
    if not response_text:
        return _format_fetch_error(url, "No content extracted from URL")

    sources = _extract_sources(candidate)
    metadata = _build_metadata(response, url_context_meta)

    _log_fetch_complete(url, len(response_text), len(sources))

    return _format_fetch_result(
        url=url,
        content=response_text,
        sources=sources,
        metadata=metadata,
    )
