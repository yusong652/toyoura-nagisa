"""Raw web fetch utilities for infrastructure layer."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import ipaddress
import socket
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlparse

import aiohttp


DEFAULT_TIMEOUT_SECONDS = 30
MAX_TIMEOUT_SECONDS = 120
MAX_RESPONSE_BYTES = 5 * 1024 * 1024
DEFAULT_MAX_ATTEMPTS = 2
DEFAULT_RETRY_BACKOFF_SECONDS = 0.2

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36"
)
FALLBACK_USER_AGENT = "toyoura-nagisa/1.0"
DEFAULT_ACCEPT_LANGUAGE = "en-US,en;q=0.9"

FORMAT_ACCEPT_HEADERS = {
    "markdown": "text/markdown;q=1.0, text/x-markdown;q=0.9, text/plain;q=0.8, text/html;q=0.7, */*;q=0.1",
    "text": "text/plain;q=1.0, text/markdown;q=0.9, text/html;q=0.8, */*;q=0.1",
    "html": "text/html;q=1.0, application/xhtml+xml;q=0.9, text/plain;q=0.8, text/markdown;q=0.7, */*;q=0.1",
}

RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
RETRYABLE_ERROR_TYPES = {"timeout", "client_error", "empty_body"}

BLOCKED_HOSTNAMES = {
    "localhost",
    "localhost.localdomain",
}

BLOCKED_TLD_SUFFIXES = (
    ".local",
    ".internal",
    ".localhost",
)


@dataclass
class WebFetchResponse:
    status: str
    url: str
    content: bytes
    content_type: str
    headers: Dict[str, str]
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


def _format_fetch_error(url: str, error_message: str, metadata: Optional[Dict[str, Any]] = None) -> WebFetchResponse:
    return WebFetchResponse(
        status="error",
        url=url,
        content=b"",
        content_type="",
        headers={},
        error=error_message,
        metadata=metadata,
    )


def _validate_url(url: str) -> Optional[str]:
    if not url or not url.strip():
        return "URL cannot be empty"

    if not url.startswith(("http://", "https://")):
        return "URL must start with http:// or https://"

    try:
        parsed = urlparse(url)
        if not parsed.netloc:
            return "URL must have a valid domain"
    except Exception as exc:
        return f"Invalid URL format: {exc}"

    return None


def _normalize_timeout(timeout: Optional[float]) -> float:
    if timeout is None:
        return DEFAULT_TIMEOUT_SECONDS

    try:
        value = float(timeout)
    except (TypeError, ValueError):
        return DEFAULT_TIMEOUT_SECONDS

    if value <= 0:
        return DEFAULT_TIMEOUT_SECONDS

    return min(value, MAX_TIMEOUT_SECONDS)


def _build_accept_header(format_hint: Optional[str]) -> str:
    if not format_hint:
        return "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"

    return FORMAT_ACCEPT_HEADERS.get(
        format_hint.lower(),
        "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    )


def _is_ip_blocked(ip: ipaddress._BaseAddress) -> bool:
    return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified


async def _resolve_host_ips(hostname: str) -> Tuple[str, ...]:
    loop = asyncio.get_running_loop()
    infos = await loop.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
    addresses = []
    for family, _, _, _, sockaddr in infos:
        if family == socket.AF_INET:
            addresses.append(sockaddr[0])
        elif family == socket.AF_INET6:
            addresses.append(sockaddr[0])
    return tuple(dict.fromkeys(addresses))


async def _validate_url_safety(url: str) -> Optional[str]:
    parsed = urlparse(url)
    host = parsed.hostname
    if not host:
        return "URL must have a valid host"

    normalized_host = host.lower()
    if normalized_host in BLOCKED_HOSTNAMES or normalized_host.endswith(BLOCKED_TLD_SUFFIXES):
        return "URL host is not allowed"

    try:
        ip = ipaddress.ip_address(normalized_host)
        if _is_ip_blocked(ip):
            return "URL host is not allowed"
        return None
    except ValueError:
        pass

    try:
        ips = await _resolve_host_ips(normalized_host)
    except Exception as exc:
        return f"Failed to resolve host: {exc}"

    for ip_str in ips:
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            continue
        if _is_ip_blocked(ip):
            return "URL host is not allowed"

    return None


def _should_retry(result: WebFetchResponse) -> bool:
    if result.status != "error":
        return False

    metadata = result.metadata or {}
    status_code = metadata.get("status_code")
    if isinstance(status_code, int) and status_code in RETRYABLE_STATUS_CODES:
        return True

    error_type = metadata.get("error_type")
    if error_type in RETRYABLE_ERROR_TYPES:
        return True

    return False


def _apply_retry_metadata(result: WebFetchResponse, attempts: int, used_fallback: bool) -> WebFetchResponse:
    if result.metadata is None:
        result.metadata = {}
    result.metadata["attempts"] = attempts
    result.metadata["retried"] = attempts > 1
    if used_fallback:
        result.metadata["fallback_user_agent"] = True
    return result


def _compute_backoff(attempts: int) -> float:
    return min(1.0, DEFAULT_RETRY_BACKOFF_SECONDS * attempts)


async def _read_response_with_limit(response: aiohttp.ClientResponse, max_bytes: int) -> Tuple[bytes, int]:
    total = 0
    chunks = []

    async for chunk in response.content.iter_chunked(8192):
        total += len(chunk)
        if total > max_bytes:
            raise ValueError("Response too large (exceeds 5MB limit)")
        chunks.append(chunk)

    return b"".join(chunks), total


async def _fetch_once(
    session: aiohttp.ClientSession,
    url: str,
    headers: Dict[str, str],
    max_bytes: int,
) -> WebFetchResponse:
    try:
        async with session.get(url, headers=headers, allow_redirects=True) as response:
            status_code = response.status
            response_headers = {key.lower(): value for key, value in response.headers.items()}
            content_type = response_headers.get("content-type", "")
            content_length = response_headers.get("content-length")
            final_url = str(response.url)

            if content_length:
                try:
                    if int(content_length) > max_bytes:
                        return _format_fetch_error(
                            final_url,
                            "Response too large (exceeds 5MB limit)",
                            metadata={"status_code": status_code, "content_length": content_length},
                        )
                except ValueError:
                    pass

            if status_code >= 400:
                return WebFetchResponse(
                    status="error",
                    url=final_url,
                    content=b"",
                    content_type=content_type,
                    headers=response_headers,
                    error=f"Request failed with status code: {status_code}",
                    metadata={"status_code": status_code},
                )

            content, bytes_read = await _read_response_with_limit(response, max_bytes)

            if bytes_read == 0:
                return _format_fetch_error(
                    final_url,
                    "Empty response body",
                    metadata={
                        "status_code": status_code,
                        "content_length": content_length,
                        "bytes_read": bytes_read,
                        "error_type": "empty_body",
                    },
                )

            return WebFetchResponse(
                status="success",
                url=final_url,
                content=content,
                content_type=content_type,
                headers=response_headers,
                metadata={
                    "status_code": status_code,
                    "content_length": content_length,
                    "bytes_read": bytes_read,
                },
            )
    except aiohttp.ClientError as exc:
        return _format_fetch_error(
            url,
            f"Request failed: {exc}",
            metadata={"error_type": "client_error"},
        )
    except asyncio.TimeoutError:
        return _format_fetch_error(
            url,
            "Request timed out",
            metadata={"error_type": "timeout"},
        )
    except ValueError as exc:
        return _format_fetch_error(url, str(exc))


async def fetch_url_raw(
    url: str,
    format_hint: Optional[str] = "markdown",
    timeout: Optional[float] = None,
    max_bytes: int = MAX_RESPONSE_BYTES,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
) -> WebFetchResponse:
    validation_error = _validate_url(url)
    if validation_error:
        return _format_fetch_error(url, validation_error)

    safety_error = await _validate_url_safety(url)
    if safety_error:
        return _format_fetch_error(url, safety_error, metadata={"error_type": "unsafe_url"})

    timeout_seconds = _normalize_timeout(timeout)
    accept_header = _build_accept_header(format_hint)
    headers = {
        "User-Agent": DEFAULT_USER_AGENT,
        "Accept": accept_header,
        "Accept-Language": DEFAULT_ACCEPT_LANGUAGE,
    }

    timeout_cfg = aiohttp.ClientTimeout(total=timeout_seconds)

    try:
        max_attempts = int(max_attempts)
    except (TypeError, ValueError):
        max_attempts = DEFAULT_MAX_ATTEMPTS

    if max_attempts <= 0:
        max_attempts = DEFAULT_MAX_ATTEMPTS

    used_fallback = False
    attempts = 0

    async with aiohttp.ClientSession(timeout=timeout_cfg) as session:
        for _ in range(max_attempts):
            attempts += 1
            result = await _fetch_once(session, url, headers, max_bytes)
            status_code = (result.metadata or {}).get("status_code")
            cf_mitigated = result.headers.get("cf-mitigated") if result.headers else None

            if result.status == "success":
                safety_error = await _validate_url_safety(result.url)
                if safety_error:
                    blocked = _format_fetch_error(
                        result.url,
                        safety_error,
                        metadata={"error_type": "unsafe_url"},
                    )
                    return _apply_retry_metadata(blocked, attempts, used_fallback)

                return _apply_retry_metadata(result, attempts, used_fallback)

            if status_code == 403 and cf_mitigated == "challenge" and not used_fallback:
                headers = {**headers, "User-Agent": FALLBACK_USER_AGENT}
                used_fallback = True
                if attempts >= max_attempts:
                    return _apply_retry_metadata(result, attempts, used_fallback)
                continue

            if not _should_retry(result) or attempts >= max_attempts:
                return _apply_retry_metadata(result, attempts, used_fallback)

            await asyncio.sleep(_compute_backoff(attempts))

        # TODO: Consider DNS rebinding protection for each redirect hop, allowlist ports,
        # and proxy-based isolation for stricter SSRF safeguards.

        return _apply_retry_metadata(
            _format_fetch_error(url, "Fetch failed"),
            attempts,
            used_fallback,
        )
