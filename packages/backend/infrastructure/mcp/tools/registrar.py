"""Protocol for registering tools without FastMCP dependency."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any, Dict, Optional, Protocol


class ToolRegistrar(Protocol):
    def tool(
        self,
        *,
        tags: Optional[Iterable[str]] = None,
        annotations: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        ...
