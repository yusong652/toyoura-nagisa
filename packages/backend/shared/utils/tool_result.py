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

import re
from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, Field, ConfigDict

__all__ = ["ToolResult", "success_response", "error_response", "user_rejected_response"]


# -----------------------------------------------------------------------------
# ANSI Escape Sequence Cleaning
# -----------------------------------------------------------------------------

# Precompiled regex for ANSI escape sequences (color codes, cursor control, etc.)
# Matches patterns like: \x1b[0m, \x1b[36m, \x1b[1;32m
# This is safe because ANSI codes have a well-defined format and won't match user text
ANSI_ESCAPE_PATTERN = re.compile(r"\x1b\[[0-9;]*m")

# Tool output truncation (simple fallback guard)
DEFAULT_MAX_LLM_CONTENT_CHARS = 50_000
TRUNCATION_NOTICE_TEMPLATE = "\n\n... [TRUNCATED - showing {max_chars:,} of {total_chars:,} characters] ..."


def strip_ansi_codes(text: str) -> str:
    """Remove ANSI escape sequences (color codes) from text.

    Many CLI tools (uv, npm, pytest, etc.) output colored text using ANSI escape
    sequences when they detect a TTY. These codes appear as "garbage" to LLMs
    and users when captured via subprocess.

    Args:
        text: Input string that may contain ANSI escape sequences

    Returns:
        Clean string with all ANSI codes removed

    Example:
        >>> strip_ansi_codes("\x1b[36magent-20251104-beta\x1b[39m")
        'agent-20251104-beta'

        >>> strip_ansi_codes("[36magent-20251104-beta[39m")  # Partial ANSI codes (malformed)
        '[36magent-20251104-beta[39m'  # Only removes complete sequences

    Safety:
        - Only matches standard ANSI escape sequences (\x1b[...m)
        - Won't affect normal text that happens to contain brackets
        - Based on industry-standard patterns (used by strip-ansi, etc.)
    """
    if not isinstance(text, str):
        return text
    return ANSI_ESCAPE_PATTERN.sub("", text)


def _truncate_text(
    text: str,
    max_chars: int,
    total_chars: Optional[int] = None,
    slice_chars: Optional[int] = None,
) -> str:
    slice_len = slice_chars if slice_chars is not None else max_chars
    if len(text) <= slice_len:
        return text
    total = total_chars if total_chars is not None else len(text)
    notice = TRUNCATION_NOTICE_TEMPLATE.format(max_chars=max_chars, total_chars=total)
    return f"{text[:slice_len]}{notice}"


def truncate_llm_content(content: Any, max_chars: int = DEFAULT_MAX_LLM_CONTENT_CHARS) -> Any:
    if content is None:
        return None

    if isinstance(content, str):
        return _truncate_text(content, max_chars)

    if isinstance(content, dict):
        parts = content.get("parts")
        if isinstance(parts, list):
            total_text_length = 0
            for part in parts:
                if isinstance(part, dict) and part.get("type") == "text":
                    total_text_length += len(part.get("text", ""))

            if total_text_length <= max_chars:
                return content

            remaining = max_chars
            truncated_parts = []
            truncated = False

            for part in parts:
                if not isinstance(part, dict):
                    if not truncated:
                        truncated_parts.append(part)
                    continue

                if part.get("type") != "text":
                    if not truncated:
                        truncated_parts.append(part)
                    continue

                if truncated:
                    continue

                text = part.get("text", "")
                if remaining <= 0:
                    truncated = True
                    truncated_parts.append(
                        {
                            **part,
                            "text": TRUNCATION_NOTICE_TEMPLATE.format(
                                max_chars=max_chars, total_chars=total_text_length
                            ).lstrip(),
                        }
                    )
                    continue

                if len(text) <= remaining:
                    truncated_parts.append({**part, "text": text})
                    remaining -= len(text)
                    continue

                truncated_parts.append(
                    {
                        **part,
                        "text": _truncate_text(
                            text,
                            max_chars,
                            total_text_length,
                            slice_chars=remaining,
                        ),
                    }
                )
                truncated = True

            updated = content.copy()
            updated["parts"] = truncated_parts
            return updated

    return content


