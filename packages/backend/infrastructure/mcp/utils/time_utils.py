"""
Time utility functions for MCP tools.
"""

from datetime import datetime
from typing import Optional, Union


def format_timestamp(
    timestamp: Optional[Union[float, int]] = None,
    format_str: str = "%Y-%m-%d %H:%M:%S"
) -> Optional[str]:
    """
    Format a Unix timestamp into a human-readable string.

    Args:
        timestamp: Unix timestamp (seconds since epoch). If None, returns None.
        format_str: strftime format string.

    Returns:
        Formatted datetime string, or None if timestamp is None.
    """
    if timestamp is None:
        return None

    try:
        dt = datetime.fromtimestamp(timestamp)
        return dt.strftime(format_str)
    except (ValueError, OSError, TypeError):
        return None


def format_time_range(
    start_time: Optional[Union[float, int]] = None,
    end_time: Optional[Union[float, int]] = None,
    format_str: str = "%m/%d %H:%M"
) -> str:
    """
    Format a time range into a human-readable string.

    Args:
        start_time: Start Unix timestamp. If None, shows "n/a".
        end_time: End Unix timestamp. If None, shows "running".
        format_str: strftime format string.

    Returns:
        Formatted time range string like "01/15 10:30 - 01/15 10:45" or "01/15 10:30 - running".
    """
    start_str = format_timestamp(start_time, format_str) if start_time else "n/a"

    if end_time:
        end_str = format_timestamp(end_time, format_str)
        return f"{start_str} - {end_str}"
    else:
        return f"{start_str} - running"
