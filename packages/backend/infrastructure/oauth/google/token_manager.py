"""
Google OAuth Token Manager

Manages token storage, refresh, and account operations for Google OAuth.
"""

from typing import List, Optional, Tuple

from backend.infrastructure.oauth.base.types import OAuthAccountInfo, OAuthCredentials, OAuthProvider
from backend.infrastructure.oauth.google.oauth_client import GoogleOAuthClient, get_default_oauth_client
from backend.infrastructure.storage import oauth_token_storage


class GoogleTokenManager:
    """Token manager for Google OAuth accounts."""

    def __init__(self, oauth_client: Optional[GoogleOAuthClient] = None):
        self._oauth_client = oauth_client or get_default_oauth_client()

    def list_accounts(self) -> List[OAuthAccountInfo]:
        return oauth_token_storage.list_accounts(OAuthProvider.GOOGLE)

    def get_default_account(self) -> Optional[str]:
        return oauth_token_storage.get_default_account(OAuthProvider.GOOGLE)

    def set_default_account(self, account_id: str) -> bool:
        return oauth_token_storage.set_default_account(OAuthProvider.GOOGLE, account_id)

    def delete_account(self, account_id: str) -> bool:
        return oauth_token_storage.delete_token(OAuthProvider.GOOGLE, account_id)

    def save_credentials(self, credentials: OAuthCredentials) -> str:
        account_id = oauth_token_storage.generate_account_id(credentials.email)
        existing = oauth_token_storage.get_token(OAuthProvider.GOOGLE, account_id)
        if existing:
            credentials.created_at = existing.created_at

        account_id = oauth_token_storage.save_token(
            OAuthProvider.GOOGLE,
            credentials,
            account_id=account_id,
        )

        if not oauth_token_storage.get_default_account(OAuthProvider.GOOGLE):
            oauth_token_storage.set_default_account(OAuthProvider.GOOGLE, account_id)

        return account_id

    def get_account_info(self, account_id: str) -> Optional[OAuthAccountInfo]:
        for account in self.list_accounts():
            if account.account_id == account_id:
                return account
        return None

    async def get_credentials(self, account_id: Optional[str] = None) -> Tuple[OAuthCredentials, str]:
        resolved_account = account_id or oauth_token_storage.get_default_account(OAuthProvider.GOOGLE)
        if not resolved_account:
            raise ValueError("No Google OAuth account connected")

        credentials = oauth_token_storage.get_token(OAuthProvider.GOOGLE, resolved_account)
        if not credentials:
            raise ValueError(f"OAuth token not found for account: {resolved_account}")

        if credentials.is_expired():
            access_token, expires_at = await self._oauth_client.refresh_access_token(credentials.refresh_token)
            credentials.access_token = access_token
            credentials.expires_at = expires_at
            oauth_token_storage.update_token(OAuthProvider.GOOGLE, resolved_account, credentials)

        return credentials, resolved_account

    async def get_access_token(self, account_id: Optional[str] = None) -> Tuple[str, str]:
        credentials, resolved_account = await self.get_credentials(account_id)
        return credentials.access_token, resolved_account
