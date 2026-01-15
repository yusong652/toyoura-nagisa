"""
Gemini-specific web fetch generator.

Fetches and processes URL content using Gemini's urlContext tool.
"""

from typing import Dict, Any, List
from google.genai import types

from backend.config import get_llm_settings
from backend.infrastructure.llm.base.content_generators.web_fetch import (
    BaseWebFetchGenerator,
    WebFetchResult,
)
from backend.infrastructure.llm.providers.google.config import get_google_client_config
from backend.infrastructure.llm.providers.google.response_processor import GoogleResponseProcessor


class GoogleWebFetchGenerator(BaseWebFetchGenerator):
    """
    Gemini-specific web fetch using urlContext tool.

    Uses Gemini's native URL context capability to fetch and process web content.
    Supports up to 20 URLs per request with automatic content extraction.
    """

    async def fetch_url_content(
        self,
        url: str,
        prompt: str,
    ) -> WebFetchResult:
        """
        Fetch and process content from a URL using Gemini's urlContext tool.

        Args:
            url: The URL to fetch content from
            prompt: Instructions for how to process the content

        Returns:
            WebFetchResult containing processed content or error information
        """
        try:
            # Validate URL
            is_valid, error_msg = self.validate_url(url)
            if not is_valid:
                return self.format_fetch_error(url, error_msg or "Invalid URL")

            self.log_fetch_start(url)

            # Get configuration
            google_client_config = get_google_client_config()
            llm_settings = get_llm_settings()
            google_llm_config = llm_settings.get_google_config()

            # Use secondary model for URL fetching (reduces primary model RPM usage)
            model = google_llm_config.secondary_model

            # Build the user prompt with URL
            user_prompt = f"{prompt}\n\nURL: {url}"

            # Configure with urlContext tool
            # Note: urlContext is incompatible with function calling
            fetch_config = types.GenerateContentConfig(
                tools=[types.Tool(url_context=types.UrlContext())],
                safety_settings=google_client_config.safety_settings.to_gemini_format(),
            )

            # Call Gemini API with urlContext
            response = await self.client.aio.models.generate_content(
                model=model,
                contents=user_prompt,
                config=fetch_config
            )

            return self._process_response(response, url)

        except Exception as e:
            import traceback
            error_msg = f"Error fetching URL content: {str(e)}"
            self.log_fetch_error(url, error_msg)
            print(f"[WebFetch] Traceback:\n{traceback.format_exc()}")
            return self.format_fetch_error(url, error_msg)

    def _process_response(self, response, url: str) -> WebFetchResult:
        """Process Gemini API response and extract content."""
        if not response.candidates:
            return self.format_fetch_error(url, "No response candidates")

        candidate = response.candidates[0]

        # Check URL retrieval status from metadata
        url_context_meta = getattr(candidate, 'url_context_metadata', None)
        if url_context_meta and url_context_meta.url_metadata:
            for meta in url_context_meta.url_metadata:
                status = getattr(meta, 'url_retrieval_status', None)
                if status and status != 'URL_RETRIEVAL_STATUS_SUCCESS':
                    return self.format_fetch_error(
                        url,
                        f"URL retrieval failed with status: {status}"
                    )

        # Extract response text
        response_text = GoogleResponseProcessor.extract_text_content(response)
        if not response_text:
            return self.format_fetch_error(url, "No content extracted from URL")

        # Extract sources and metadata
        sources = self._extract_sources(candidate)
        metadata = self._build_metadata(response, url_context_meta)

        self.log_fetch_complete(url, len(response_text), len(sources))

        return self.format_fetch_result(
            url=url,
            content=response_text,
            sources=sources,
            metadata=metadata
        )

    def _extract_sources(self, candidate) -> List[Dict[str, str]]:
        """Extract source citations from grounding metadata."""
        sources = []

        grounding_meta = getattr(candidate, 'grounding_metadata', None)
        if not grounding_meta:
            return sources

        grounding_chunks = getattr(grounding_meta, 'grounding_chunks', None)
        if not grounding_chunks:
            return sources

        for chunk in grounding_chunks:
            web_info = getattr(chunk, 'web', None)
            if web_info:
                sources.append({
                    'title': getattr(web_info, 'title', 'Untitled'),
                    'url': getattr(web_info, 'uri', '')
                })

        return sources

    def _build_metadata(self, response, url_context_meta) -> Dict[str, Any]:
        """Build metadata dictionary from response."""
        metadata = {}

        # Add usage metadata
        usage_meta = getattr(response, 'usage_metadata', None)
        if usage_meta:
            metadata['token_usage'] = {
                'prompt_tokens': getattr(usage_meta, 'prompt_token_count', 0),
                'tool_use_tokens': getattr(usage_meta, 'tool_use_prompt_token_count', 0),
                'output_tokens': getattr(usage_meta, 'candidates_token_count', 0),
                'total_tokens': getattr(usage_meta, 'total_token_count', 0),
            }

        # Add URL retrieval info
        if url_context_meta and url_context_meta.url_metadata:
            metadata['url_retrieval'] = []
            for meta in url_context_meta.url_metadata:
                metadata['url_retrieval'].append({
                    'retrieved_url': getattr(meta, 'retrieved_url', ''),
                    'status': getattr(meta, 'url_retrieval_status', 'unknown'),
                })

        return metadata
