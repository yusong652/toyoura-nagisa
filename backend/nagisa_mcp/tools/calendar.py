from fastmcp import FastMCP
from pydantic import Field
from typing import List, Optional
from datetime import datetime
import os
from .google_auth.google_calendar import build_google_calendar_service

# 这里可以扩展更多模型和工具

def get_user_email():
    """Get the default user email address from USER_GMAIL_ADDRESS environment variable."""
    user_email = os.getenv("USER_GMAIL_ADDRESS")
    if not user_email:
        raise ValueError("USER_GMAIL_ADDRESS environment variable not set.")
    return user_email


def register_calendar_tools(mcp: FastMCP):
    """Register Google Calendar tools to MCP (OAuth2 version)"""

    @mcp.tool()
    def list_calendar_events(
        max_results: int = Field(10, description="Maximum number of events to retrieve."),
        calendar_id: str = Field('primary', description="Calendar ID to query. Default is 'primary'.")
    ) -> List[dict]:
        """
        List upcoming events from the user's Google Calendar.
        This tool can be used for: checking calendar, viewing schedule, listing calendar events, showing my calendar, querying upcoming meetings, etc.
        Example user queries: "show my calendar", "list my schedule", "check my events", "查查日历", "查看日程", "列出我的日历事件", "查询未来的会议安排".

        The user email is determined by the USER_GMAIL_ADDRESS environment variable.

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

    @mcp.tool()
    def add_calendar_event(
        summary: str = Field(..., description="Event summary/title."),
        start: str = Field(..., description="Event start time in RFC3339 format (e.g. 2024-06-06T10:00:00+09:00)."),
        end: str = Field(..., description="Event end time in RFC3339 format (e.g. 2024-06-06T11:00:00+09:00)."),
        calendar_id: str = Field('primary', description="Calendar ID to add event to. Default is 'primary'.")
    ) -> dict:
        """
        Add a new event to the user's Google Calendar.

        The user email is determined by the USER_GMAIL_ADDRESS environment variable.

        Args:
            summary (str): Event summary/title.
            start (str): Event start time in RFC3339 format.
            end (str): Event end time in RFC3339 format.
            calendar_id (str): Calendar ID to add event to. Default is 'primary'.

        Returns:
            dict: Contains 'status', 'event_id', and 'message'.
        """
        try:
            user_email = get_user_email()
            service = build_google_calendar_service(user_email)
            event = {
                'summary': summary,
                'start': {'dateTime': start},
                'end': {'dateTime': end}
            }
            created = service.events().insert(calendarId=calendar_id, body=event).execute()
            return {
                'status': 'success',
                'event_id': created['id'],
                'message': f"Event created: {created.get('htmlLink', '')}"
            }
        except Exception as e:
            return {'status': 'error', 'message': f'Failed to add event: {str(e)}'}

    @mcp.tool()
    def delete_calendar_event(
        event_id: str = Field(..., description="ID of the event to delete."),
        calendar_id: str = Field('primary', description="Calendar ID. Default is 'primary'.")
    ) -> dict:
        """
        Delete an event from the user's Google Calendar.

        The user email is determined by the USER_GMAIL_ADDRESS environment variable.

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

    @mcp.tool()
    def update_calendar_event(
        event_id: str = Field(..., description="ID of the event to update."),
        summary: Optional[str] = Field(None, description="New summary/title for the event."),
        start: Optional[str] = Field(None, description="New start time in RFC3339 format."),
        end: Optional[str] = Field(None, description="New end time in RFC3339 format."),
        calendar_id: str = Field('primary', description="Calendar ID. Default is 'primary'.")
    ) -> dict:
        """
        Update an event in the user's Google Calendar.

        The user email is determined by the USER_GMAIL_ADDRESS environment variable.

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