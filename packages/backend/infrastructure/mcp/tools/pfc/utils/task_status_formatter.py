"""
Shared task status formatting utilities for PFC tools.

This module provides common task status formatting functionality used by:
- pfc_check_task_status.py: Agent tool for querying task status
- UserPfcTaskMonitor: User task status context injection

Provides unified output format for consistent LLM understanding.
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any, Tuple, List
from backend.infrastructure.mcp.utils.time_utils import format_timestamp
from .models import DEFAULT_OUTPUT_LINES, MAX_OUTPUT_LINES


# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------

# Output truncation for context injection (to avoid token bloat)
CONTEXT_INJECTION_MAX_CHARS = 2000


# -----------------------------------------------------------------------------
# Data structures
# -----------------------------------------------------------------------------

@dataclass
class TaskStatusData:
    """Structured task status data."""
    task_id: str
    status: str  # running, completed, failed, interrupted, not_found
    entry_script: Optional[str] = None
    description: Optional[str] = None
    output: Optional[str] = None
    error: Optional[str] = None
    result: Optional[Any] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    elapsed_time: Optional[float] = None
    git_commit: Optional[str] = None


@dataclass
class FormattedTaskStatus:
    """Formatted task status result."""
    text: str
    pagination: Optional[Dict[str, Any]] = None


# -----------------------------------------------------------------------------
# Pagination utilities (matching pfc_check_task_status.py)
# -----------------------------------------------------------------------------

def paginate_output(
    output: str,
    offset: int = 0,
    limit: int = DEFAULT_OUTPUT_LINES,
    filter_text: Optional[str] = None,
) -> Tuple[str, Dict[str, Any]]:
    """
    Paginate task output with optional filtering.

    Args:
        output: Raw output text
        offset: Skip N newest lines (0=most recent)
        limit: Lines to display
        filter_text: Optional text filter

    Returns:
        Tuple of (paginated_text, pagination_info)
    """
    if not output:
        return "(no output)", {
            "total_lines": 0,
            "line_range": "0-0",
            "has_earlier": False,
            "has_later": False,
        }

    lines = output.splitlines()
    total_lines = len(lines)

    # Apply filter if specified
    if filter_text:
        lines = [line for line in lines if filter_text in line]
        total_lines = len(lines)

    # Apply pagination (offset from end, newest first)
    start_idx = max(0, total_lines - limit - offset)
    end_idx = max(0, total_lines - offset)
    paginated_lines = lines[start_idx:end_idx]

    # Build pagination info
    has_earlier = start_idx > 0
    has_later = offset > 0
    line_range = f"{start_idx + 1}-{end_idx}" if paginated_lines else "0-0"

    pagination = {
        "total_lines": total_lines,
        "line_range": line_range,
        "has_earlier": has_earlier,
        "has_later": has_later,
    }

    return "\n".join(paginated_lines), pagination


# -----------------------------------------------------------------------------
# Formatting functions
# -----------------------------------------------------------------------------

def format_task_status_for_llm(
    data: TaskStatusData,
    offset: int = 0,
    limit: int = DEFAULT_OUTPUT_LINES,
    filter_text: Optional[str] = None,
) -> FormattedTaskStatus:
    """
    Format task status for LLM consumption (agent tool output).

    This is the full format used by pfc_check_task_status tool.

    Args:
        data: Task status data
        offset: Output pagination offset
        limit: Output pagination limit
        filter_text: Optional output filter

    Returns:
        FormattedTaskStatus with text and pagination info
    """
    # Paginate output
    output_text, pagination = paginate_output(
        data.output or "",
        offset=offset,
        limit=limit,
        filter_text=filter_text,
    )

    # Build navigation hint (status-aware)
    if data.status == "submitted":
        nav_hint = "use pfc_check_task_status to monitor progress"
    else:
        nav_parts = []
        if pagination["has_later"]:
            nav_parts.append(f"offset={max(0, offset - limit)} for newer")
        if pagination["has_earlier"]:
            nav_parts.append(f"offset={offset + limit} for older")
        nav_hint = " | ".join(nav_parts) if nav_parts else "all shown"

    # Build filter info
    filter_info = f", filtered by '{filter_text}'" if filter_text else ""

    # Format time info
    start_str = format_timestamp(data.start_time) or "n/a"
    end_str = format_timestamp(data.end_time) or "n/a"
    git_str = data.git_commit[:8] if data.git_commit else "n/a"
    elapsed_str = f"{data.elapsed_time:.1f}s" if data.elapsed_time else "n/a"

    # Build status-specific text
    if data.status == "submitted":
        # Just submitted, no end time yet
        time_section = f"submitted: {start_str}"
    elif data.status == "running":
        import time
        current_str = format_timestamp(time.time())
        time_section = f"started: {start_str}\ncurrent: {current_str}"
    else:
        time_section = f"started: {start_str}\nended: {end_str}"

    # Build result line (only if exists)
    result_line = f"result: {data.result}\n" if data.result is not None else ""

    # Build error section (for failed tasks)
    error_section = f"\nError:\n{data.error}" if data.error else ""

    # Compose full text
    text = (
        f"task_id: {data.task_id}\n"
        f"status: {data.status}\n"
        f"{time_section}\n"
        f"elapsed: {elapsed_str}\n"
        f"git: {git_str}\n"
        f"entry_script: {data.entry_script or 'n/a'}\n"
        f"description: {data.description or 'n/a'}\n"
        f"{result_line}\n"
        f"Output ({pagination['total_lines']} lines{filter_info}, showing {pagination['line_range']}):\n"
        f"{output_text}"
        f"{error_section}\n\n"
        f"Next: {nav_hint}"
    )

    return FormattedTaskStatus(text=text, pagination=pagination)


def format_task_status_for_context(data: TaskStatusData) -> str:
    """
    Format task status for context injection (user intent awareness).

    This is a more compact format for system-reminder injection,
    similar to how file mentions inject file content.

    Args:
        data: Task status data

    Returns:
        Formatted XML-style string for context injection
    """
    # Truncate output for context injection
    output = data.output or ""
    if len(output) > CONTEXT_INJECTION_MAX_CHARS:
        output = f"... (truncated, showing last {CONTEXT_INJECTION_MAX_CHARS} chars)\n{output[-CONTEXT_INJECTION_MAX_CHARS:]}"

    # Format metadata
    elapsed_str = f"{data.elapsed_time:.1f}s" if data.elapsed_time else "n/a"
    git_str = data.git_commit[:8] if data.git_commit else "n/a"

    lines = [
        "<pfc-task-status>",
        f"<task_id>{data.task_id}</task_id>",
        f"<status>{data.status}</status>",
        f"<entry_script>{data.entry_script or 'n/a'}</entry_script>",
        f"<description>{data.description or 'n/a'}</description>",
        f"<elapsed>{elapsed_str}</elapsed>",
        f"<git>{git_str}</git>",
    ]

    if output:
        lines.append(f"<output>\n{output}\n</output>")

    if data.error:
        lines.append(f"<error>{data.error}</error>")

    lines.append("</pfc-task-status>")

    return "\n".join(lines)


def create_task_status_data(raw_data: Dict[str, Any], task_id: str) -> TaskStatusData:
    """
    Create TaskStatusData from raw pfc-server response.

    Args:
        raw_data: Raw data dict from pfc-server
        task_id: Task ID

    Returns:
        Structured TaskStatusData
    """
    return TaskStatusData(
        task_id=task_id,
        status=raw_data.get("status", "unknown"),
        entry_script=raw_data.get("entry_script", raw_data.get("script_path")),
        description=raw_data.get("description"),
        output=raw_data.get("output"),
        error=raw_data.get("error"),
        result=raw_data.get("result"),
        start_time=raw_data.get("start_time"),
        end_time=raw_data.get("end_time"),
        elapsed_time=raw_data.get("elapsed_time"),
        git_commit=raw_data.get("git_commit"),
    )
