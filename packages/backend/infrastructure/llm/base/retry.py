import asyncio
from typing import AsyncGenerator, Awaitable, Callable, Optional, TypeVar


T = TypeVar("T")


class RateLimitError(Exception):
    def __init__(self, message: str, retry_after: Optional[float] = None):
        super().__init__(message)
        self.retry_after = retry_after


def is_retryable_error(error: Exception) -> bool:
    if isinstance(error, RateLimitError):
        return True

    error_str = str(error).lower()
    error_type = type(error).__name__.lower()

    retryable_patterns = [
        "timeout",
        "timed out",
        "connection",
        "network",
        "reset",
        "broken pipe",
        "eof",
        "read error",
        "rate limit",
        "resource_exhausted",
        "retrydelay",
        "429",
    ]

    for pattern in retryable_patterns:
        if pattern in error_str:
            return True

    retryable_types = ["timeout", "connection", "network"]
    for pattern in retryable_types:
        if pattern in error_type:
            return True

    return False


async def run_with_retries(
    call: Callable[[], Awaitable[T]],
    *,
    max_retries: int,
    timeout: Optional[float] = None,
    base_delay: float = 1.0,
    debug: bool = False,
) -> T:
    attempt = 0

    while True:
        try:
            if timeout is None:
                return await call()
            return await asyncio.wait_for(call(), timeout=timeout)
        except Exception as exc:
            retryable = is_retryable_error(exc)
            if debug:
                print(f"[DEBUG] LLM call failed (attempt {attempt + 1}/{max_retries + 1}): {exc}")

            if not retryable or attempt >= max_retries:
                raise

            retry_after = getattr(exc, "retry_after", None)
            delay = retry_after if isinstance(retry_after, (int, float)) else base_delay * (2**attempt)
            if debug:
                print(f"[DEBUG] LLM retrying in {delay}s")

            attempt += 1
            await asyncio.sleep(delay)


async def stream_with_retries(
    stream_factory: Callable[[], AsyncGenerator[T, None]],
    *,
    max_retries: int,
    timeout: Optional[float] = None,
    base_delay: float = 1.0,
    debug: bool = False,
) -> AsyncGenerator[T, None]:
    attempt = 0

    while True:
        had_chunk = False
        try:
            stream = stream_factory()
            iterator = stream.__aiter__()

            if timeout is not None:
                try:
                    first_chunk = await asyncio.wait_for(iterator.__anext__(), timeout=timeout)
                except StopAsyncIteration:
                    return

                had_chunk = True
                yield first_chunk

            async for chunk in iterator:
                had_chunk = True
                yield chunk

            return
        except Exception as exc:
            retryable = is_retryable_error(exc)
            if debug:
                print(f"[DEBUG] LLM streaming failed (attempt {attempt + 1}/{max_retries + 1}): {exc}")

            if had_chunk or not retryable or attempt >= max_retries:
                raise

            retry_after = getattr(exc, "retry_after", None)
            delay = retry_after if isinstance(retry_after, (int, float)) else base_delay * (2**attempt)
            if debug:
                print(f"[DEBUG] LLM retrying stream in {delay}s")

            attempt += 1
            await asyncio.sleep(delay)
