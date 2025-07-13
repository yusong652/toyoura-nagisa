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

from backend.nagisa_mcp.tools.google_auth.google_calendar import build_google_calendar_service
from backend.nagisa_mcp.utils.tool_result import ToolResult
from backend.nagisa_mcp.utils import ensure_future_datetime

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
    calendar_id: str = "primary"
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
            "calendar_id": self.calendar_id,
            "created": self.created,
            "updated": self.updated,
            "html_link": self.html_link,
        }

@dataclass
class CalendarOperationResult:
    """Result of a calendar operation with metadata."""
    operation_type: CalendarOperationType
    success: bool
    events: List[CalendarEvent]
    calendar_id: str
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
            "calendar_id": self.calendar_id,
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "operation_metadata": {
                "operation_type": self.operation_type.value,
                "calendar_id": self.calendar_id,
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
    
    # Validate time format if provided
    if start:
        try:
            datetime.fromisoformat(start.replace('Z', '+00:00'))
        except ValueError:
            warnings.append("Invalid start time format. Please use RFC3339 format")
    
    if end:
        try:
            datetime.fromisoformat(end.replace('Z', '+00:00'))
        except ValueError:
            warnings.append("Invalid end time format. Please use RFC3339 format")
    
    return warnings

def _parse_calendar_event(event_data: Dict[str, Any], calendar_id: str) -> CalendarEvent:
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
        calendar_id=calendar_id,
        created=event_data.get('created'),
        updated=event_data.get('updated'),
        html_link=event_data.get('htmlLink'),
    )

