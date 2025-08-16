"""Google Calendar tools – comprehensive calendar management with enterprise-grade functionality.

This module provides atomic calendar operations focusing on Google Calendar integration
with rich metadata, security controls, and intelligent event processing. It supports
event creation, listing, updates, and deletion with comprehensive validation.

Modeled after the coding tools' architecture for consistency and interoperability.
"""

import os
import time
from pathlib import Path
from typing import Dict, List, Any, Optional, Union, Tuple
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timezone

from pydantic import Field
from pydantic.fields import FieldInfo
from fastmcp import FastMCP

from backend.infrastructure.auth.google.google_calendar import build_google_calendar_service
from backend.infrastructure.mcp.utils.tool_result import ToolResult
from backend.infrastructure.mcp.utils import ensure_future_datetime
from backend.infrastructure.mcp.utils.datetime_builder import (
    parse_calendar_datetime_params,
    get_date_range_examples
)

__all__ = ["register_calendar_tools"]

# -----------------------------------------------------------------------------
# Constants and configuration
# -----------------------------------------------------------------------------

# Default limits for calendar operations
DEFAULT_MAX_EVENTS = 10
MAX_EVENTS_HARD_LIMIT = 100
MAX_EVENT_TITLE_LENGTH = 200
MAX_EVENT_DESCRIPTION_LENGTH = 2000
MAX_EVENT_LOCATION_LENGTH = 500

# Calendar operation timeouts
CALENDAR_OPERATION_TIMEOUT = 30  # seconds
CALENDAR_BATCH_TIMEOUT = 60     # seconds for batch operations

# Performance thresholds
PERFORMANCE_SLOW_THRESHOLD = 2.0  # seconds
PERFORMANCE_LARGE_THRESHOLD = 5.0  # seconds

# Time validation thresholds
PAST_TIME_WARNING_THRESHOLD = 24 * 60 * 60  # 24 hours in seconds - warn if event is more than 24 hours in the past
IMMEDIATE_PAST_WARNING_THRESHOLD = 60  # 60 seconds - warn if event is in the immediate past
CALENDAR_OAUTH_TOKEN_DIR = Path(os.getenv("CALENDAR_OAUTH_TOKEN_DIR", 
    Path(__file__).parent / "../google_auth/tokens")).resolve()    

# -----------------------------------------------------------------------------
# Enums for type safety
# -----------------------------------------------------------------------------

class CalendarOperationType(str, Enum):
    """Types of calendar operations."""
    LIST_EVENTS = "list_events"
    CREATE_EVENT = "create_event"
    UPDATE_EVENT = "update_event"
    DELETE_EVENT = "delete_event"

class EventStatus(str, Enum):
    """Google Calendar event status."""
    CONFIRMED = "confirmed"
    TENTATIVE = "tentative"
    CANCELLED = "cancelled"

class EventVisibility(str, Enum):
    """Event visibility settings."""
    DEFAULT = "default"
    PUBLIC = "public"
    PRIVATE = "private"
    CONFIDENTIAL = "confidential"

class TimeZone(str, Enum):
    """Common timezone identifiers."""
    UTC = "UTC"
    JST = "Asia/Tokyo"
    PST = "America/Los_Angeles"
    EST = "America/New_York"
    CET = "Europe/Paris"
    GMT = "Europe/London"

# -----------------------------------------------------------------------------
# Data structures
# -----------------------------------------------------------------------------

@dataclass
class CalendarEvent:
    """Represents a calendar event with comprehensive metadata."""
    id: str
    summary: str
    start: str
    end: str
    location: Optional[str] = None
    description: Optional[str] = None
    status: EventStatus = EventStatus.CONFIRMED
    visibility: EventVisibility = EventVisibility.DEFAULT
    created: Optional[str] = None
    updated: Optional[str] = None
    html_link: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "summary": self.summary,
            "start": self.start,
            "end": self.end,
            "location": self.location,
            "description": self.description,
            "status": self.status.value,
            "visibility": self.visibility.value,
            "created": self.created,
            "updated": self.updated,
            "html_link": self.html_link,
        }
    
    def to_llm_dict(self) -> Dict[str, Any]:
        """Convert to simplified dictionary for LLM consumption."""
        result = {
            "id": self.id,
            "summary": self.summary,
            "start": self.start,
            "end": self.end,
        }
        
        # Only include optional fields if they have values
        if self.location:
            result["location"] = self.location
        if self.description:
            result["description"] = self.description
        if self.html_link:
            result["html_link"] = self.html_link
            
        return result

