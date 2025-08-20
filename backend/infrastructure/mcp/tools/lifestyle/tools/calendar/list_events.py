"""Google Calendar list events tool.

This module provides the list_calendar_events tool for retrieving
events from Google Calendar with filtering and pagination support.
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime, timezone, timedelta

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

# Default limits for calendar operations
DEFAULT_MAX_EVENTS = 100
MAX_EVENTS_HARD_LIMIT = 100

# Calendar operation timeouts
CALENDAR_OPERATION_TIMEOUT = 30  # seconds

CALENDAR_OAUTH_TOKEN_DIR = Path(os.getenv("CALENDAR_OAUTH_TOKEN_DIR", 
    Path(__file__).parents[7] / "credentials/google/tokens")).resolve()    


# Response helper functions moved to backend.infrastructure.mcp.utils.tool_result

# -----------------------------------------------------------------------------
# List events tool
# -----------------------------------------------------------------------------

def register_list_events_tool(mcp: FastMCP):
    """Register the list calendar events tool."""
    
    common_tags = {"calendar", "schedule", "event", "google", "time"}
    common_annotations = {"category": "calendar", "tags": ["calendar", "schedule", "event", "google", "time"]}

    @mcp.tool(tags=common_tags, annotations=common_annotations)
    def list_calendar_events(
        max_results: Optional[int] = Field(
            DEFAULT_MAX_EVENTS,
            ge=1,
            le=MAX_EVENTS_HARD_LIMIT,
            description="Maximum number of events to retrieve.",
        ),
        time_min: Optional[Dict[str, int]] = Field(
            None,
            description="Start time filter. If not provided, defaults to current time to show upcoming events. Example: {'year': 2025, 'month': 7, 'day': 30}",
        ),
        time_max: Optional[Dict[str, int]] = Field(
            None,
            description="End time filter. If not provided, defaults to 1 year from start time to limit recurring events like birthdays. Example: {'year': 2025, 'month': 7, 'day': 31}",
        ),
    ) -> Dict[str, Any]:
        """List events from Google Calendar. Automatically limits recurring events like birthdays to within 1 year. If no time filter is provided, shows upcoming events from current time."""
        
        try:
            print(f"DEBUG: list_calendar_events called with time_min={time_min}, time_max={time_max}, max_results={max_results}")
            
            # Set default if None
            if max_results is None:
                max_results = DEFAULT_MAX_EVENTS

            # Convert simple datetime parameters to ISO strings
            try:
                processed_params = parse_calendar_datetime_params(
                    time_min=time_min,
                    time_max=time_max
                )
                
                time_min = processed_params.get('time_min')
                time_max = processed_params.get('time_max')
                
            except ValueError as e:
                print(f"DEBUG: ValueError in parameter processing: {e}")
                return error_response(f"Invalid parameters: {str(e)}")

            # If no time_min provided, default to current time to get upcoming events
            if time_min is None:
                current_time = datetime.now(timezone.utc)
                time_min = current_time.isoformat()
                print(f"DEBUG: No time_min provided, defaulting to current time: {time_min}")

            # If no time_max provided, default to 1 year from time_min to prevent endless recurring events
            if time_max is None and time_min:
                # Parse the time_min to add 1 year
                start_time = datetime.fromisoformat(time_min.replace('Z', '+00:00'))
                end_time = start_time + timedelta(days=365)  # 1 year
                time_max = end_time.isoformat()
                print(f"DEBUG: No time_max provided, defaulting to 1 year from start: {time_max}")

            print(f"DEBUG: After parameter processing - time_min={time_min}, time_max={time_max}")

            # Validate parameters
            if max_results <= 0 or max_results > MAX_EVENTS_HARD_LIMIT:
                error_msg = f"max_results must be between 1 and {MAX_EVENTS_HARD_LIMIT}"
                return error_response(error_msg)

            # Get user email and build service
            print("DEBUG: Getting user email...")
            user_email = get_user_email()
            if not user_email:
                return error_response("USER_GMAIL_ADDRESS environment variable not set")
            
            print(f"DEBUG: Building calendar service for {user_email}")
            service = build_google_calendar_service(user_email, tokens_dir=CALENDAR_OAUTH_TOKEN_DIR)
            if not service:
                return error_response("Failed to build Google Calendar service")
            
            print("DEBUG: Calendar service built successfully")
            
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
            if time_max:
                query_params['timeMax'] = time_max
            
            # Execute calendar operation
            print(f"DEBUG: Executing calendar operation with params: {query_params}")
            def list_operation():
                return service.events().list(**query_params).execute()
            result = execute_calendar_operation(
                CalendarOperationType.LIST_EVENTS,
                list_operation,
            )
            
            print(f"DEBUG: Calendar operation result: {result}")
            
            # Debug: log the result structure
            if not result.get("success", False):
                return error_response(f"Calendar operation failed: {result.get('error_message', 'Unknown error')}")
            
            # Build user-facing message
            if result["success"]:
                message = "Retrieved events from primary calendar"
            else:
                message = f"Failed to retrieve events: {result['error_message']}"
            
            # Build string-based LLM content (aligned with coding tools)
            if result["success"]:
                if result["total_events"] == 0:
                    llm_content = "No events found."
                else:
                    # Format events as readable text
                    events_text = []
                    for event in result["events"]:
                        event_line = f"• {event['summary']} ({event['start']} - {event['end']}) [ID: {event['id']}]"
                        if event.get('location'):
                            event_line += f" at {event['location']}"
                        if event.get('status') != "confirmed":
                            event_line += f" [{event['status']}]"
                        events_text.append(event_line)
                    
                    llm_content = "Found events:\n\n" + "\n".join(events_text)
                    
                    # Add warnings if any
                    if result["warnings"]:
                        llm_content += "\n\nWarnings:\n" + "\n".join(f"⚠️  {w}" for w in result['warnings'])
            else:
                llm_content = f"<error>Failed to list events: {result['error_message']}</error>"
            
            print(f"DEBUG: Returning success response - message: {message}")
            print(f"DEBUG: LLM content: {llm_content}")
            response = success_response(message, llm_content, **result)
            print(f"DEBUG: Final response: {response}")
            return response
            
        except ValueError as e:
            print(f"DEBUG: ValueError: {e}")
            return error_response(str(e))
        except Exception as e:
            print(f"DEBUG: Unexpected error: {e}")
            print(f"DEBUG: Exception type: {type(e)}")
            import traceback
            print(f"DEBUG: Traceback: {traceback.format_exc()}")
            return error_response(f"Unexpected error listing events: {str(e)}")