def clean_llm_content(content: Any) -> Any:
    """Recursively clean ANSI codes from llm_content.

    This function handles multiple llm_content formats:
    - Simple string: "text with \x1b[36mcolor\x1b[39m"
    - Parts structure: {"parts": [{"type": "text", "text": "..."}]}
    - None or other types: passed through unchanged

    Args:
        content: llm_content value of any type

    Returns:
        Cleaned content with ANSI codes removed from all text fields

    Example:
        >>> clean_llm_content("\x1b[36mHello\x1b[39m")
        'Hello'

        >>> clean_llm_content({
        ...     "parts": [{"type": "text", "text": "\x1b[36mHello\x1b[39m"}]
        ... })
        {'parts': [{'type': 'text', 'text': 'Hello'}]}
    """
    if content is None:
        return None

    # Handle simple string content
    if isinstance(content, str):
        return truncate_llm_content(strip_ansi_codes(content))

    # Handle parts-based structure (recommended format)
    if isinstance(content, dict):
        if "parts" in content and isinstance(content["parts"], list):
            cleaned_parts = []
            for part in content["parts"]:
                if isinstance(part, dict) and "text" in part:
                    cleaned_part = part.copy()
                    cleaned_part["text"] = strip_ansi_codes(part["text"])
                    cleaned_parts.append(cleaned_part)
                else:
                    cleaned_parts.append(part)

            content = content.copy()
            content["parts"] = cleaned_parts

    return truncate_llm_content(content)


class ToolResult(BaseModel):
    """Unified success/error wrapper for all tool outputs.

    **Core Fields** (all tools must return these four fields):
    - `status`: Operation outcome ("success" | "error") - REQUIRED
    - `message`: User-facing message (success description or error details) - REQUIRED
    - `llm_content`: Structured data for LLM conversation history - REQUIRED
    - `data`: Tool-specific payload and metadata - OPTIONAL

    **llm_content Structure**:
    Must follow the parts-based format for LLM consumption:
    ```python
    llm_content = {
        "parts": [
            {"type": "text", "text": "content for LLM"},
            # Can include multiple parts
        ]
    }
    ```

    For simple text, can also be a string (auto-wrapped in parts by LLM layer).
    For errors, use `<error>` tags: `{"parts": [{"type": "text", "text": "<error>...</error>"}]}`

    **Field Usage Guidelines**:
    - `status`: "success" or "error" - identifies operation outcome
    - `message`: Brief user-friendly summary for UI display
    - `llm_content`: Structured content for LLM (parts format preferred, string accepted)
    - `data`: Additional metadata, debugging info, or tool-specific payloads

    **Usage Pattern**:
    ```python
    # Success case with parts-based llm_content
    return ToolResult(
        status="success",
        message="Found 5 matches in 3 files",
        llm_content={
            "parts": [
                {"type": "text", "text": "Search completed: 5 matches found"}
            ]
        },
        data={"total_matches": 5, "file_count": 3}
    ).model_dump()

    # Error case (error_response auto-generates parts structure)
    return error_response("Invalid pattern: Regex compilation failed")
    # Returns: llm_content = {"parts": [{"type": "text", "text": "<error>...</error>"}]}

    # Or use success_response with custom llm_content
    return success_response(
        "Operation completed",
        llm_content={"parts": [{"type": "text", "text": "Details..."}]},
        file_count=3
    )
    ```
    """

    status: Literal["success", "error"] = Field(..., description="Operation outcome: 'success' or 'error'")
    message: str = Field(..., description="Short user-facing summary suitable for display")
    llm_content: Optional[Any] = Field(
        None, description="Structured content for LLM conversation history - must match docstring schema"
    )
    data: Optional[Dict[str, Any]] = Field(
        None, description="Tool-specific payload and metadata for debugging/extension"
    )

    # Allow tools to attach extra fields without breaking validation
    model_config = ConfigDict(extra="allow")


# -----------------------------------------------------------------------------
# Convenience functions for creating tool responses
# -----------------------------------------------------------------------------


def success_response(message: str, llm_content: Any = None, **data: Any) -> Dict[str, Any]:
    """Create a standardized success response for all tools.

    This function provides a unified way for all tools to return success responses,
    ensuring consistent structure across coding, lifestyle, communication, and other tool categories.

    **Automatic ANSI Cleaning**: This function automatically removes ANSI escape sequences
    (color codes) from llm_content to prevent "garbage" characters in LLM consumption.

    Args:
        message: Brief user-friendly success message for UI display
        llm_content: Content for LLM conversation context in parts format:
            - Recommended: {"parts": [{"type": "text", "text": "..."}]}
            - Also accepts: string (will be used as-is, auto-wrapped by LLM layer)
            - ANSI codes will be automatically removed
        **data: Tool-specific data fields stored under the 'data' field

    Returns:
        Dict[str, Any]: ToolResult dictionary with four fields:
            - status: "success"
            - message: str (user-facing message)
            - llm_content: Any (cleaned value or None)
            - data: Dict[str, Any] or None

    Example:
        # Standard parts-based llm_content (recommended)
        return success_response(
            "Read file: example.txt (10 lines)",
            llm_content={"parts": [{"type": "text", "text": "file content..."}]},
            file_path="example.txt",
            lines=10
        )

        # ANSI codes are automatically cleaned
        return success_response(
            "Command executed",
            llm_content={"parts": [{"type": "text", "text": "\x1b[36moutput\x1b[39m"}]}
        )
        # Result: llm_content = {"parts": [{"type": "text", "text": "output"}]}
    """
    # Automatically clean ANSI codes from llm_content
    cleaned_content = clean_llm_content(llm_content)

    return ToolResult(
        status="success",
        message=message,
        llm_content=cleaned_content,
        data=data if data else None,
    ).model_dump()


