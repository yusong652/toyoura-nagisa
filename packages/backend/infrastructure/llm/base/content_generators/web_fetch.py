"""
Base web fetch generator for fetching and processing URL content using LLM APIs.

Handles URL content fetching with proper error handling and debugging support.
"""

from abc import abstractmethod
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from .base import BaseContentGenerator


@dataclass
class WebFetchResult:
    """Standardized result from web fetch operations."""
    status: str  # "success" or "error"
    url: str
    content: str  # Processed content (markdown or summary)
    sources: List[Dict[str, str]]  # List of {title, url} for citations
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None  # Token usage, retrieval status, etc.


class BaseWebFetchGenerator(BaseContentGenerator):
    """
    Abstract base class for web fetch content generation.

    Handles URL content fetching using LLM APIs with appropriate URL context tools.
    Fetches web content and returns structured results with proper error
    handling and debugging support.
    """

    @abstractmethod
    async def fetch_url_content(
        self,
        url: str,
        prompt: str,
    ) -> WebFetchResult:
        """
        Fetch and process content from a URL.

        Args:
            url: The URL to fetch content from
            prompt: Instructions for how to process the content

        Returns:
            WebFetchResult containing processed content or error information

        Note:
            Uses self.client for API calls (inherited from BaseContentGenerator).
            Debug mode is read from llm_settings.debug.
        """
        pass

    @staticmethod
    def validate_url(url: str) -> tuple[bool, Optional[str]]:
        """
        Validate URL format and protocol.

        Args:
            url: URL to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not url or not url.strip():
            return False, "URL cannot be empty"

        # Check for valid protocol
        if not url.startswith(('http://', 'https://')):
            return False, "URL must start with http:// or https://"

        # Basic URL structure validation
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            if not parsed.netloc:
                return False, "URL must have a valid domain"
        except Exception as e:
            return False, f"Invalid URL format: {str(e)}"

        return True, None

    @staticmethod
    def format_fetch_result(
        url: str,
        content: str,
        sources: List[Dict[str, str]],
        metadata: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None
    ) -> WebFetchResult:
        """
        Format fetch results into standardized structure.

        Args:
            url: Original URL
            content: Processed content
            sources: List of source citations
            metadata: Additional metadata
            error: Optional error message

        Returns:
            Standardized WebFetchResult
        """
        return WebFetchResult(
            status="error" if error else "success",
            url=url,
            content=content,
            sources=sources,
            error=error,
            metadata=metadata
        )

    @staticmethod
    def format_fetch_error(url: str, error_message: str) -> WebFetchResult:
        """
        Format fetch error into standardized response.

        Args:
            url: Original URL
            error_message: Error description

        Returns:
            Standardized error response
        """
        return WebFetchResult(
            status="error",
            url=url,
            content="",
            sources=[],
            error=error_message,
            metadata=None
        )

    @staticmethod
    def log_fetch_start(url: str):
        """Log fetch start."""
        print(f"[WebFetch] Fetching: {url}")

    @staticmethod
    def log_fetch_complete(url: str, content_length: int, sources_count: int):
        """Log fetch completion."""
        print(f"[WebFetch] Complete: {url} ({content_length} chars, {sources_count} sources)")

    @staticmethod
    def log_fetch_error(url: str, error: str):
        """Log fetch error."""
        print(f"[WebFetch] Error fetching {url}: {error}")
