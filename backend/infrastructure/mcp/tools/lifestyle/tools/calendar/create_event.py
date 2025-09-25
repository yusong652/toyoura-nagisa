"""Google Calendar create event tool.

This module provides the create_calendar_event tool for creating
new events in Google Calendar with comprehensive validation.
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
    validate_event_times
)

# -----------------------------------------------------------------------------
# Constants and configuration
# -----------------------------------------------------------------------------

CALENDAR_OAUTH_TOKEN_DIR = Path(os.getenv("CALENDAR_OAUTH_TOKEN_DIR", 
    Path(__file__).parents[7] / "credentials/google/tokens")).resolve()    


# Response helper functions moved to backend.infrastructure.mcp.utils.tool_result

# -----------------------------------------------------------------------------
# Create event tool
# -----------------------------------------------------------------------------

def register_create_event_tool(mcp: FastMCP):
    """Register the create calendar event tool."""
    
    common_tags = {"calendar", "schedule", "event", "google", "time"}
    common_annotations = {"category": "calendar", "tags": ["calendar", "schedule", "event", "google", "time"]}

    @mcp.tool(tags=common_tags, annotations=common_annotations)
    def create_calendar_event(
        summary: str = Field(..., description="Event summary/title."),
        start: Dict[str, int] = Field(..., description="Event start time. Provide a simple object with year, month, day, hour, minute. Example: {'year': 2025, 'month': 7, 'day': 30, 'hour': 10, 'minute': 0}"),
        end: Optional[Dict[str, int]] = Field(None, description="Event end time. If not provided, defaults to start time + 1 hour. Example: {'year': 2025, 'month': 7, 'day': 30, 'hour': 11, 'minute': 0}"),
        location: Optional[str] = Field(None, description="Event location (e.g., 'Conference Room A', '123 Main St')."),
        description: Optional[str] = Field(None, description="Event description or notes."),
    ) -> Dict[str, Any]:
        """Create a new event in Google Calendar."""

        # IMMEDIATE DEBUG: Check if function is called at all
        print("DEBUG: create_calendar_event function entered!")
        
        try:
            print(f"DEBUG: create_calendar_event called with summary={summary}, start={start}, end={end}")
            
            # If no end time provided, set to start + 1 hour
            if end is None:
                # Create end time by adding 1 hour to start time
                end = start.copy()
                end['hour'] = end.get('hour', 0) + 1
                # Handle hour overflow (e.g., 23:00 + 1 hour = next day 00:00)
                if end['hour'] >= 24:
                    end['hour'] = end['hour'] - 24
                    end['day'] = end.get('day', 1) + 1
                    # Note: This is a simple overflow handling
                    # More complex month/year overflow would need additional logic

            # Parameter processing - convert datetime objects to ISO strings
            start_str = None
            end_str = None

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
                start_str = processed_params.get('start', start)
                end_str = processed_params.get('end', end)
                location = processed_params.get('location', location)
                description = processed_params.get('description', description)
                
            except ValueError as e:
                print(f"DEBUG: ValueError in create_calendar_event parameter processing: {e}")
                return error_response(f"Invalid parameters: {str(e)}")

            warnings = []  # No warnings for now
            # Validate and parse datetime
            try:
                start_dt = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
                end_dt = datetime.fromisoformat(end_str.replace('Z', '+00:00'))
            except ValueError as e:
                return error_response(f"Invalid datetime format: {str(e)}. Please use RFC3339 format")

            # Validate time order
            time_error = validate_event_times(start_str, end_str)
            if time_error:
                return error_response(time_error)

            # No auto-correction - use exact times as provided by user

            start_iso = start_dt.strftime('%Y-%m-%dT%H:%M:%S%z').replace('+0000', 'Z').replace('-0000', 'Z')
            end_iso = end_dt.strftime('%Y-%m-%dT%H:%M:%S%z').replace('+0000', 'Z').replace('-0000', 'Z')
            
            # Get user email and build service
            user_email = get_user_email()
            service = build_google_calendar_service(user_email, tokens_dir=CALENDAR_OAUTH_TOKEN_DIR)
            
            # Prepare event data
            event_data = {
                'summary': summary,
                'start': {'dateTime': start_iso},
                'end': {'dateTime': end_iso}
            }
            
            if location:
                event_data['location'] = location
            if description:
                event_data['description'] = description
            
            # Execute calendar operation
            def create_operation():
                return service.events().insert(calendarId='primary', body=event_data).execute()
            
            result = execute_calendar_operation(
                CalendarOperationType.CREATE_EVENT,
                create_operation,
            )
            
            # Add validation warnings
            result["warnings"].extend(warnings)
            
            # Build simple success message
            if result["success"] and result["events"]:
                created_event = result["events"][0]
                message = f"Event '{created_event['summary']}' scheduled for {created_event['start']} - {created_event['end']}"
                llm_content = message
            elif result["success"]:
                message = "Event created successfully"
                llm_content = message
            else:
                message = result['error_message']
                llm_content = f"<error>{message}</error>"
            
            return success_response(message, llm_content, **result)
            
        except ValueError as e:
            return error_response(str(e))
        except Exception as e:
            if 'Not Found' in str(e):
                return error_response("Primary calendar not found")
            elif 'Invalid Value' in str(e):
                return error_response(f"Invalid event data: {str(e)}")
            else:
                return error_response(f"Unexpected error creating event: {str(e)}")
            