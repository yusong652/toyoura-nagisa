import os
from pathlib import Path
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from backend.config import get_auth_config

SCOPES = [
    'openid',
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/userinfo.profile',
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/calendar.events',
    "https://www.googleapis.com/auth/contacts.readonly",
    
]

def get_credentials(email, tokens_dir=None):
    """
    Load OAuth2 credentials for the given email from the tokens directory.
    If token does not exist, raise FileNotFoundError.
    Args:
        email: The Google account email address (str)
        tokens_dir: Optional, path to the tokens directory. Defaults to project credentials/google/tokens
        credentials_path: (unused, for compatibility)
    Returns:
        Credentials object
    Raises:
        FileNotFoundError if token file does not exist
    """
    safe_email = email.replace('@', '_at_').replace('.', '_')
    
    if tokens_dir is None:
        # Use project root credentials directory
        project_root = Path(__file__).parent.parent.parent.parent.parent
        tokens_dir = project_root / 'credentials' / 'google' / 'tokens'
    
    token_path = Path(tokens_dir) / f'token_{safe_email}.json'
    if not token_path.exists():
        raise FileNotFoundError(f"Token file not found for {email}: {token_path}")
    
    creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    
    # Check if token is expired and try to refresh
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            # Save the refreshed token
            import json
            with open(token_path, 'w') as token_file:
                token_file.write(creds.to_json())
        except Exception as e:
            raise ValueError(f"Failed to refresh token for {email}: {str(e)}. Please re-authenticate.")
    
    # Check if credentials are valid
    if not creds or not creds.valid:
        raise ValueError(f"Invalid credentials for {email}. Please re-authenticate.")
    
    return creds

# 可扩展：save_token, load_token等辅助函数
