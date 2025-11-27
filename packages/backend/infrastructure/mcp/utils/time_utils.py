"""Time utilities - Timezone detection and time formatting functions."""

import datetime
from typing import Optional
from timezonefinder import TimezoneFinder

# Initialize TimezoneFinder instance
_tf = TimezoneFinder()

def get_timezone_from_location(latitude: float, longitude: float) -> Optional[str]:
    """Convert latitude/longitude to timezone string using TimezoneFinder.

    Args:
        latitude: Latitude coordinate
        longitude: Longitude coordinate

    Returns:
        Timezone string (e.g., 'America/New_York') or None if detection fails
    """
    try:
        return _tf.timezone_at(lat=latitude, lng=longitude)
    except Exception:
        return None


def format_timestamp(timestamp: Optional[float]) -> str:
    """Format Unix timestamp to readable date-time string.

    Args:
        timestamp: Unix timestamp (seconds since epoch)

    Returns:
        Formatted string in "MM-DD HH:MM:SS" format, or empty string if timestamp is None

    Example:
        >>> format_timestamp(1699123456.789)
        "11-04 23:57:36"
    """
    if not timestamp:
        return ""
    dt = datetime.datetime.fromtimestamp(timestamp)
    return dt.strftime("%m-%d %H:%M:%S")


def format_time_range(start_time: Optional[float], end_time: Optional[float] = None) -> str:
    """Format task time range consistently across all PFC tools.

    Args:
        start_time: Unix timestamp for task start (seconds since epoch)
        end_time: Unix timestamp for task end (seconds since epoch), optional

    Returns:
        Formatted time string:
        - "started MM-DD HH:MM:SS" if only start_time
        - "MM-DD HH:MM:SS → HH:MM:SS" if same day
        - "MM-DD HH:MM:SS → MM-DD HH:MM:SS" if different days
        - "" if start_time is None

    Example:
        >>> format_time_range(1699123456.789)
        "started 11-04 23:57:36"
        >>> format_time_range(1699123456.789, 1699123556.789)
        "11-04 23:57:36 → 23:59:16"
        >>> format_time_range(1699123456.789, 1699209856.789)
        "11-04 23:57:36 → 11-05 23:57:36"
    """
    if not start_time:
        return ""

    start_str = format_timestamp(start_time)

    if not end_time:
        return f"started {start_str}"

    # Check if start and end are on the same day
    start_dt = datetime.datetime.fromtimestamp(start_time)
    end_dt = datetime.datetime.fromtimestamp(end_time)

    if end_dt.date() == start_dt.date():
        # Same day: show only time for end
        end_str = end_dt.strftime("%H:%M:%S")
    else:
        # Different days: show full date-time for end
        end_str = format_timestamp(end_time)

    return f"{start_str} → {end_str}"