@dataclass
class CalendarOperationResult:
    """Result of a calendar operation with metadata."""
    operation_type: CalendarOperationType
    success: bool
    events: List[CalendarEvent]
    execution_time: float
    total_events: int
    error_message: Optional[str] = None
    warnings: List[str] = None
    
    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []
    
    @property
    def performance_category(self) -> str:
        """Get performance category based on execution time."""
        if self.execution_time > PERFORMANCE_LARGE_THRESHOLD:
            return "slow"
        elif self.execution_time > PERFORMANCE_SLOW_THRESHOLD:
            return "moderate"
        else:
            return "fast"
    
    def get_summary(self) -> Dict[str, Any]:
        """Get operation summary statistics."""
        return {
            "operation_type": self.operation_type.value,
            "success": self.success,
            "total_events": self.total_events,
            "performance_category": self.performance_category,
            "execution_time": self.execution_time,
            "has_warnings": len(self.warnings) > 0,
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "operation_metadata": {
                "operation_type": self.operation_type.value,
                "execution_time": self.execution_time,
                "performance_category": self.performance_category,
                "success": self.success,
                "error_message": self.error_message,
                "warnings": self.warnings,
            },
            "events": [event.to_dict() for event in self.events],
            "summary": self.get_summary(),
        }

# -----------------------------------------------------------------------------
# Utility functions
# -----------------------------------------------------------------------------

def get_user_email() -> str:
    """Get the default user email address from environment variable.
    
    Returns:
        str: User email address for Google Calendar API
        
    Raises:
        ValueError: If USER_GMAIL_ADDRESS environment variable is not set
    """
    user_email = os.getenv("USER_GMAIL_ADDRESS")
    if not user_email:
        raise ValueError("USER_GMAIL_ADDRESS environment variable not set")
    return user_email

def _validate_time_past_warning(dt: datetime, time_label: str) -> Optional[str]:
    """Validate if datetime is in the past and return appropriate warning message."""
    now = datetime.now(dt.tzinfo)
    time_diff = (now - dt).total_seconds()
    
    if time_diff > 0:  # Past time
        if time_diff > PAST_TIME_WARNING_THRESHOLD:
            return f"Warning: {time_label} time is in the past ({time_diff/3600:.1f} hours ago). Event will be scheduled for the next occurrence."
        elif time_diff > IMMEDIATE_PAST_WARNING_THRESHOLD:
            return f"Warning: {time_label} time is in the recent past ({time_diff/60:.1f} minutes ago). Event will be scheduled for the next occurrence."
        else:
            return f"Warning: {time_label} time is in the immediate past ({time_diff:.0f} seconds ago). Event will be scheduled for the next occurrence."
    
    return None

def _validate_event_data(
    summary: str,
    start: Optional[str] = None,
    end: Optional[str] = None,
    location: Optional[str] = None,
    description: Optional[str] = None,
) -> List[str]:
    """Validate event data and return warnings."""
    warnings = []
    
    # Validate summary
    if len(summary) > MAX_EVENT_TITLE_LENGTH:
        warnings.append(f"Event title exceeds recommended length ({MAX_EVENT_TITLE_LENGTH} chars)")
    
    # Validate location
    if location and len(location) > MAX_EVENT_LOCATION_LENGTH:
        warnings.append(f"Event location exceeds recommended length ({MAX_EVENT_LOCATION_LENGTH} chars)")
    
    # Validate description
    if description and len(description) > MAX_EVENT_DESCRIPTION_LENGTH:
        warnings.append(f"Event description exceeds recommended length ({MAX_EVENT_DESCRIPTION_LENGTH} chars)")
    
    # Validate time format and check for past times
    if start:
        try:
            start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
            past_warning = _validate_time_past_warning(start_dt, "start")
            if past_warning:
                warnings.append(past_warning)
        except ValueError:
            warnings.append("Invalid start time format. Please use RFC3339 format")
    
    if end:
        try:
            end_dt = datetime.fromisoformat(end.replace('Z', '+00:00'))
            past_warning = _validate_time_past_warning(end_dt, "end")
            if past_warning:
                warnings.append(past_warning)
        except ValueError:
            warnings.append("Invalid end time format. Please use RFC3339 format")
    
    return warnings

