import json
from datetime import datetime
from typing import Dict, Any, Optional
from mcp.types import CallToolResult

def extract_tool_result_from_mcp(result: CallToolResult) -> Dict[str, Any]:
    """
    Extract ToolResult object from MCP CallToolResult response.
    
    Parses standardized ToolResult JSON from MCP CallToolResult.content[0].text
    and applies MCP error flags when necessary.
    
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
    """
    # Extract and parse ToolResult JSON from TextContent
    content_block = result.content[0]

    # Type guard to ensure we have TextContent with text attribute
    if hasattr(content_block, 'text') and hasattr(content_block, 'type') and content_block.type == 'text':
        text_content = content_block.text  # type: ignore
        tool_result = json.loads(text_content)
    else:
        raise ValueError(f"Expected TextContent but got {type(content_block).__name__} with type {getattr(content_block, 'type', 'unknown')}")
    
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