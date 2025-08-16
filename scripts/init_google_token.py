import os
import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from backend.infrastructure.auth.google.oauth import SCOPES

def main():
    """
    Run this script to complete Google OAuth2 flow in your browser and save token.json for each account.
    Token will be saved as tokens/token_{email}.json
    """
    # Use the secure credentials directory for credentials and tokens
    credentials_dir = project_root / 'credentials' / 'google'
    credentials_path = credentials_dir / 'credentials.json'
    tokens_dir = credentials_dir / 'tokens'
    os.makedirs(tokens_dir, exist_ok=True)

    if not os.path.exists(credentials_path):
        print(f"Please download your credentials.json from Google Cloud Console and place it at: {credentials_path}")
        return

    flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
    # 强制Google返回refresh_token
    creds = flow.run_local_server(
        port=8080,
        authorization_prompt_message='Please visit this URL: {url}',
        success_message='The auth flow is complete; you may close this window.',
        open_browser=True,
        prompt='consent',
        access_type='offline'
    )

    # 获取当前账户email
    service = build('oauth2', 'v2', credentials=creds)
    user_info = service.userinfo().get().execute()
    email = user_info['email']
    safe_email = email.replace('@', '_at_').replace('.', '_')
    token_path = os.path.join(tokens_dir, f'token_{safe_email}.json')

    # Check if token already exists and inform user
    if os.path.exists(token_path):
        print(f"Updating existing token for {email}")
    else:
        print(f"Creating new token for {email}")
    
    with open(token_path, 'w') as token_file:
        token_file.write(creds.to_json())
    print(f"Token saved to {token_path} for account: {email}")

if __name__ == "__main__":
    main() 