def _parse_calendar_event(event_data: Dict[str, Any]) -> CalendarEvent:
    """Parse Google Calendar API event data into CalendarEvent object."""
    return CalendarEvent(
        id=event_data['id'],
        summary=event_data.get('summary', ''),
        start=event_data['start'].get('dateTime', event_data['start'].get('date', '')),
        end=event_data['end'].get('dateTime', event_data['end'].get('date', '')),
        location=event_data.get('location'),
        description=event_data.get('description'),
        status=EventStatus(event_data.get('status', 'confirmed')),
        visibility=EventVisibility(event_data.get('visibility', 'default')),
        created=event_data.get('created'),
        updated=event_data.get('updated'),
        html_link=event_data.get('htmlLink'),
    )

def _execute_calendar_operation(
    operation_type: CalendarOperationType,
    operation_func,
    **kwargs
) -> CalendarOperationResult:
    """Execute a calendar operation with error handling and timing."""
    start_time = time.time()
    
    try:
        result = operation_func(**kwargs)
        execution_time = time.time() - start_time
        
        # Parse result based on operation type
        if operation_type == CalendarOperationType.LIST_EVENTS:
            events = [_parse_calendar_event(event) for event in result.get('items', [])]
            return CalendarOperationResult(
                operation_type=operation_type,
                success=True,
                events=events,
                execution_time=execution_time,
                total_events=len(events),
            )
        else:
            # Single event operations
            event = _parse_calendar_event(result) if result else None
            return CalendarOperationResult(
                operation_type=operation_type,
                success=True,
                events=[event] if event else [],
                execution_time=execution_time,
                total_events=1 if event else 0,
            )
            
    except Exception as e:
        execution_time = time.time() - start_time
        return CalendarOperationResult(
            operation_type=operation_type,
            success=False,
            events=[],
            execution_time=execution_time,
            total_events=0,
            error_message=str(e),
        )

# -----------------------------------------------------------------------------
# Core calendar operations
# -----------------------------------------------------------------------------

