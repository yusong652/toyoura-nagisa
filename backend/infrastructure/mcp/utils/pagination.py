"""
Pagination utilities for MCP tools.

Provides reusable pagination functions for efficient context usage
when displaying long outputs from various tools.
"""

from typing import Dict, Any, Tuple


def format_paginated_output(
    output: str,
    offset: int,
    limit: int,
) -> Tuple[str, Dict[str, Any]]:
    """
    Format output with pagination for efficient context usage.

    Args:
        output: Complete output string to paginate
        offset: Line offset from newest (0 = most recent)
        limit: Number of lines to display

    Returns:
        Tuple of (formatted_output, pagination_metadata)

    Example:
        >>> output = "line1\\nline2\\nline3\\nline4\\nline5"
        >>> text, meta = format_paginated_output(output, offset=0, limit=2)
        >>> # Shows: "line4\\nline5" (most recent 2 lines)
        >>> text, meta = format_paginated_output(output, offset=2, limit=2)
        >>> # Shows: "line2\\nline3" (skip 2 newest, show next 2)
    """
    # Parse output into lines
    lines = output.split('\n') if output else []
    total_lines = len(lines)

    if total_lines == 0:
        return "(no output yet)", {
            "total_lines": 0,
            "displayed_count": 0,
            "offset": offset,
            "limit": limit,
            "line_range": "0-0",
            "has_earlier": False,
            "has_later": False
        }

    # Calculate slice indices (offset from end, newest = highest index)
    # offset=0, limit=10: show lines [-10:] (most recent 10 lines)
    # offset=10, limit=10: show lines [-20:-10] (skip 10 newest, show next 10)
    end_idx = total_lines - offset
    start_idx = max(0, total_lines - offset - limit)

    # Extract slice
    displayed = lines[start_idx:end_idx] if end_idx > start_idx else []
    displayed_count = len(displayed)

    # Keep chronological order (oldest to newest within the slice)
    # No reversal needed - natural time flow for better causality reasoning

    # Calculate line numbers for display (0 = newest)
    first_line_num = offset
    last_line_num = offset + displayed_count - 1 if displayed_count > 0 else offset

    # Format output
    output_text = '\n'.join(displayed) if displayed else "(no lines in range)"

    # Determine if there are more lines to explore
    has_earlier = start_idx > 0  # More lines before the displayed range
    has_later = offset > 0       # More lines after the displayed range (newer)

    # Build metadata
    metadata = {
        "total_lines": total_lines,
        "displayed_count": displayed_count,
        "offset": offset,
        "limit": limit,
        "line_range": f"{first_line_num}-{last_line_num}",
        "has_earlier": has_earlier,
        "has_later": has_later
    }

    return output_text, metadata
