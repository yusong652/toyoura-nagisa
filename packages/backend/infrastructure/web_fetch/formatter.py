"""Web fetch content formatting utilities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from bs4 import BeautifulSoup
import trafilatura


@dataclass
class WebFormatResult:
    content: str
    title: Optional[str]
    metadata: Dict[str, Any]


def _extract_charset(content_type: str) -> Optional[str]:
    if not content_type:
        return None

    parts = content_type.split(";")
    for part in parts[1:]:
        part = part.strip()
        if part.lower().startswith("charset="):
            return part.split("=", 1)[1].strip()

    return None


def _decode_bytes(content: bytes, content_type: str) -> str:
    encoding = _extract_charset(content_type) or "utf-8"
    try:
        return content.decode(encoding, errors="replace")
    except LookupError:
        return content.decode("utf-8", errors="replace")


def _extract_title(html: str) -> Optional[str]:
    try:
        soup = BeautifulSoup(html, "html.parser")
        if soup.title and soup.title.string:
            return soup.title.string.strip()
    except Exception:
        return None
    return None


def _html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "iframe", "object", "embed"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())


def _html_to_markdown(html: str) -> Optional[str]:
    try:
        return trafilatura.extract(html, output_format="markdown")
    except Exception:
        return None


def _html_to_plaintext(html: str) -> Optional[str]:
    try:
        return trafilatura.extract(html, output_format="txt")
    except Exception:
        return None


def format_web_content(
    content: bytes,
    content_type: str,
    output_format: str,
) -> WebFormatResult:
    decoded = _decode_bytes(content, content_type)
    normalized_format = (output_format or "markdown").lower()
    normalized_type = (content_type or "").lower()
    title = None
    metadata: Dict[str, Any] = {
        "source_content_type": content_type,
        "output_format": normalized_format,
    }

    if "text/html" in normalized_type or "application/xhtml" in normalized_type:
        title = _extract_title(decoded)

        if normalized_format == "html":
            return WebFormatResult(content=decoded, title=title, metadata=metadata)

        if normalized_format == "markdown":
            markdown = _html_to_markdown(decoded)
            if markdown:
                return WebFormatResult(content=markdown, title=title, metadata=metadata)
            metadata["fallback"] = "html_text"
            return WebFormatResult(content=_html_to_text(decoded), title=title, metadata=metadata)

        if normalized_format == "text":
            text = _html_to_plaintext(decoded)
            if text:
                return WebFormatResult(content=text, title=title, metadata=metadata)
            metadata["fallback"] = "html_text"
            return WebFormatResult(content=_html_to_text(decoded), title=title, metadata=metadata)

        return WebFormatResult(content=decoded, title=title, metadata=metadata)

    if normalized_format == "html":
        return WebFormatResult(content=decoded, title=title, metadata=metadata)

    return WebFormatResult(content=decoded, title=title, metadata=metadata)
