import json
from datetime import datetime
from typing import Dict, Any, Optional, Tuple
from mcp.types import CallToolResult


def _parse_mcp_text_content(text: str) -> Tuple[bool, Dict[str, Any]]:
    """
    Parse MCP text content as JSON or detect plain text error.

    Args:
        text: Text content from MCP CallToolResult

    Returns:
        Tuple[bool, Dict[str, Any]]: (is_json, result)
            - is_json: True if successfully parsed as JSON
            - result: Parsed dict if JSON, empty dict if plain text

    Note:
        This function handles two types of MCP responses:
        1. Normal responses: JSON-formatted ToolResult from tools
        2. Validation errors: Plain text error messages from FastMCP
    """
    try:
        parsed = json.loads(text)
        return (True, parsed)
    except json.JSONDecodeError:
        # Not JSON - FastMCP validation error or other plain text
        return (False, {})


def _format_mcp_validation_error(error_text: str) -> Dict[str, Any]:
    """
    Format MCP validation error as friendly ToolResult for LLM.

    When FastMCP parameter validation fails, it returns plain text errors instead
    of JSON. This function converts those errors into standardized ToolResult format
    that LLMs can understand and use to correct their tool calls.

    Args:
        error_text: Raw error text from FastMCP (e.g., "ValidationError: ...")

    Returns:
        Dict[str, Any]: ToolResult dictionary with:
            - status: "error"
            - message: User-facing error summary
            - llm_content: Structured content for LLM with helpful guidance

    Example:
        Input: "ValidationError: 1 validation error for call[pfc_execute_command]\\n..."
        Output: ToolResult with formatted error message guiding LLM to fix parameters
    """
    from backend.infrastructure.mcp.utils.tool_result import error_response

    # Extract tool name if present in error text
    tool_name = "unknown tool"
    if "call[" in error_text and "]" in error_text:
        try:
            start = error_text.index("call[") + 5
            end = error_text.index("]", start)
            tool_name = error_text[start:end]
        except (ValueError, IndexError):
            pass

    # Format friendly error message for LLM
    error_message = (
        f"Tool parameter validation failed: {tool_name}\n\n"
        f"MCP Validation Error:\n{error_text}\n\n"
        f"Common causes:\n"
        f"  • Provided a parameter that doesn't exist in the tool schema\n"
        f"  • Missing a required parameter\n"
        f"  • Parameter value has incorrect type (e.g., string instead of number)\n"
        f"  • Parameter value doesn't match constraints\n\n"
        f"Action required:\n"
        f"  1. Check the tool schema to see accepted parameters\n"
        f"  2. Verify all required parameters are provided\n"
        f"  3. Ensure parameter types match the schema\n"
        f"  4. Retry with corrected parameters"
    )

    return error_response(
        error_message,
        llm_content={
            "parts": [{
                "type": "text",
                "text": error_message
            }]
        }
    )


def extract_tool_result_from_mcp(result: CallToolResult) -> Dict[str, Any]:
    """
    Extract ToolResult object from MCP CallToolResult response.

    Parses standardized ToolResult JSON from MCP CallToolResult.content[0].text
    and applies MCP error flags when necessary. Handles both normal JSON responses
    and plain text validation errors from FastMCP.

    Args:
        result: MCP CallToolResult object with structure:
            - content: List[ContentBlock] containing TextContent
            - isError: bool indicating MCP-level error

    Returns:
        Dict[str, Any]: ToolResult dictionary with structure:
            - status: Literal["success", "error"] - Operation outcome
            - message: str - User-facing summary for display
            - llm_content: Optional[Any] - Structured data for LLM conversation
            - data: Optional[Dict[str, Any]] - Tool-specific payload and metadata
            - error: Optional[str] - Detailed error info when status="error"
            - is_error: bool - Added when MCP marks result as error

    Note:
        All tools return ToolResult.model_dump() as standardized JSON,
        ensuring consistent structure across the MCP ecosystem.

        When FastMCP parameter validation fails, it returns plain text errors
        instead of JSON. This function automatically converts those to friendly
        ToolResult format for LLM consumption.
    """
    # Extract text content from MCP response
    content_block = result.content[0]

    # Type guard to ensure we have TextContent with text attribute
    if not (hasattr(content_block, 'text') and hasattr(content_block, 'type') and content_block.type == 'text'):
        raise ValueError(
            f"Expected TextContent but got {type(content_block).__name__} "
            f"with type {getattr(content_block, 'type', 'unknown')}"
        )

    text_content = content_block.text  # type: ignore

    # Parse text content (JSON or plain text error)
    is_json, tool_result = _parse_mcp_text_content(text_content)

    if not is_json:
        # Plain text error - convert to friendly ToolResult format
        tool_result = _format_mcp_validation_error(text_content)

    # Apply MCP error flag if present
    if result.isError:
        tool_result["is_error"] = True

    return tool_result

def ensure_future_datetime(dt: datetime, now: Optional[datetime] = None) -> datetime:
    """
    Ensure datetime is in the future by adjusting year if necessary.
    
    Automatically adjusts the year to current or next year when the provided
    datetime falls before the reference time, ensuring returned datetime
    is always in the future.
    
    Args:
        dt: Target datetime to adjust
        now: Reference datetime (defaults to current time with dt's timezone)
    
    Returns:
        datetime: Adjusted datetime guaranteed to be >= now
        
    Example:
        # If now is 2024-06-15 and dt is 2024-01-01
        # Returns 2025-01-01 (next year)
    """
    if now is None:
        now = datetime.now(dt.tzinfo)
    if dt >= now:
        return dt
    dt_this_year = dt.replace(year=now.year)
    if dt_this_year >= now:
        return dt_this_year
    dt_next_year = dt.replace(year=now.year + 1)
    return dt_next_year