def _execute_calendar_operation(
    operation_type: CalendarOperationType,
    operation_func,
    calendar_id: str = "primary",
    **kwargs
) -> CalendarOperationResult:
    """Execute a calendar operation with error handling and timing."""
    start_time = time.time()
    
    try:
        result = operation_func(**kwargs)
        execution_time = time.time() - start_time
        
        # Parse result based on operation type
        if operation_type == CalendarOperationType.LIST_EVENTS:
            events = [_parse_calendar_event(event, calendar_id) for event in result.get('items', [])]
            return CalendarOperationResult(
                operation_type=operation_type,
                success=True,
                events=events,
                calendar_id=calendar_id,
                execution_time=execution_time,
                total_events=len(events),
            )
        else:
            # Single event operations
            event = _parse_calendar_event(result, calendar_id) if result else None
            return CalendarOperationResult(
                operation_type=operation_type,
                success=True,
                events=[event] if event else [],
                calendar_id=calendar_id,
                execution_time=execution_time,
                total_events=1 if event else 0,
            )
            
    except Exception as e:
        execution_time = time.time() - start_time
        return CalendarOperationResult(
            operation_type=operation_type,
            success=False,
            events=[],
            calendar_id=calendar_id,
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
        calendar_id: str = Field(
            'primary',
            description="Calendar ID to query. Use 'primary' for main calendar.",
        ),
        time_min: Optional[str] = Field(
            None,
            description="Lower bound (exclusive) for events to filter by. RFC3339 format (e.g., '2024-01-01T00:00:00Z').",
        ),
        time_max: Optional[str] = Field(
            None,
            description="Upper bound (exclusive) for events to filter by. RFC3339 format (e.g., '2024-12-31T23:59:59Z').",
        ),
    ) -> Dict[str, Any]:
        """
        List upcoming events from Google Calendar with comprehensive filtering and metadata.
        
        This tool provides atomic calendar listing functionality, focusing exclusively on
        retrieving and organizing calendar events with rich metadata. It supports time-based
        filtering, pagination, and detailed event information.
        
        ## Return Value
        **For LLM:** Returns structured data with consistent format across all calendar tools.
        
        **Structure:**
        ```json
        {
          "operation": {
            "type": "list_events",
            "calendar_id": "primary",
            "max_results": 10,
            "time_range": {
              "start": "2024-01-01T00:00:00Z",
              "end": "2024-12-31T23:59:59Z"
            }
          },
          "result": {
            "events": [
              {
                "id": "event_id_123",
                "summary": "Team Meeting",
                "start": "2024-06-06T10:00:00+09:00",
                "end": "2024-06-06T11:00:00+09:00",
                "location": "Conference Room A",
                "status": "confirmed"
              }
            ],
            "total_events": 5,
            "execution_time": 1.23,
            "success": true
          },
          "summary": {
            "operation_type": "list_events",
            "success": true,
            "total_events": 5,
            "performance_category": "fast",
            "has_warnings": false
          }
        }
        ```
        
        ## Core Functionality
        Lists calendar events with comprehensive filtering, sorting, and metadata analysis.
        
        ## Strategic Usage
        Use this tool to **query calendar events** with time-based filtering and rich metadata.
        
        Access results through the structured response: `result.events` for event list,
        `result.total_events` for count, `summary.success` for operation status.
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
        if isinstance(max_results, FieldInfo):
            max_results = DEFAULT_MAX_EVENTS
        if isinstance(calendar_id, FieldInfo):
            calendar_id = 'primary'
        if isinstance(time_min, FieldInfo):
            time_min = None
        if isinstance(time_max, FieldInfo):
            time_max = None

        # Validate parameters
        if max_results <= 0 or max_results > MAX_EVENTS_HARD_LIMIT:
            return _error(f"max_results must be between 1 and {MAX_EVENTS_HARD_LIMIT}")

        try:
            # Get user email and build service
            user_email = get_user_email()
            service = build_google_calendar_service(user_email)
            
            # Prepare query parameters
            query_params = {
                'calendarId': calendar_id,
                'maxResults': max_results,
                'singleEvents': True,
                'orderBy': 'startTime'
            }
            
            # Set time bounds
            if time_min:
                query_params['timeMin'] = time_min
            else:
                query_params['timeMin'] = datetime.utcnow().isoformat() + 'Z'
            
            if time_max:
                query_params['timeMax'] = time_max
            
            # Execute calendar operation
            def list_operation():
                return service.events().list(**query_params).execute()
            
            result = _execute_calendar_operation(
                CalendarOperationType.LIST_EVENTS,
                list_operation,
                calendar_id=calendar_id,
            )
            
            # Build user-facing message
            if result.success:
                events_word = "event" if result.total_events == 1 else "events"
                message = f"Retrieved {result.total_events} {events_word} from {calendar_id} ({result.execution_time:.2f}s)"
            else:
                message = f"Failed to retrieve events: {result.error_message}"
            
            # Build structured LLM content
            llm_content = {
                "operation": {
                    "type": "list_events",
                    "calendar_id": calendar_id,
                    "max_results": max_results,
                    "time_range": {
                        "start": time_min,
                        "end": time_max
                    }
                },
                "result": {
                    "events": [event.to_dict() for event in result.events],
                    "total_events": result.total_events,
                    "execution_time": result.execution_time,
                    "success": result.success
                },
                "summary": result.get_summary()
            }
            
            # Add warnings if any
            if result.warnings:
                llm_content["warnings"] = result.warnings
            
            return _success(message, llm_content, **result.to_dict())
            
        except ValueError as e:
            return _error(str(e))
        except Exception as e:
            return _error(f"Unexpected error listing events: {str(e)}")

    @mcp.tool(tags=common_tags, annotations=common_annotations)
    def create_calendar_event(
        summary: str = Field(..., description="Event summary/title (required)."),
        start: str = Field(..., description="Event start time in RFC3339 format (e.g., '2024-06-06T10:00:00+09:00')."),
        end: str = Field(..., description="Event end time in RFC3339 format (e.g., '2024-06-06T11:00:00+09:00')."),
        location: Optional[str] = Field(None, description="Event location (e.g., 'Conference Room A', '123 Main St')."),
        description: Optional[str] = Field(None, description="Event description or notes."),
        calendar_id: str = Field('primary', description="Calendar ID to add event to. Use 'primary' for main calendar."),
    ) -> Dict[str, Any]:
        """
        Create a new event in Google Calendar with comprehensive validation and metadata.
        
        This tool provides atomic event creation functionality, focusing exclusively on
        creating calendar events with rich validation, automatic future date correction,
        and comprehensive metadata tracking.
        
        ## Return Value
        **For LLM:** Returns structured data with consistent format across all calendar tools.
        
        **Structure:**
        ```json
        {
          "operation": {
            "type": "create_event",
            "calendar_id": "primary",
            "event_data": {
              "summary": "Team Meeting",
              "start": "2024-06-06T10:00:00+09:00",
              "end": "2024-06-06T11:00:00+09:00",
              "location": "Conference Room A"
            }
          },
          "result": {
            "event": {
              "id": "event_id_123",
              "summary": "Team Meeting",
              "start": "2024-06-06T10:00:00+09:00",
              "end": "2024-06-06T11:00:00+09:00",
              "html_link": "https://calendar.google.com/event?eid=..."
            },
            "success": true,
            "execution_time": 0.85
          },
          "summary": {
            "operation_type": "create_event",
            "success": true,
            "performance_category": "fast",
            "has_warnings": false
          }
        }
        ```
        
        ## Core Functionality
        Creates calendar events with automatic future date correction and comprehensive validation.
        
        ## Strategic Usage
        Use this tool to **create calendar events** with intelligent date handling and validation.
        
        **Important:** If the user input does not specify a year, the system will automatically
        calculate the next upcoming occurrence of that date in the future.
        
        Access results through the structured response: `result.event` for created event,
        `result.success` for operation status, `summary.has_warnings` for validation issues.
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
        if isinstance(location, FieldInfo):
            location = None
        if isinstance(description, FieldInfo):
            description = None
        if isinstance(calendar_id, FieldInfo):
            calendar_id = 'primary'

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
            
            # Auto-correct to future time
            now = datetime.now(start_dt.tzinfo)
            start_dt = ensure_future_datetime(start_dt, now)
            end_dt = ensure_future_datetime(end_dt, now)
            start = start_dt.isoformat()
            end = end_dt.isoformat()
            
            # Get user email and build service
            user_email = get_user_email()
            service = build_google_calendar_service(user_email)
            
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
                return service.events().insert(calendarId=calendar_id, body=event_data).execute()
            
            result = _execute_calendar_operation(
                CalendarOperationType.CREATE_EVENT,
                create_operation,
                calendar_id=calendar_id,
            )
            
            # Add validation warnings
            result.warnings.extend(warnings)
            
            # Build user-facing message
            if result.success:
                created_event = result.events[0]
                message = f"Created event '{created_event.summary}' in {calendar_id} ({result.execution_time:.2f}s)"
            else:
                message = f"Failed to create event: {result.error_message}"
            
            # Build structured LLM content
            llm_content = {
                "operation": {
                    "type": "create_event",
                    "calendar_id": calendar_id,
                    "event_data": {
                        "summary": summary,
                        "start": start,
                        "end": end,
                        "location": location,
                        "description": description
                    }
                },
                "result": {
                    "event": result.events[0].to_dict() if result.events else None,
                    "success": result.success,
                    "execution_time": result.execution_time
                },
                "summary": result.get_summary()
            }
            
            # Add warnings if any
            if result.warnings:
                llm_content["warnings"] = result.warnings
            
            return _success(message, llm_content, **result.to_dict())
            
        except ValueError as e:
            return _error(str(e))
        except Exception as e:
            if 'Not Found' in str(e):
                return _error(f"Calendar not found: {calendar_id}")
            elif 'Invalid Value' in str(e):
                return _error(f"Invalid event data: {str(e)}")
            else:
                return _error(f"Unexpected error creating event: {str(e)}")

    @mcp.tool(tags=common_tags, annotations=common_annotations)
    def update_calendar_event(
        event_id: str = Field(..., description="ID of the event to update."),
        summary: Optional[str] = Field(None, description="New event summary/title."),
        start: Optional[str] = Field(None, description="New start time in RFC3339 format."),
        end: Optional[str] = Field(None, description="New end time in RFC3339 format."),
        location: Optional[str] = Field(None, description="New event location."),
        description: Optional[str] = Field(None, description="New event description."),
        calendar_id: str = Field('primary', description="Calendar ID containing the event."),
    ) -> Dict[str, Any]:
        """
        Update an existing event in Google Calendar with comprehensive validation.
        
        This tool provides atomic event update functionality, focusing exclusively on
        modifying calendar events with rich validation, partial updates support,
        and comprehensive metadata tracking.
        
        ## Return Value
        **For LLM:** Returns structured data with consistent format across all calendar tools.
        
        **Structure:**
        ```json
        {
          "operation": {
            "type": "update_event",
            "event_id": "event_id_123",
            "calendar_id": "primary",
            "updates": {
              "summary": "Updated Team Meeting",
              "location": "New Conference Room"
            }
          },
          "result": {
            "event": {
              "id": "event_id_123",
              "summary": "Updated Team Meeting",
              "start": "2024-06-06T10:00:00+09:00",
              "end": "2024-06-06T11:00:00+09:00",
              "location": "New Conference Room",
              "html_link": "https://calendar.google.com/event?eid=..."
            },
            "success": true,
            "execution_time": 0.92
          },
          "summary": {
            "operation_type": "update_event",
            "success": true,
            "performance_category": "fast",
            "has_warnings": false
          }
        }
        ```
        
        ## Core Functionality
        Updates calendar events with partial field updates and comprehensive validation.
        
        ## Strategic Usage
        Use this tool to **modify calendar events** with selective field updates and validation.
        
        **Note:** Only provide the fields you want to update. Omitted fields will remain unchanged.
        
        Access results through the structured response: `result.event` for updated event,
        `result.success` for operation status, `summary.has_warnings` for validation issues.
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
        if isinstance(calendar_id, FieldInfo):
            calendar_id = 'primary'

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
            # Get user email and build service
            user_email = get_user_email()
            service = build_google_calendar_service(user_email)
            
            # Get existing event
            existing_event = service.events().get(
                calendarId=calendar_id,
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
                    calendarId=calendar_id,
                    eventId=event_id,
                    body=existing_event
                ).execute()
            
            result = _execute_calendar_operation(
                CalendarOperationType.UPDATE_EVENT,
                update_operation,
                calendar_id=calendar_id,
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
                    "type": "update_event",
                    "event_id": event_id,
                    "calendar_id": calendar_id,
                    "updates": updates
                },
                "result": {
                    "event": result.events[0].to_dict() if result.events else None,
                    "success": result.success,
                    "execution_time": result.execution_time
                },
                "summary": result.get_summary()
            }
            
            # Add warnings if any
            if result.warnings:
                llm_content["warnings"] = result.warnings
            
            return _success(message, llm_content, **result.to_dict())
            
        except Exception as e:
            if 'Not Found' in str(e):
                return _error(f"Event or calendar not found: {event_id} in {calendar_id}")
            else:
                return _error(f"Unexpected error updating event: {str(e)}")

    @mcp.tool(tags=common_tags, annotations=common_annotations)
    def delete_calendar_event(
        event_id: str = Field(..., description="ID of the event to delete."),
        calendar_id: str = Field('primary', description="Calendar ID containing the event."),
    ) -> Dict[str, Any]:
        """
        Delete an event from Google Calendar with comprehensive validation and metadata.
        
        This tool provides atomic event deletion functionality, focusing exclusively on
        removing calendar events with comprehensive validation, confirmation tracking,
        and detailed operation metadata.
        
        ## Return Value
        **For LLM:** Returns structured data with consistent format across all calendar tools.
        
        **Structure:**
        ```json
        {
          "operation": {
            "type": "delete_event",
            "event_id": "event_id_123",
            "calendar_id": "primary"
          },
          "result": {
            "success": true,
            "execution_time": 0.67,
            "deleted_event_id": "event_id_123"
          },
          "summary": {
            "operation_type": "delete_event",
            "success": true,
            "performance_category": "fast",
            "has_warnings": false
          }
        }
        ```
        
        ## Core Functionality
        Deletes calendar events with comprehensive validation and operation tracking.
        
        ## Strategic Usage
        Use this tool to **remove calendar events** with proper validation and confirmation.
        
        **Warning:** This operation is permanent and cannot be undone through the API.
        
        Access results through the structured response: `result.success` for operation status,
        `result.deleted_event_id` for confirmation, `summary.performance_category` for timing.
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
        if isinstance(calendar_id, FieldInfo):
            calendar_id = 'primary'

        # Validate required fields
        if not event_id or not event_id.strip():
            return _error("Event ID is required")

        try:
            # Get user email and build service
            user_email = get_user_email()
            service = build_google_calendar_service(user_email)
            
            # Execute calendar operation
            def delete_operation():
                service.events().delete(calendarId=calendar_id, eventId=event_id).execute()
                return {}  # Delete returns empty response on success
            
            result = _execute_calendar_operation(
                CalendarOperationType.DELETE_EVENT,
                delete_operation,
                calendar_id=calendar_id,
            )
            
            # Build user-facing message
            if result.success:
                message = f"Deleted event {event_id} from {calendar_id} ({result.execution_time:.2f}s)"
            else:
                message = f"Failed to delete event: {result.error_message}"
            
            # Build structured LLM content
            llm_content = {
                "operation": {
                    "type": "delete_event",
                    "event_id": event_id,
                    "calendar_id": calendar_id
                },
                "result": {
                    "success": result.success,
                    "execution_time": result.execution_time,
                    "deleted_event_id": event_id if result.success else None
                },
                "summary": result.get_summary()
            }
            
            # Add warnings if any
            if result.warnings:
                llm_content["warnings"] = result.warnings
            
            return _success(message, llm_content, **result.to_dict())
            
        except Exception as e:
            if 'Not Found' in str(e):
                return _error(f"Event not found: {event_id} in {calendar_id}")
            else:
                return _error(f"Unexpected error deleting event: {str(e)}") 