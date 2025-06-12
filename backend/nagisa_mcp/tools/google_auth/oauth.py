import os
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
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
        tokens_dir: Optional, path to the tokens directory. Defaults to script directory/tokens
        credentials_path: (unused, for compatibility)
    Returns:
        Credentials object
    Raises:
        FileNotFoundError if token file does not exist
    """
    safe_email = email.replace('@', '_at_').replace('.', '_')
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if tokens_dir is None:
        tokens_dir = os.path.join(script_dir, 'tokens')
    token_path = os.path.join(tokens_dir, f'token_{safe_email}.json')
    if not os.path.exists(token_path):
        raise FileNotFoundError(f"Token file not found for {email}: {token_path}")
    creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    return creds

# 可扩展：save_token, load_token等辅助函数