def register_calendar_tools(mcp: FastMCP):
    """Register Google Calendar tools with proper tags synchronization."""
    
    # Common tags for all calendar tools
    common_tags = {"calendar", "schedule", "event", "google", "time"}
    common_annotations = {"category": "calendar", "tags": ["calendar", "schedule", "event", "google", "time"]}

    @mcp.tool(tags=common_tags, annotations=common_annotations)
    def list_calendar_events(
        max_results: int = Field(
            DEFAULT_MAX_EVENTS,
            ge=1,
            le=MAX_EVENTS_HARD_LIMIT,
            description="Maximum number of events to retrieve (1-100).",
        ),
        time_min: Optional[Dict[str, int]] = Field(
            None,
            description="Start time filter. Provide a simple object with year, month, day, and optionally hour, minute. Example: {'year': 2025, 'month': 7, 'day': 30, 'hour': 0, 'minute': 0}",
        ),
        time_max: Optional[Dict[str, int]] = Field(
            None,
            description="End time filter. Provide a simple object with year, month, day, and optionally hour, minute. Example: {'year': 2025, 'month': 7, 'day': 31, 'hour': 23, 'minute': 59}",
        ),
    ) -> Dict[str, Any]:
        """List upcoming events from Google Calendar with comprehensive filtering and metadata.
        
        Returns structured event data with time-based filtering support.
        Supports pagination and detailed event information including location and links.
        """
        
        # Helper functions for consistent results
        def _error(message: str) -> Dict[str, Any]:
            return ToolResult(status="error", message=message, error=message).model_dump()

        def _success(message: str, llm_content: Any, **data: Any) -> Dict[str, Any]:
            return ToolResult(
                status="success",
                message=message,
                llm_content=llm_content,
                data=data,
            ).model_dump()

        print(f"[DEBUG] list_calendar_events called with:")
        print(f"  max_results: {max_results} (type: {type(max_results)})")
        print(f"  time_min: {time_min} (type: {type(time_min)})")
        print(f"  time_max: {time_max} (type: {type(time_max)})")

        # Parameter processing
        try:
            # Handle FieldInfo objects (default values)
            if isinstance(max_results, FieldInfo):
                print(f"[DEBUG] max_results is FieldInfo, setting to DEFAULT_MAX_EVENTS: {DEFAULT_MAX_EVENTS}")
                max_results = DEFAULT_MAX_EVENTS
            if isinstance(time_min, FieldInfo):
                print(f"[DEBUG] time_min is FieldInfo, setting to None")
                time_min = None
            if isinstance(time_max, FieldInfo):
                print(f"[DEBUG] time_max is FieldInfo, setting to None")
                time_max = None

            # Convert simple datetime parameters to ISO strings
            processed_params = parse_calendar_datetime_params(
                max_results=max_results,
                time_min=time_min,
                time_max=time_max
            )
            
            max_results = processed_params.get('max_results', DEFAULT_MAX_EVENTS)
            time_min = processed_params.get('time_min')
            time_max = processed_params.get('time_max')
            
            print(f"[DEBUG] After datetime processing:")
            print(f"  max_results: {max_results}")
            print(f"  time_min: {time_min}")
            print(f"  time_max: {time_max}")
            
        except ValueError as e:
            print(f"[DEBUG] Parameter processing failed: {str(e)}")
            return _error(f"Invalid parameters: {str(e)}")

        # Validate parameters
        if max_results <= 0 or max_results > MAX_EVENTS_HARD_LIMIT:
            error_msg = f"max_results must be between 1 and {MAX_EVENTS_HARD_LIMIT}"
            print(f"[DEBUG] Parameter validation failed: {error_msg}")
            return _error(error_msg)

        try:
            print(f"[DEBUG] Starting calendar operation...")
            
            # Get user email and build service
            print(f"[DEBUG] Getting user email...")
            try:
                user_email = get_user_email()
                print(f"[DEBUG] User email: {user_email}")
            except Exception as e:
                print(f"[DEBUG] Failed to get user email: {str(e)}")
                raise

            print(f"[DEBUG] Building Google Calendar service...")
            print(f"[DEBUG] Tokens directory: {CALENDAR_OAUTH_TOKEN_DIR}")
            try:
                service = build_google_calendar_service(user_email, tokens_dir=CALENDAR_OAUTH_TOKEN_DIR)
                print(f"[DEBUG] Service built successfully")
            except Exception as e:
                print(f"[DEBUG] Failed to build service: {str(e)}")
                raise
            
            # Prepare query parameters
            query_params = {
                'calendarId': 'primary',
                'maxResults': max_results,
                'singleEvents': True,
                'orderBy': 'startTime'
            }
            
            # Set time bounds
            if time_min:
                query_params['timeMin'] = time_min
                print(f"[DEBUG] Using provided time_min: {time_min}")
            else:
                # Use proper RFC3339 format with Z suffix for UTC (no microseconds)
                default_time_min = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
                query_params['timeMin'] = default_time_min
                print(f"[DEBUG] Using default time_min: {default_time_min}")
            
            if time_max:
                query_params['timeMax'] = time_max
                print(f"[DEBUG] Using time_max: {time_max}")
            
            print(f"[DEBUG] Final query parameters: {query_params}")
            
            # Execute calendar operation
            def list_operation():
                print(f"[DEBUG] Executing calendar API call...")
                try:
                    result = service.events().list(**query_params).execute()
                    print(f"[DEBUG] API call successful, got result with keys: {list(result.keys())}")
                    items = result.get('items', [])
                    print(f"[DEBUG] Found {len(items)} items")
                    return result
                except Exception as e:
                    print(f"[DEBUG] API call failed: {str(e)}")
                    print(f"[DEBUG] Exception type: {type(e)}")
                    raise
            
            print(f"[DEBUG] Calling _execute_calendar_operation...")
            result = _execute_calendar_operation(
                CalendarOperationType.LIST_EVENTS,
                list_operation,
            )
            
            print(f"[DEBUG] Operation result:")
            print(f"  success: {result.success}")
            print(f"  total_events: {result.total_events}")
            print(f"  execution_time: {result.execution_time}")
            print(f"  error_message: {result.error_message}")
            print(f"  warnings: {result.warnings}")
            
            # Build user-facing message
            if result.success:
                events_word = "event" if result.total_events == 1 else "events"
                message = f"Retrieved {result.total_events} {events_word} from primary calendar ({result.execution_time:.2f}s)"
                print(f"[DEBUG] Success message: {message}")
            else:
                message = f"Failed to retrieve events: {result.error_message}"
                print(f"[DEBUG] Error message: {message}")
            
            # Build structured LLM content
            llm_content = {
                "operation": {
                    "type": "list_events",
                    "max_results": max_results
                },
                "result": {
                    "events": [event.to_llm_dict() for event in result.events],
                    "total_events": result.total_events
                },
                "summary": {
                    "operation_type": "list_events",
                    "success": result.success,
                    "has_warnings": len(result.warnings) > 0
                }
            }
            
            # Add time range only if specified
            if time_min or time_max:
                llm_content["operation"]["time_range"] = {
                    "start": time_min,
                    "end": time_max
                }
            
            # Add warnings if any
            if result.warnings:
                llm_content["warnings"] = result.warnings
            
            print(f"[DEBUG] Returning success result")
            return _success(message, llm_content, operation_result=result.to_dict())
            
        except ValueError as e:
            error_msg = str(e)
            print(f"[DEBUG] ValueError caught: {error_msg}")
            return _error(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error listing events: {str(e)}"
            print(f"[DEBUG] Exception caught: {error_msg}")
            print(f"[DEBUG] Exception type: {type(e)}")
            import traceback
            print(f"[DEBUG] Full traceback:")
            traceback.print_exc()
            return _error(error_msg)

    @mcp.tool(tags=common_tags, annotations=common_annotations)
    def create_calendar_event(
        summary: str = Field(..., description="Event summary/title (required)."),
        start: Dict[str, int] = Field(..., description="Event start time. Provide a simple object with year, month, day, hour, minute. Example: {'year': 2025, 'month': 7, 'day': 30, 'hour': 10, 'minute': 0}"),
        end: Dict[str, int] = Field(..., description="Event end time. Provide a simple object with year, month, day, hour, minute. Example: {'year': 2025, 'month': 7, 'day': 30, 'hour': 11, 'minute': 0}"),
        location: Optional[str] = Field(None, description="Event location (e.g., 'Conference Room A', '123 Main St')."),
        description: Optional[str] = Field(None, description="Event description or notes."),
    ) -> Dict[str, Any]:
        """Create a new event in Google Calendar with comprehensive validation and metadata.
        
        Returns structured event data with automatic future date correction.
        Automatically schedules past times for next occurrence with detailed warnings.
        
        Example: create_calendar_event("Team Meeting", "2025-07-07T19:00:00+09:00", "2025-07-07T11:20:00+09:00")
        """
        
        # Helper functions for consistent results
        def _error(message: str) -> Dict[str, Any]:
            return ToolResult(status="error", message=message, error=message).model_dump()

        def _success(message: str, llm_content: Any, **data: Any) -> Dict[str, Any]:
            return ToolResult(
                status="success",
                message=message,
                llm_content=llm_content,
                data=data,
            ).model_dump()

        # Parameter processing
        try:
            # Handle FieldInfo objects (default values)
            if isinstance(location, FieldInfo):
                location = None
            if isinstance(description, FieldInfo):
                description = None

            # Convert simple datetime parameters to ISO strings
            processed_params = parse_calendar_datetime_params(
                summary=summary,
                start=start,
                end=end,
                location=location,
                description=description
            )
            
            summary = processed_params.get('summary', summary)
            start = processed_params.get('start', start)
            end = processed_params.get('end', end)
            location = processed_params.get('location', location)
            description = processed_params.get('description', description)
            
        except ValueError as e:
            return _error(f"Invalid parameters: {str(e)}")

        # Validate event data
        warnings = _validate_event_data(summary, start, end, location, description)
        
        # Validate required fields
        if not summary or not summary.strip():
            return _error("Event summary is required")
        
        if not start or not end:
            return _error("Both start and end times are required")

        try:
            # Validate and parse datetime
            try:
                start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
                end_dt = datetime.fromisoformat(end.replace('Z', '+00:00'))
            except ValueError as e:
                return _error(f"Invalid datetime format: {str(e)}. Please use RFC3339 format")
            
            # Validate time order
            if start_dt >= end_dt:
                return _error("Start time must be before end time")
            
            # Check for past times and auto-correct to future time
            now = datetime.now(start_dt.tzinfo)
            original_start = start_dt
            original_end = end_dt
            
            # Auto-correct to future time
            start_dt = ensure_future_datetime(start_dt, now)
            end_dt = ensure_future_datetime(end_dt, now)
            
            # Add warnings for time corrections
            if start_dt != original_start:
                time_diff = (now - original_start).total_seconds()
                if time_diff > PAST_TIME_WARNING_THRESHOLD:
                    warnings.append(f"Start time was {time_diff/3600:.1f} hours in the past. Automatically scheduled for next occurrence.")
                elif time_diff > IMMEDIATE_PAST_WARNING_THRESHOLD:
                    warnings.append(f"Start time was {time_diff/60:.1f} minutes in the past. Automatically scheduled for next occurrence.")
                else:
                    warnings.append(f"Start time was {time_diff:.0f} seconds in the past. Automatically scheduled for next occurrence.")
            
            if end_dt != original_end:
                time_diff = (now - original_end).total_seconds()
                if time_diff > PAST_TIME_WARNING_THRESHOLD:
                    warnings.append(f"End time was {time_diff/3600:.1f} hours in the past. Automatically scheduled for next occurrence.")
                elif time_diff > IMMEDIATE_PAST_WARNING_THRESHOLD:
                    warnings.append(f"End time was {time_diff/60:.1f} minutes in the past. Automatically scheduled for next occurrence.")
                else:
                    warnings.append(f"End time was {time_diff:.0f} seconds in the past. Automatically scheduled for next occurrence.")
            
            start = start_dt.strftime('%Y-%m-%dT%H:%M:%S%z').replace('+0000', 'Z').replace('-0000', 'Z')
            end = end_dt.strftime('%Y-%m-%dT%H:%M:%S%z').replace('+0000', 'Z').replace('-0000', 'Z')
            
            # Get user email and build service
            user_email = get_user_email()
            service = build_google_calendar_service(user_email, tokens_dir=CALENDAR_OAUTH_TOKEN_DIR)
            
            # Prepare event data
            event_data = {
                'summary': summary,
                'start': {'dateTime': start},
                'end': {'dateTime': end}
            }
            
            if location:
                event_data['location'] = location
            if description:
                event_data['description'] = description
            
            # Execute calendar operation
            def create_operation():
                return service.events().insert(calendarId='primary', body=event_data).execute()
            
            result = _execute_calendar_operation(
                CalendarOperationType.CREATE_EVENT,
                create_operation,
            )
            
            # Add validation warnings
            result.warnings.extend(warnings)
            
            # Build user-facing message
            if result.success:
                created_event = result.events[0]
                message = f"Created event '{created_event.summary}' in primary calendar ({result.execution_time:.2f}s)"
            else:
                message = f"Failed to create event: {result.error_message}"
            
            # Build structured LLM content
            llm_content = {
                "operation": {
                    "type": "create_event"
                },
                "result": {
                    "event": result.events[0].to_llm_dict() if result.events else None
                },
                "summary": {
                    "operation_type": "create_event",
                    "success": result.success,
                    "has_warnings": len(result.warnings) > 0
                }
            }
            
            # Add warnings if any
            if result.warnings:
                llm_content["warnings"] = result.warnings
            
            return _success(message, llm_content, operation_result=result.to_dict())
            
        except ValueError as e:
            return _error(str(e))
        except Exception as e:
            if 'Not Found' in str(e):
                return _error("Primary calendar not found")
            elif 'Invalid Value' in str(e):
                return _error(f"Invalid event data: {str(e)}")
            else:
                return _error(f"Unexpected error creating event: {str(e)}")

    @mcp.tool(tags=common_tags, annotations=common_annotations)
    def update_calendar_event(
        event_id: str = Field(..., description="ID of the event to update."),
        summary: Optional[str] = Field(None, description="New event summary/title."),
        start: Optional[Dict[str, int]] = Field(None, description="New start time. Provide a simple object with year, month, day, hour, minute. Example: {'year': 2025, 'month': 7, 'day': 30, 'hour': 10, 'minute': 0}"),
        end: Optional[Dict[str, int]] = Field(None, description="New end time. Provide a simple object with year, month, day, hour, minute. Example: {'year': 2025, 'month': 7, 'day': 30, 'hour': 11, 'minute': 0}"),
        location: Optional[str] = Field(None, description="New event location."),
        description: Optional[str] = Field(None, description="New event description."),
    ) -> Dict[str, Any]:
        """Update an existing event in Google Calendar with comprehensive validation.
        
        Returns structured event data with partial field updates support.
        Only provide fields you want to update - omitted fields remain unchanged.
        Automatically corrects past times to next occurrence with warnings.
        """
        
        # Helper functions for consistent results
        def _error(message: str) -> Dict[str, Any]:
            return ToolResult(status="error", message=message, error=message).model_dump()

        def _success(message: str, llm_content: Any, **data: Any) -> Dict[str, Any]:
            return ToolResult(
                status="success",
                message=message,
                llm_content=llm_content,
                data=data,
            ).model_dump()

        # Parameter processing
        try:
            # Handle FieldInfo objects (default values)
            if isinstance(summary, FieldInfo):
                summary = None
            if isinstance(start, FieldInfo):
                start = None
            if isinstance(end, FieldInfo):
                end = None
            if isinstance(location, FieldInfo):
                location = None
            if isinstance(description, FieldInfo):
                description = None

            # Convert simple datetime parameters to ISO strings
            processed_params = parse_calendar_datetime_params(
                summary=summary,
                start=start,
                end=end,
                location=location,
                description=description
            )
            
            summary = processed_params.get('summary', summary)
            start = processed_params.get('start', start)
            end = processed_params.get('end', end)
            location = processed_params.get('location', location)
            description = processed_params.get('description', description)
            
        except ValueError as e:
            return _error(f"Invalid parameters: {str(e)}")

        # Validate required fields
        if not event_id or not event_id.strip():
            return _error("Event ID is required")
        
        # Check if any updates are provided
        updates = {}
        if summary is not None:
            updates['summary'] = summary
        if start is not None:
            updates['start'] = start
        if end is not None:
            updates['end'] = end
        if location is not None:
            updates['location'] = location
        if description is not None:
            updates['description'] = description
        
        if not updates:
            return _error("At least one field must be provided for update")

        # Validate event data
        warnings = _validate_event_data(
            summary or "",
            start,
            end,
            location,
            description
        )

        try:
            # Validate and process time updates if provided
            if start is not None or end is not None:
                # Parse and validate time updates
                if start is not None:
                    try:
                        start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
                        # Check for past time and auto-correct
                        now = datetime.now(start_dt.tzinfo)
                        original_start = start_dt
                        start_dt = ensure_future_datetime(start_dt, now)
                        
                        if start_dt != original_start:
                            time_diff = (now - original_start).total_seconds()
                            if time_diff > PAST_TIME_WARNING_THRESHOLD:
                                warnings.append(f"Updated start time was {time_diff/3600:.1f} hours in the past. Automatically scheduled for next occurrence.")
                            elif time_diff > IMMEDIATE_PAST_WARNING_THRESHOLD:
                                warnings.append(f"Updated start time was {time_diff/60:.1f} minutes in the past. Automatically scheduled for next occurrence.")
                            else:
                                warnings.append(f"Updated start time was {time_diff:.0f} seconds in the past. Automatically scheduled for next occurrence.")
                        
                        start = start_dt.strftime('%Y-%m-%dT%H:%M:%S%z').replace('+0000', 'Z').replace('-0000', 'Z')
                    except ValueError as e:
                        return _error(f"Invalid start time format: {str(e)}. Please use RFC3339 format")
                
                if end is not None:
                    try:
                        end_dt = datetime.fromisoformat(end.replace('Z', '+00:00'))
                        # Check for past time and auto-correct
                        now = datetime.now(end_dt.tzinfo)
                        original_end = end_dt
                        end_dt = ensure_future_datetime(end_dt, now)
                        
                        if end_dt != original_end:
                            time_diff = (now - original_end).total_seconds()
                            if time_diff > PAST_TIME_WARNING_THRESHOLD:
                                warnings.append(f"Updated end time was {time_diff/3600:.1f} hours in the past. Automatically scheduled for next occurrence.")
                            elif time_diff > IMMEDIATE_PAST_WARNING_THRESHOLD:
                                warnings.append(f"Updated end time was {time_diff/60:.1f} minutes in the past. Automatically scheduled for next occurrence.")
                            else:
                                warnings.append(f"Updated end time was {time_diff:.0f} seconds in the past. Automatically scheduled for next occurrence.")
                        
                        end = end_dt.strftime('%Y-%m-%dT%H:%M:%S%z').replace('+0000', 'Z').replace('-0000', 'Z')
                    except ValueError as e:
                        return _error(f"Invalid end time format: {str(e)}. Please use RFC3339 format")
                
                # Validate time order if both times are provided
                if start is not None and end is not None:
                    start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
                    end_dt = datetime.fromisoformat(end.replace('Z', '+00:00'))
                    if start_dt >= end_dt:
                        return _error("Start time must be before end time")
            
            # Get user email and build service
            user_email = get_user_email()
            service = build_google_calendar_service(user_email, tokens_dir=CALENDAR_OAUTH_TOKEN_DIR)
            
            # Get existing event
            existing_event = service.events().get(
                calendarId='primary',
                eventId=event_id
            ).execute()
            
            # Apply updates
            if summary is not None:
                existing_event['summary'] = summary
            if start is not None:
                existing_event['start']['dateTime'] = start
            if end is not None:
                existing_event['end']['dateTime'] = end
            if location is not None:
                existing_event['location'] = location
            if description is not None:
                existing_event['description'] = description
            
            # Execute calendar operation
            def update_operation():
                return service.events().update(
                    calendarId='primary',
                    eventId=event_id,
                    body=existing_event
                ).execute()
            
            result = _execute_calendar_operation(
                CalendarOperationType.UPDATE_EVENT,
                update_operation,
            )
            
            # Add validation warnings
            result.warnings.extend(warnings)
            
            # Build user-facing message
            if result.success:
                updated_event = result.events[0]
                fields_updated = len(updates)
                fields_word = "field" if fields_updated == 1 else "fields"
                message = f"Updated {fields_updated} {fields_word} in event '{updated_event.summary}' ({result.execution_time:.2f}s)"
            else:
                message = f"Failed to update event: {result.error_message}"
            
            # Build structured LLM content
            llm_content = {
                "operation": {
                    "type": "update_event"
                },
                "result": {
                    "event": result.events[0].to_llm_dict() if result.events else None
                },
                "summary": {
                    "operation_type": "update_event",
                    "success": result.success,
                    "has_warnings": len(result.warnings) > 0
                }
            }
            
            # Add warnings if any
            if result.warnings:
                llm_content["warnings"] = result.warnings
            
            return _success(message, llm_content, operation_result=result.to_dict())
            
        except Exception as e:
            if 'Not Found' in str(e):
                return _error(f"Event not found: {event_id} in primary calendar")
            else:
                return _error(f"Unexpected error updating event: {str(e)}")

    @mcp.tool(tags=common_tags, annotations=common_annotations)
    def delete_calendar_event(
        event_id: str = Field(..., description="ID of the event to delete."),
    ) -> Dict[str, Any]:
        """Delete an event from Google Calendar with comprehensive validation and metadata.
        
        Returns structured deletion confirmation with operation tracking.
        Warning: This operation is permanent and cannot be undone through the API.
        """
        
        # Helper functions for consistent results
        def _error(message: str) -> Dict[str, Any]:
            return ToolResult(status="error", message=message, error=message).model_dump()

        def _success(message: str, llm_content: Any, **data: Any) -> Dict[str, Any]:
            return ToolResult(
                status="success",
                message=message,
                llm_content=llm_content,
                data=data,
            ).model_dump()

        # Parameter validation and normalization

        # Validate required fields
        if not event_id or not event_id.strip():
            return _error("Event ID is required")

        try:
            # Get user email and build service
            user_email = get_user_email()
            service = build_google_calendar_service(user_email, tokens_dir=CALENDAR_OAUTH_TOKEN_DIR)
            
            # Execute calendar operation
            def delete_operation():
                service.events().delete(calendarId='primary', eventId=event_id).execute()
                return {}  # Delete returns empty response on success
            
            result = _execute_calendar_operation(
                CalendarOperationType.DELETE_EVENT,
                delete_operation,
            )
            
            # Build user-facing message
            if result.success:
                message = f"Deleted event {event_id} from primary calendar ({result.execution_time:.2f}s)"
            else:
                message = f"Failed to delete event: {result.error_message}"
            
            # Build structured LLM content
            llm_content = {
                "operation": {
                    "type": "delete_event"
                },
                "result": {
                    "deleted_event_id": event_id if result.success else None
                },
                "summary": {
                    "operation_type": "delete_event",
                    "success": result.success,
                    "has_warnings": len(result.warnings) > 0
                }
            }
            
            # Add warnings if any
            if result.warnings:
                llm_content["warnings"] = result.warnings
            
            return _success(message, llm_content, operation_result=result.to_dict())
            
        except Exception as e:
            if 'Not Found' in str(e):
                return _error(f"Event not found: {event_id} in primary calendar")
            else:
                return _error(f"Unexpected error deleting event: {str(e)}") 