from googleapiclient.discovery import build
from .oauth import get_credentials

def get_gmail_service(email, tokens_dir=None):
    """
    Initialize and return a Gmail API service using OAuth2 credentials for the given email.
    Args:
        email: The Google account email address (str)
        tokens_dir: Optional, path to the tokens directory
    Returns:
        Gmail API service object
    Raises:
        FileNotFoundError if token file does not exist
    """
    creds = get_credentials(email, tokens_dir=tokens_dir)
    service = build('gmail', 'v1', credentials=creds)
    return service
