"""Utility functions for calendar operations.

This module provides common utility functions for processing calendar data
and executing calendar operations with consistent error handling.
"""

from typing import Dict, Any, Optional
from enum import Enum
from datetime import datetime, timezone, timedelta


class CalendarOperationType(str, Enum):
    """Types of calendar operations."""
    LIST_EVENTS = "list_events"
    CREATE_EVENT = "create_event"
    UPDATE_EVENT = "update_event"
    DELETE_EVENT = "delete_event"


def parse_calendar_event(event_data: Dict[str, Any]) -> Dict[str, Any]:
    """Parse Google Calendar API event data into simplified dictionary.
    
    Args:
        event_data: Raw event data from Google Calendar API
    
    Returns:
        Dict[str, Any]: Simplified event dictionary with essential fields only
    """
    return {
        'id': event_data['id'],
        'summary': event_data.get('summary', ''),
        'start': event_data['start'].get('dateTime', event_data['start'].get('date', '')),
        'end': event_data['end'].get('dateTime', event_data['end'].get('date', '')),
        'location': event_data.get('location'),
        'status': event_data.get('status', 'confirmed'),
    }


def execute_calendar_operation(
    operation_type: CalendarOperationType,
    operation_func,
    **kwargs
) -> Dict[str, Any]:
    """Execute a calendar operation with error handling.
    
    Args:
        operation_type: Type of calendar operation being performed
        operation_func: Function to execute the calendar operation
        **kwargs: Additional arguments to pass to operation_func
    
    Returns:
        Dict[str, Any]: Operation result with structure:
            - success: bool - Whether operation succeeded
            - events: List[Dict] - List of event dictionaries
            - total_events: int - Number of events returned
            - error_message: Optional[str] - Error message if failed
            - warnings: List[str] - Any warnings from operation
    """
    try:
        result = operation_func(**kwargs)
        
        # Parse result based on operation type
        if operation_type == CalendarOperationType.LIST_EVENTS:
            events = [parse_calendar_event(event) for event in result.get('items', [])]
            return {
                "success": True,
                "events": events,
                "total_events": len(events),
                "error_message": None,
                "warnings": [],
            }
        else:
            # Single event operations
            event = parse_calendar_event(result) if result else None
            return {
                "success": True,
                "events": [event] if event else [],
                "total_events": 1 if event else 0,
                "error_message": None,
                "warnings": [],
            }
            
    except Exception as e:
        return {
            "success": False,
            "events": [],
            "total_events": 0,
            "error_message": str(e),
            "warnings": [],
        }


def parse_calendar_datetime_params(**kwargs) -> Dict[str, Any]:
    """Parse calendar tool datetime parameters.
    
    Converts simple datetime objects to ISO strings for calendar API.
    
    Args:
        **kwargs: Tool parameters which may include datetime fields
        
    Returns:
        Dict[str, Any]: Dictionary with converted datetime parameters
        
    Raises:
        ValueError: If datetime parameters are invalid
    """
    datetime_fields = ['time_min', 'time_max', 'start', 'end']
    result = kwargs.copy()
    
    for field in datetime_fields:
        if field in result and result[field] is not None:
            param_value = result[field]
            
            # Handle ISO string format (already formatted)
            if isinstance(param_value, str):
                result[field] = param_value
                continue
            
            # Handle simple object format
            if isinstance(param_value, dict):
                # Extract values with defaults
                year = param_value.get('year')
                month = param_value.get('month')
                day = param_value.get('day')
                hour = param_value.get('hour', 0)
                minute = param_value.get('minute', 0)
                timezone_offset_hours = param_value.get('timezone_offset_hours', 9)  # Default to JST
                
                if year and month and day:
                    # Create timezone object
                    tz = timezone(timedelta(hours=timezone_offset_hours))
                    
                    # Create datetime object
                    dt = datetime(
                        year=year,
                        month=month,
                        day=day,
                        hour=hour,
                        minute=minute,
                        second=0,
                        microsecond=0,
                        tzinfo=tz
                    )
                    
                    result[field] = dt.isoformat()
    
    return result


def validate_event_times(start_time_str: str, end_time_str: str) -> Optional[str]:
    """Validate calendar event times.
    
    Only checks two essential conditions:
    1. Start time must be after current time
    2. End time must be after start time
    
    Args:
        start_time_str: Start time in RFC3339 format
        end_time_str: End time in RFC3339 format
        
    Returns:
        Optional[str]: Error message if validation fails, None if valid
        
    Example:
        >>> error = validate_event_times("2025-12-01T10:00:00Z", "2025-12-01T11:00:00Z")
        >>> if error:
        ...     print(f"Validation error: {error}")
    """
    try:
        # Parse times
        start_dt = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
        end_dt = datetime.fromisoformat(end_time_str.replace('Z', '+00:00'))
        
        # Convert to UTC if no timezone info
        if start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=timezone.utc)
        if end_dt.tzinfo is None:
            end_dt = end_dt.replace(tzinfo=timezone.utc)
        
        now = datetime.now(timezone.utc)
        
        # Check 1: Start time must be after current time
        if start_dt <= now:
            return "Start time must be in the future"
        
        # Check 2: End time must be after start time
        if end_dt <= start_dt:
            return "End time must be after start time"
        
        return None  # Valid
        
    except ValueError as e:
        return f"Invalid time format: {str(e)}"