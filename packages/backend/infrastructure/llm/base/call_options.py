from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class CallOptions:
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    top_p: Optional[float] = None
    top_k: Optional[int] = None
    timeout: Optional[float] = None
    max_retries: Optional[int] = None
    thinking: Optional[Dict[str, Any]] = None  # Provider-specific thinking config dict
    thinking_level: Optional[str] = None  # "default", "low", or "high"


_STANDARD_OPTION_KEYS = {
    "temperature",
    "max_tokens",
    "top_p",
    "top_k",
    "timeout",
    "max_retries",
    "thinking",
    "thinking_level",
}


def parse_call_options(kwargs: Dict[str, Any]) -> CallOptions:
    if "max_output_tokens" in kwargs:
        raise ValueError("Use max_tokens; max_output_tokens is not supported")

    unknown_keys = set(kwargs) - _STANDARD_OPTION_KEYS
    if unknown_keys:
        unknown = ", ".join(sorted(unknown_keys))
        raise ValueError(f"Unsupported call options: {unknown}")

    return CallOptions(
        temperature=kwargs.get("temperature"),
        max_tokens=kwargs.get("max_tokens"),
        top_p=kwargs.get("top_p"),
        top_k=kwargs.get("top_k"),
        timeout=kwargs.get("timeout"),
        max_retries=kwargs.get("max_retries"),
        thinking=kwargs.get("thinking"),
        thinking_level=kwargs.get("thinking_level"),
    )