def error_response(message: str, llm_content: Any = None, **data) -> Dict[str, Any]:
    """Create a standardized error response for all tools.

    This function provides a unified way for all tools to return error responses,
    ensuring consistent error handling across coding, lifestyle, communication, and other tool categories.

    **Automatic ANSI Cleaning**: This function automatically removes ANSI escape sequences
    (color codes) from llm_content to prevent "garbage" characters in LLM consumption.

    Args:
        message: Brief user-friendly error message with details (e.g., "File not found: example.txt")
        llm_content: Optional custom content for LLM in parts format. If not provided,
            automatically wraps message in <error> tags: {"parts": [{"type": "text", "text": "<error>...</error>"}]}
            ANSI codes will be automatically removed from custom content.
        **data: Additional error context data (optional)

    Returns:
        Dict[str, Any]: ToolResult dictionary with four fields:
            - status: "error"
            - message: str (error description)
            - llm_content: Any (cleaned custom or auto-generated with <error> tags)
            - data: Dict[str, Any] or None

    Note:
        If llm_content is not provided, this function automatically wraps the error message
        in <error> tags within a parts structure for consistent LLM error handling.

    Example:
        # Simple error (auto-wrapped in <error> tags)
        return error_response("File not found: /path/to/file.txt")
        # Returns:
        # {
        #   "status": "error",
        #   "message": "File not found: /path/to/file.txt",
        #   "llm_content": {"parts": [{"type": "text", "text": "<error>File not found...</error>"}]},
        #   "data": None
        # }

        # Custom llm_content for richer error context
        return error_response(
            "API not found",
            llm_content={"parts": [{"type": "text", "text": "⚠️ Try alternative approach..."}]},
            suggestion="Use fallback tool"
        )
    """
    # If no custom llm_content provided, use default <error> wrapped format
    if llm_content is None:
        llm_content = {"parts": [{"type": "text", "text": f"<error>{message}</error>"}]}

    # Automatically clean ANSI codes from llm_content
    cleaned_content = clean_llm_content(llm_content)

    return ToolResult(
        status="error",
        message=message,
        llm_content=cleaned_content,
        data=data if data else None,
    ).model_dump()


def user_rejected_response(user_message: Optional[str] = None, include_stop_instruction: bool = True) -> Dict[str, Any]:
    """Create a standardized user rejection response for all tools.

    This function provides a unified way for tools to return user rejection responses,
    indicating that the user chose not to proceed with the operation.

    Following Claude Code's pattern: user rejection is treated as an error from the
    tool execution perspective (operation was NOT completed), even though it's not
    a backend logic error. The <error> tag helps LLM clearly understand the operation
    did not execute, and red UI feedback shows users the action was rejected.

    Args:
        user_message: Optional message from the user explaining the rejection
        include_stop_instruction: If True (default), include "STOP what you are doing..."
            instruction. Set to False for "reject_and_tell" where agent should continue.

    Returns:
        Dict[str, Any]: ToolResult dictionary with four fields:
            - status: "error" (tool operation was not completed)
            - message: str (rejection message for UI)
            - llm_content: {"parts": [{"type": "text", "text": "<error>...</error>"}]}
            - data: None

    Example:
        return user_rejected_response(user_message="This command looks dangerous")
        # Returns:
        # {
        #   "status": "error",
        #   "message": "The user doesn't want to proceed...",
        #   "llm_content": {"parts": [{"type": "text", "text": "<error>...</error>"}]},
        #   "data": None
        # }
    """
    # Build rejection message based on whether we should include stop instruction
    if include_stop_instruction:
        # reject: User wants to stop and provide input via main input
        stop_instruction = "STOP what you are doing and wait for the user to tell you how to proceed."
    else:
        # reject_and_tell: User provided instruction, agent should continue
        stop_instruction = "Please proceed based on the user's instruction above."

    if user_message:
        text = (
            f"The user doesn't want to proceed with this tool use. "
            f"The tool use was rejected: {user_message}. "
            f"{stop_instruction}"
        )
    else:
        text = f"The user doesn't want to proceed with this tool use. The tool use was rejected. {stop_instruction}"

    # Use error_response for consistent error formatting with <error> tags
    return error_response(text)
