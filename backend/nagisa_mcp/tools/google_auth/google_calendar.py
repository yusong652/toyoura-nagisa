from googleapiclient.discovery import build
from .oauth import get_credentials

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
    service = build('calendar', 'v3', credentials=creds)
    return service 