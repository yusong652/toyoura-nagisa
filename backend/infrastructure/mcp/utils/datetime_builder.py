"""Simple datetime construction utilities for LLM-friendly date/time handling.

This module provides utilities to construct ISO datetime strings from simple
year/month/day/hour/minute parameters that are easy for LLMs to provide.
"""

from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
from dataclasses import dataclass


@dataclass
class SimpleDateTime:
    """Simple datetime representation that LLMs can easily provide."""
    year: int
    month: int
    day: int
    hour: int = 0
    minute: int = 0
    timezone_offset_hours: int = 9  # Default to JST (UTC+9)
    
    def to_iso_string(self) -> str:
        """Convert to ISO datetime string with timezone."""
        # Create timezone object
        tz = timezone(timedelta(hours=self.timezone_offset_hours))
        
        # Create datetime object
        dt = datetime(
            year=self.year,
            month=self.month,
            day=self.day,
            hour=self.hour,
            minute=self.minute,
            second=0,
            microsecond=0,
            tzinfo=tz
        )
        
        # Format as ISO string
        return dt.isoformat()


def build_datetime_from_simple_params(
    year: int,
    month: int,
    day: int,
    hour: int = 0,
    minute: int = 0,
    timezone_offset_hours: int = 9
) -> str:
    """Build ISO datetime string from simple parameters.
    
    Args:
        year: Year (e.g., 2025)
        month: Month (1-12)
        day: Day of month (1-31)
        hour: Hour (0-23), default 0
        minute: Minute (0-59), default 0
        timezone_offset_hours: Timezone offset from UTC, default 9 (JST)
    
    Returns:
        ISO datetime string (e.g., "2025-07-30T08:00:00+09:00")
    
    Raises:
        ValueError: If date/time parameters are invalid
    """
    # Validate parameters
    if not (1 <= month <= 12):
        raise ValueError(f"Month must be between 1 and 12, got {month}")
    
    if not (1 <= day <= 31):
        raise ValueError(f"Day must be between 1 and 31, got {day}")
    
    if not (0 <= hour <= 23):
        raise ValueError(f"Hour must be between 0 and 23, got {hour}")
    
    if not (0 <= minute <= 59):
        raise ValueError(f"Minute must be between 0 and 59, got {minute}")
    
    if not (-12 <= timezone_offset_hours <= 14):
        raise ValueError(f"Timezone offset must be between -12 and 14, got {timezone_offset_hours}")
    
    simple_dt = SimpleDateTime(
        year=year,
        month=month,
        day=day,
        hour=hour,
        minute=minute,
        timezone_offset_hours=timezone_offset_hours
    )
    
    return simple_dt.to_iso_string()


def parse_flexible_datetime_param(param_value: Any) -> Optional[str]:
    """Parse flexible datetime parameter formats.
    
    Supports:
    1. Simple object: {"year": 2025, "month": 7, "day": 30, "hour": 8, "minute": 0}
    2. Date-only object: {"year": 2025, "month": 7, "day": 30}
    3. ISO string (for backward compatibility): "2025-07-30T08:00:00+09:00"
    4. None/null values
    
    Args:
        param_value: The parameter value to parse
        
    Returns:
        ISO datetime string or None
        
    Raises:
        ValueError: If the parameter format is invalid
    """
    if param_value is None:
        return None
    
    # Handle ISO string format (backward compatibility)
    if isinstance(param_value, str):
        # Basic validation for ISO format
        try:
            datetime.fromisoformat(param_value.replace('Z', '+00:00'))
            return param_value
        except ValueError:
            raise ValueError(f"Invalid ISO datetime string: {param_value}")
    
    # Handle simple object format
    if isinstance(param_value, dict):
        required_fields = ['year', 'month', 'day']
        
        # Check for required fields
        for field in required_fields:
            if field not in param_value:
                raise ValueError(f"Missing required field '{field}' in datetime parameter")
        
        # Extract values with defaults
        year = param_value['year']
        month = param_value['month']
        day = param_value['day']
        hour = param_value.get('hour', 0)
        minute = param_value.get('minute', 0)
        timezone_offset_hours = param_value.get('timezone_offset_hours', 9)
        
        # Validate types
        for field, value in [('year', year), ('month', month), ('day', day), 
                           ('hour', hour), ('minute', minute), ('timezone_offset_hours', timezone_offset_hours)]:
            if not isinstance(value, int):
                raise ValueError(f"Field '{field}' must be an integer, got {type(value).__name__}")
        
        return build_datetime_from_simple_params(
            year=year,
            month=month,
            day=day,
            hour=hour,
            minute=minute,
            timezone_offset_hours=timezone_offset_hours
        )
    
    raise ValueError(f"Unsupported datetime parameter type: {type(param_value).__name__}. Expected simple object with year/month/day fields or ISO string.")


def parse_calendar_datetime_params(**kwargs) -> Dict[str, Any]:
    """Parse calendar tool datetime parameters.
    
    Converts simple datetime objects to ISO strings for calendar API.
    
    Args:
        **kwargs: Tool parameters which may include datetime fields
        
    Returns:
        Dictionary with converted datetime parameters
        
    Raises:
        ValueError: If datetime parameters are invalid
    """
    datetime_fields = ['time_min', 'time_max', 'start', 'end']
    result = kwargs.copy()
    
    for field in datetime_fields:
        if field in result:
            try:
                result[field] = parse_flexible_datetime_param(result[field])
            except ValueError as e:
                raise ValueError(f"Invalid {field} parameter: {str(e)}")
    
    return result


def get_current_datetime_components(timezone_offset_hours: int = 9) -> Dict[str, int]:
    """Get current date/time components for reference.
    
    Args:
        timezone_offset_hours: Timezone offset from UTC, default 9 (JST)
        
    Returns:
        Dictionary with current year, month, day, hour, minute
    """
    tz = timezone(timedelta(hours=timezone_offset_hours))
    now = datetime.now(tz)
    
    return {
        'year': now.year,
        'month': now.month,
        'day': now.day,
        'hour': now.hour,
        'minute': now.minute,
        'timezone_offset_hours': timezone_offset_hours
    }


def get_date_range_examples() -> Dict[str, Dict[str, Any]]:
    """Get example date range parameters for documentation.
    
    Returns:
        Dictionary with example start and end date parameters
    """
    current = get_current_datetime_components()
    
    # Today start (00:00)
    today_start = {
        'year': current['year'],
        'month': current['month'],
        'day': current['day'],
        'hour': 0,
        'minute': 0
    }
    
    # Today end (23:59)
    today_end = {
        'year': current['year'],
        'month': current['month'],
        'day': current['day'],
        'hour': 23,
        'minute': 59
    }
    
    return {
        'today_start': today_start,
        'today_end': today_end,
        'current_time': current
    }