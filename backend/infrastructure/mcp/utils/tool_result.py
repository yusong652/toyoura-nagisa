from __future__ import annotations

"""Unified Pydantic models for tool responses.

All tools should return one of these models (converted to `dict` via 
:pymeth:`pydantic.BaseModel.model_dump`) to ensure:

1. **Explicit Schema**: Output structure is machine-readable for automatic docs
2. **Stable Contract**: Frontend can rely on consistent `status`, `message`, etc.
3. **LLM Consistency**: Structured responses help LLM maintain coherent reasoning
4. **Extensibility**: Tools can extend via `data` or arbitrary extra fields

Each tool should:
- Use `ToolResult` for all responses
- Document the exact structure of `llm_content` in docstring
- Maintain consistent field naming across tools
- Include relevant metadata in `data` for debugging
"""

from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, Field, ConfigDict

__all__ = ["ToolResult", "success_response", "error_response"]


class ToolResult(BaseModel):
    """Unified success/error wrapper for all tool outputs.
    
    **Core Fields**:
    - `status`: Operation outcome ("success" | "error")
    - `message`: User-facing summary for display
    - `llm_content`: Structured data for LLM conversation history
    - `data`: Tool-specific payload and metadata
    - `error`: Detailed error information when status="error"
    
    **Usage Pattern**:
    ```python
    # Success case
    return ToolResult(
        status="success",
        message="Found 5 matches in 3 files",
        llm_content={"files": [...], "summary": {...}},
        data={"files": [...], "summary": {...}}
    ).model_dump()
    
    # Error case  
    return ToolResult(
        status="error",
        message="Invalid search pattern",
        error="Regex compilation failed: invalid syntax"
    ).model_dump()
    ```
    """

    status: Literal["success", "error"] = Field(
        ..., 
        description="Operation outcome: 'success' or 'error'"
    )
    message: str = Field(
        ..., 
        description="Short user-facing summary suitable for display"
    )
    llm_content: Optional[Any] = Field(
        None, 
        description="Structured content for LLM conversation history - must match docstring schema"
    )
    data: Optional[Dict[str, Any]] = Field(
        None, 
        description="Tool-specific payload and metadata for debugging/extension"
    )
    error: Optional[str] = Field(
        None, 
        description="Detailed error information when status='error'"
    )

    # Allow tools to attach extra fields without breaking validation
    model_config = ConfigDict(extra="allow")


# -----------------------------------------------------------------------------
# Convenience functions for creating tool responses
# -----------------------------------------------------------------------------

def success_response(message: str, llm_content: Any = None, **data: Any) -> Dict[str, Any]:
    """Create a success response for tools.
    
    Args:
        message: User-facing success message
        llm_content: Structured content for LLM conversation
        **data: Additional data fields to include
    
    Returns:
        Dict: ToolResult as dictionary ready for return
        
    Example:
        return success_response(
            "Event created successfully",
            llm_content="Created meeting at 2pm",
            event_id="abc123"
        )
    """
    return ToolResult(
        status="success",
        message=message,
        llm_content=llm_content,
        data=data if data else None,
    ).model_dump()


def error_response(message: str, error: Optional[str] = None) -> Dict[str, Any]:
    """Create an error response for tools.
    
    Args:
        message: User-facing error message
        error: Detailed error information (defaults to message if not provided)
    
    Returns:
        Dict: ToolResult as dictionary ready for return
        
    Example:
        return error_response(
            "Failed to create event",
            error="Invalid date format: expected YYYY-MM-DD"
        )
    """
    return ToolResult(
        status="error",
        message=message,
        error=error or message,
        llm_content=f"<error>{message}</error>"
    ).model_dump() 