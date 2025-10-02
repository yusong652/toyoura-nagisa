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

__all__ = ["ToolResult", "success_response", "error_response", "user_rejected_response"]


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

    # Allow tools to attach extra fields without breaking validation
    model_config = ConfigDict(extra="allow")


# -----------------------------------------------------------------------------
# Convenience functions for creating tool responses
# -----------------------------------------------------------------------------

def success_response(message: str, llm_content: Any = None, **data: Any) -> Dict[str, Any]:
    """Create a standardized success response for all MCP tools.
    
    This function provides a unified way for all tools to return success responses,
    ensuring consistent structure across coding, lifestyle, communication, and other tool categories.
    
    Args:
        message: Brief user-friendly success message for UI display
        llm_content: Content for LLM conversation context (can be any type)
        **data: Tool-specific data fields stored under the 'data' field
    
    Returns:
        Dict[str, Any]: ToolResult dictionary with status="success"
        
    Example:
        return success_response(
            "Operation completed successfully",
            llm_content="Process finished with 3 items processed",
            results=["item1", "item2", "item3"],
            count=3
        )
    """
    return ToolResult(
        status="success",
        message=message,
        llm_content=llm_content,
        data=data if data else None,
    ).model_dump()


def error_response(message: str, **data) -> Dict[str, Any]:
    """Create a standardized error response for all MCP tools.

    This function provides a unified way for all tools to return error responses,
    ensuring consistent error handling across coding, lifestyle, communication, and other tool categories.

    Args:
        message: Brief user-friendly error message for UI display
        **data: Additional error context data

    Returns:
        Dict[str, Any]: ToolResult dictionary with status="error" and parts-based llm_content

    Example:
        return error_response("Operation failed", error_code=404)
    """
    return ToolResult(
        status="error",
        message=message,
        llm_content={
            "parts": [
                {"type": "text", "text": f"<error>{message}</error>"}
            ]
        },
        data=data if data else None,
    ).model_dump()


def user_rejected_response(user_message: Optional[str] = None) -> Dict[str, Any]:
    """Create a standardized user rejection response for all MCP tools.

    This function provides a unified way for tools to return user rejection responses,
    indicating that the user chose not to proceed with the operation. This is NOT an error,
    but a valid user decision that should be communicated clearly to the LLM.

    Args:
        user_message: Optional message from the user explaining the rejection

    Returns:
        Dict[str, Any]: ToolResult dictionary with status="success" and parts-based llm_content

    Example:
        return user_rejected_response(user_message="This command looks dangerous")
    """
    # Follow Claude Code's rejection message pattern
    if user_message:
        text = f"The user doesn't want to proceed with this tool use. The tool use was rejected: {user_message}"
    else:
        text = "The user doesn't want to proceed with this tool use. The tool use was rejected."

    return ToolResult(
        status="success",  # Successfully captured user's decision
        message=text,
        llm_content={
            "parts": [
                {"type": "text", "text": text}
            ]
        },
        data=None
    ).model_dump()