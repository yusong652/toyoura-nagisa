from googleapiclient.discovery import build
from .oauth import get_credentials
from google.auth.transport.requests import Request

def build_google_calendar_service(email, tokens_dir=None):
    """
    Initialize and return a Google Calendar API service using OAuth2 credentials for the given email.
    Args:
        email: The Google account email address (str)
        tokens_dir: Optional, path to the tokens directory
    Returns:
        Google Calendar API service object
    Raises:
        FileNotFoundError if token file does not exist
    """
    creds = get_credentials(email, tokens_dir=tokens_dir)
    
    # Check if credentials need to be refreshed
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except Exception as e:
            raise Exception(f"Failed to refresh credentials: {str(e)}")
    
    service = build('calendar', 'v3', credentials=creds)
    return service 