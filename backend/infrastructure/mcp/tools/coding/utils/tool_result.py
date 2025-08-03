from __future__ import annotations

"""Unified Pydantic models for tool responses.

All filesystem / coding tools should return one of these models (converted to
`dict` via :pymeth:`pydantic.BaseModel.model_dump`) so that:

1.  The output schema is explicit and machine-readable for automatic docs.
2.  Frontend code can rely on a stable contract (`status`, `message`, …).
3.  Additional tool-specific payload can still be attached via `data` or
    arbitrary extra fields (``extra = "allow"``).

NOTE: We keep the model minimal for backward compatibility, allowing unknown
fields. Each tool may extend via `data` or by setting extra keys.
"""

from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, Field, ConfigDict

__all__ = ["ToolResult"]


class ToolResult(BaseModel):
    """Generic success/error wrapper for tool outputs."""

    status: Literal["success", "error"] = Field(..., description="Operation outcome")
    message: str = Field(..., description="Short user-facing summary (display)")
    llm_content: Optional[Any] = Field(
        None, description="Full content intended for LLM conversation history"
    )
    data: Optional[Dict[str, Any]] = Field(
        None, description="Structured payload specific to the tool (e.g. items, content)"
    )
    error: Optional[str] = Field(None, description="Error details when status='error'")

    # Allow tools to attach extra fields without breaking validation
    model_config = ConfigDict(extra="allow") 