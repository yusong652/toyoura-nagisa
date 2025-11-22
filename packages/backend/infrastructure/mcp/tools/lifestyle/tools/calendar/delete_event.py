"""Google Calendar delete event tool.

This module provides the delete_calendar_event tool for removing
events from Google Calendar with proper validation and warnings.
"""

import os
from pathlib import Path
from typing import Dict, Any

from pydantic import Field
from fastmcp import FastMCP

from backend.infrastructure.auth.google.google_calendar import build_google_calendar_service
from backend.infrastructure.mcp.utils.tool_result import success_response, error_response
from backend.infrastructure.mcp.utils.user import get_user_email
from backend.infrastructure.mcp.utils.calendar_utils import (
    CalendarOperationType,
    execute_calendar_operation,
)

# -----------------------------------------------------------------------------
# Constants and configuration
# -----------------------------------------------------------------------------

CALENDAR_OAUTH_TOKEN_DIR = Path(os.getenv("CALENDAR_OAUTH_TOKEN_DIR", 
    Path(__file__).parents[7] / "credentials/google/tokens")).resolve()    


# Response helper functions moved to backend.infrastructure.mcp.utils.tool_result

# -----------------------------------------------------------------------------
# Delete event tool
# -----------------------------------------------------------------------------

def register_delete_event_tool(mcp: FastMCP):
    """Register the delete calendar event tool."""
    
    common_tags = {"calendar", "schedule", "event", "google", "time"}
    common_annotations = {"category": "calendar", "tags": ["calendar", "schedule", "event", "google", "time"]}

    @mcp.tool(tags=common_tags, annotations=common_annotations)
    def delete_calendar_event(
        event_id: str = Field(..., description="ID of the event to delete."),
    ) -> Dict[str, Any]:
        """Delete an event from Google Calendar.

        Warning: This operation is permanent and cannot be undone through the API.
        """
        

        # Parameter validation and normalization

        # Validate required fields
        if not event_id or not event_id.strip():
            return error_response("Event ID is required")

        try:
            # Get user email and build service
            user_email = get_user_email()
            service = build_google_calendar_service(user_email, tokens_dir=CALENDAR_OAUTH_TOKEN_DIR)
            
            # Get event summary before deletion
            event_info = service.events().get(
                calendarId='primary',
                eventId=event_id
            ).execute()
            event_summary = event_info.get('summary', 'Untitled Event')
            
            # Execute calendar operation
            def delete_operation():
                service.events().delete(calendarId='primary', eventId=event_id).execute()
                return {}  # Delete returns empty response on success
            
            result = execute_calendar_operation(
                CalendarOperationType.DELETE_EVENT,
                delete_operation,
            )
            
            # Build user-facing message
            if result["success"]:
                message = f"Deleted event '{event_summary}' [ID: {event_id}]"
            else:
                message = f"Failed to delete event: {result['error_message']}"
            
            # Build string-based LLM content (aligned with coding tools)
            if result["success"]:
                llm_content = f"Deleted event: {event_summary} [ID: {event_id}]"
                
                # Add warnings if any
                if result["warnings"]:
                    llm_content += "\n\nWarnings:\n" + "\n".join(f"⚠️  {w}" for w in result['warnings'])
            else:
                llm_content = f"<error>Failed to delete event: {result['error_message']}</error>"
            
            return success_response(
                message,
                llm_content={
                    "parts": [
                        {"type": "text", "text": llm_content}
                    ]
                },
                **result
            )
            
        except Exception as e:
            if 'Not Found' in str(e):
                return error_response(f"Event not found: {event_id} in primary calendar")
            else:
                return error_response(f"Unexpected error deleting event: {str(e)}")