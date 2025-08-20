"""Google Calendar update event tool.

This module provides the update_calendar_event tool for modifying
existing events in Google Calendar with partial updates support.
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

from pydantic import Field
from fastmcp import FastMCP

from backend.infrastructure.auth.google.google_calendar import build_google_calendar_service
from backend.infrastructure.mcp.utils.tool_result import success_response, error_response
from backend.infrastructure.mcp.utils.user import get_user_email
from backend.infrastructure.mcp.utils.calendar_utils import (
    CalendarOperationType,
    execute_calendar_operation,
    parse_calendar_datetime_params,
)

# -----------------------------------------------------------------------------
# Constants and configuration
# -----------------------------------------------------------------------------

CALENDAR_OAUTH_TOKEN_DIR = Path(os.getenv("CALENDAR_OAUTH_TOKEN_DIR", 
    Path(__file__).parents[7] / "credentials/google/tokens")).resolve()    


# Response helper functions moved to backend.infrastructure.mcp.utils.tool_result

# -----------------------------------------------------------------------------
# Update event tool
# -----------------------------------------------------------------------------

def register_update_event_tool(mcp: FastMCP):
    """Register the update calendar event tool."""
    
    common_tags = {"calendar", "schedule", "event", "google", "time"}
    common_annotations = {"category": "calendar", "tags": ["calendar", "schedule", "event", "google", "time"]}

    @mcp.tool(tags=common_tags, annotations=common_annotations)
    def update_calendar_event(
        event_id: str = Field(..., description="ID of the event to update."),
        summary: Optional[str] = Field(None, description="New event summary/title."),
        start: Optional[Dict[str, int]] = Field(None, description="New start time. Provide a simple object with year, month, day, hour, minute. Example: {'year': 2025, 'month': 7, 'day': 30, 'hour': 10, 'minute': 0}"),
        end: Optional[Dict[str, int]] = Field(None, description="New end time. Provide a simple object with year, month, day, hour, minute. Example: {'year': 2025, 'month': 7, 'day': 30, 'hour': 11, 'minute': 0}"),
        location: Optional[str] = Field(None, description="New event location."),
        description: Optional[str] = Field(None, description="New event description."),
    ) -> Dict[str, Any]:
        """Update an existing event in Google Calendar."""
        

        # Parameter processing
        try:
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
            return error_response(f"Invalid parameters: {str(e)}")

        # Validate required fields
        if not event_id or not event_id.strip():
            return error_response("Event ID is required")
        
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
            return error_response("At least one field must be provided for update")

        warnings = []  # No warnings for now

        try:
            # Validate time order if both times are provided
            if start is not None and end is not None and isinstance(start, str) and isinstance(end, str):
                try:
                    # Handle timezone offset in ISO format
                    start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
                    end_dt = datetime.fromisoformat(end.replace('Z', '+00:00'))
                    if start_dt >= end_dt:
                        return error_response("Start time must be before end time")
                except ValueError:
                    # If parsing fails, skip validation
                    pass
            
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
                if isinstance(start, str):
                    existing_event['start']['dateTime'] = start
                    # Ensure timeZone is set
                    if 'timeZone' not in existing_event['start']:
                        existing_event['start']['timeZone'] = 'Asia/Tokyo'
            if end is not None:
                if isinstance(end, str):
                    existing_event['end']['dateTime'] = end
                    # Ensure timeZone is set
                    if 'timeZone' not in existing_event['end']:
                        existing_event['end']['timeZone'] = 'Asia/Tokyo'
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
            
            result = execute_calendar_operation(
                CalendarOperationType.UPDATE_EVENT,
                update_operation,
            )
            
            # Add validation warnings
            result["warnings"].extend(warnings)
            
            # Build simple success message
            if result["success"]:
                updated_event = result["events"][0]
                message = f"Updated event '{updated_event['summary']}' [ID: {updated_event['id']}]"
                llm_content = f"Updated event: {updated_event['summary']} [ID: {updated_event['id']}]"
            else:
                message = result['error_message']
                llm_content = f"<error>{message}</error>"
            
            return success_response(message, llm_content, **result)
            
        except Exception as e:
            if 'Not Found' in str(e):
                return error_response(f"Event not found: {event_id} in primary calendar")
            else:
                return error_response(f"Unexpected error updating event: {str(e)}")