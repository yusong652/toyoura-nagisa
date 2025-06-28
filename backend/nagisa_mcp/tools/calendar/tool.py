from fastmcp import FastMCP
from pydantic import Field
from typing import List, Optional
from datetime import datetime
import os
from backend.nagisa_mcp.tools.google_auth.google_calendar import build_google_calendar_service
from backend.nagisa_mcp.utils import ensure_future_datetime

# 这里可以扩展更多模型和工具

def get_user_email():
    """Get the default user email address from USER_GMAIL_ADDRESS environment variable."""
    user_email = os.getenv("USER_GMAIL_ADDRESS")
    if not user_email:
        raise ValueError("USER_GMAIL_ADDRESS environment variable not set.")
    return user_email


def register_calendar_tools(mcp: FastMCP):
    """Register Google Calendar tools to MCP (OAuth2 version)"""

    @mcp.tool(tags={"calendar"}, annotations={"category": "calendar"})
    def list_calendar_events(
        max_results: int = Field(10, description="Maximum number of events to retrieve."),
        calendar_id: str = Field('primary', description="Calendar ID to query. Default is 'primary'.")
    ) -> List[dict]:
        """
        List upcoming events from the user's Google Calendar.
        This tool can be used for: checking calendar, viewing schedule, listing calendar events, querying upcoming meetings, etc.

        Args:
            max_results (int): Maximum number of events to retrieve. Default is 10.
            calendar_id (str): Calendar ID to query. Default is 'primary'.

        Returns:
            List[dict]: A list of event dictionaries, each containing:
                - id (str): Event ID
                - summary (str): Event summary/title
                - start (str): Start time (ISO format)
                - end (str): End time (ISO format)
        """
        try:
            user_email = get_user_email()
            service = build_google_calendar_service(user_email)
            now = datetime.utcnow().isoformat() + 'Z'
            events_result = service.events().list(
                calendarId=calendar_id, timeMin=now, maxResults=max_results, singleEvents=True, orderBy='startTime'
            ).execute()
            events = events_result.get('items', [])
            return [
                {
                    'id': event['id'],
                    'summary': event.get('summary', ''),
                    'start': event['start'].get('dateTime', event['start'].get('date', '')),
                    'end': event['end'].get('dateTime', event['end'].get('date', ''))
                }
                for event in events
            ]
        except Exception as e:
            return [{"error": f"Failed to list events: {str(e)}"}]

    @mcp.tool(tags={"calendar"}, annotations={"category": "calendar"})
    def create_calendar_event(
        summary: str = Field(..., description="Event summary/title."),
        start: str = Field(..., description="Event start time in RFC3339 format (e.g. 2024-06-06T10:00:00+09:00)."),
        end: str = Field(..., description="Event end time in RFC3339 format (e.g. 2024-06-06T11:00:00+09:00)."),
        location: Optional[str] = Field(None, description="Event location (e.g. 'Conference Room A', '123 Main St, City')."),
        calendar_id: str = Field('primary', description="Calendar ID to add event to. Default is 'primary'.")
    ) -> dict:
        """
        Create a new event in the user's Google Calendar.

        **Important for LLM/Agent:**
        If the user input does not specify a year, you should first check the current date (by calling the get_current_time tool),
        and complete the date as the next upcoming occurrence of that date in the future. This ensures the event is always scheduled in the future.

        Args:
            summary (str): Event summary/title.
            start (str): Event start time in RFC3339 format.
            end (str): Event end time in RFC3339 format.
            location (Optional[str]): Event location. Can be a room name, address, or any location description.
            calendar_id (str): Calendar ID to add event to. Default is 'primary'.

        Returns:
            dict: Contains 'status', 'event_id', and 'message'.
        """
        try:
            user_email = get_user_email()
            service = build_google_calendar_service(user_email)
            
            # Validate date format
            try:
                start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
                end_dt = datetime.fromisoformat(end.replace('Z', '+00:00'))
            except ValueError as e:
                return {
                    'status': 'error',
                    'message': f'Invalid date format: {str(e)}. Please use RFC3339 format (e.g. 2024-06-06T10:00:00+09:00)'
                }
            # 自动修正为未来时间
            now = datetime.now(start_dt.tzinfo)
            start_dt = ensure_future_datetime(start_dt, now)
            end_dt = ensure_future_datetime(end_dt, now)
            start = start_dt.isoformat()
            end = end_dt.isoformat()
            
            event = {
                'summary': summary,
                'start': {'dateTime': start},
                'end': {'dateTime': end}
            }
            
            if location:
                event['location'] = location
            
            try:
                created = service.events().insert(calendarId=calendar_id, body=event).execute()
                return {
                    'status': 'success',
                    'event_id': created['id'],
                    'message': f"Event created: {created.get('htmlLink', '')}"
                }
            except Exception as e:
                if 'Not Found' in str(e):
                    return {
                        'status': 'error',
                        'message': f'Calendar not found: {calendar_id}. Please check if the calendar ID is correct.'
                    }
                elif 'Invalid Value' in str(e):
                    return {
                        'status': 'error',
                        'message': f'Invalid event data: {str(e)}'
                    }
                else:
                    raise e
                    
        except FileNotFoundError as e:
            return {
                'status': 'error',
                'message': f'Authentication error: {str(e)}. Please make sure you have completed the OAuth2 setup.'
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Failed to create event: {str(e)}'
            }

    @mcp.tool(tags={"calendar"}, annotations={"category": "calendar"})
    def delete_calendar_event(
        event_id: str = Field(..., description="ID of the event to delete."),
        calendar_id: str = Field('primary', description="Calendar ID. Default is 'primary'.")
    ) -> dict:
        """
        Delete an event from the user's Google Calendar.

        Args:
            event_id (str): ID of the event to delete.
            calendar_id (str): Calendar ID. Default is 'primary'.

        Returns:
            dict: Contains 'status' and 'message'.
        """
        try:
            user_email = get_user_email()
            service = build_google_calendar_service(user_email)
            service.events().delete(calendarId=calendar_id, eventId=event_id).execute()
            return {'status': 'success', 'message': f'Event {event_id} deleted.'}
        except Exception as e:
            return {'status': 'error', 'message': f'Failed to delete event: {str(e)}'}

    @mcp.tool(tags={"calendar"}, annotations={"category": "calendar"})
    def update_calendar_event(
        event_id: str = Field(..., description="ID of the event to update."),
        summary: Optional[str] = Field(None, description="New summary/title for the event."),
        start: Optional[str] = Field(None, description="New start time in RFC3339 format."),
        end: Optional[str] = Field(None, description="New end time in RFC3339 format."),
        calendar_id: str = Field('primary', description="Calendar ID. Default is 'primary'.")
    ) -> dict:
        """
        Update an event in the user's Google Calendar.

        Args:
            event_id (str): ID of the event to update.
            summary (Optional[str]): New summary/title for the event.
            start (Optional[str]): New start time in RFC3339 format.
            end (Optional[str]): New end time in RFC3339 format.
            calendar_id (str): Calendar ID. Default is 'primary'.

        Returns:
            dict: Contains 'status', 'event_id', and 'message'.
        """
        try:
            user_email = get_user_email()
            service = build_google_calendar_service(user_email)
            event = service.events().get(calendarId=calendar_id, eventId=event_id).execute()
            if summary:
                event['summary'] = summary
            if start:
                event['start']['dateTime'] = start
            if end:
                event['end']['dateTime'] = end
            updated = service.events().update(calendarId=calendar_id, eventId=event_id, body=event).execute()
            return {
                'status': 'success',
                'event_id': updated['id'],
                'message': f"Event updated: {updated.get('htmlLink', '')}"
            }
        except Exception as e:
            return {'status': 'error', 'message': f'Failed to update event: {str(e)}'}

    # 可选：为示例添加其他标签
    extra_tags = {"google"}
    for func in [list_calendar_events, create_calendar_event, delete_calendar_event, update_calendar_event]:
        func.tags.update(extra_tags) 