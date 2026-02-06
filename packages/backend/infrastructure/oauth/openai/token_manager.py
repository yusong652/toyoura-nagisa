"""
OpenAI OAuth Token Manager

Manages OpenAI OAuth token lifecycle including:
- Token retrieval with automatic refresh
- Multi-account support
- Credential caching

Reference: Google token manager implementation
"""

import time
from typing import List, Optional, Tuple

from backend.infrastructure.oauth.base.types import OAuthAccountInfo, OAuthCredentials, OAuthProvider
from backend.infrastructure.oauth.openai.oauth_client import (
    OpenAIOAuthClient,
    IdTokenInfo,
    get_default_oauth_client,
)
from backend.infrastructure.storage import oauth_token_storage
from backend.infrastructure.storage.oauth_token_storage import (
    get_token,
    update_token,
    get_default_account,
    has_accounts,
)


class OpenAITokenManager:
    """
    Manages OpenAI OAuth tokens with automatic refresh.

    Features:
    - Automatic token refresh when expired
    - Multi-account support with default account
    - Caches ID token info for plan type checking
    """

    def __init__(self, oauth_client: Optional[OpenAIOAuthClient] = None):
        """
        Initialize token manager.

        Args:
            oauth_client: OAuth client instance (defaults to standard client)
        """
        self.oauth_client = oauth_client or get_default_oauth_client()
        self._id_token_cache: dict[str, IdTokenInfo] = {}

    # ========== Account Management Methods ==========

    def list_accounts(self) -> List[OAuthAccountInfo]:
        """List all connected OpenAI OAuth accounts."""
        return oauth_token_storage.list_accounts(OAuthProvider.OPENAI)

    def get_default_account(self) -> Optional[str]:
        """Get the default account ID."""
        return oauth_token_storage.get_default_account(OAuthProvider.OPENAI)

    def set_default_account(self, account_id: str) -> bool:
        """Set the default account."""
        return oauth_token_storage.set_default_account(OAuthProvider.OPENAI, account_id)

    def delete_account(self, account_id: str) -> bool:
        """Delete an account and its credentials."""
        # Also remove from cache
        self._id_token_cache.pop(account_id, None)
        return oauth_token_storage.delete_token(OAuthProvider.OPENAI, account_id)

    def save_credentials(self, credentials: OAuthCredentials, id_token_info: Optional[IdTokenInfo] = None) -> str:
        """
        Save OAuth credentials for a new or existing account.

        Args:
            credentials: OAuth credentials to save
            id_token_info: Optional ID token info for caching

        Returns:
            Account ID used for storage
        """
        account_id = oauth_token_storage.generate_account_id(credentials.email)

        # Preserve created_at if updating existing account
        existing = oauth_token_storage.get_token(OAuthProvider.OPENAI, account_id)
        if existing:
            credentials.created_at = existing.created_at

        account_id = oauth_token_storage.save_token(
            OAuthProvider.OPENAI,
            credentials,
            account_id=account_id,
        )

        # Set as default if no default exists
        if not oauth_token_storage.get_default_account(OAuthProvider.OPENAI):
            oauth_token_storage.set_default_account(OAuthProvider.OPENAI, account_id)

        # Cache ID token info if provided
        if id_token_info:
            self._id_token_cache[account_id] = id_token_info

        return account_id

    def get_account_info(self, account_id: str) -> Optional[OAuthAccountInfo]:
        """Get account info by ID."""
        for account in self.list_accounts():
            if account.account_id == account_id:
                return account
        return None

    # ========== Credential Access Methods ==========

    async def get_credentials(
        self,
        account_id: Optional[str] = None,
    ) -> Tuple[OAuthCredentials, str]:
        """
        Get valid credentials for an account, refreshing if needed.

        Args:
            account_id: Specific account ID, or None for default account

        Returns:
            Tuple of (credentials, account_id)

        Raises:
            ValueError: If no credentials found or refresh fails
        """
        # Resolve account ID
        if not account_id:
            account_id = get_default_account(OAuthProvider.OPENAI)

        if not account_id:
            raise ValueError("No OpenAI OAuth account found. Please connect an account first.")

        # Get stored credentials
        credentials = get_token(OAuthProvider.OPENAI, account_id)
        if not credentials:
            raise ValueError(f"No credentials found for account: {account_id}")

        # Check if refresh is needed (5 minute buffer)
        if credentials.is_expired(buffer_seconds=300):
            credentials = await self._refresh_credentials(account_id, credentials)

        return credentials, account_id

    async def get_access_token(
        self,
        account_id: Optional[str] = None,
    ) -> Tuple[str, str]:
        """
        Get a valid access token for an account.

        Args:
            account_id: Specific account ID, or None for default account

        Returns:
            Tuple of (access_token, account_id)

        Raises:
            ValueError: If no credentials found or refresh fails
        """
        credentials, resolved_account_id = await self.get_credentials(account_id)
        return credentials.access_token, resolved_account_id

    async def get_chatgpt_account_id(
        self,
        account_id: Optional[str] = None,
    ) -> Tuple[Optional[str], str]:
        """
        Get the ChatGPT account ID (for ChatGPT-Account-Id header).

        Args:
            account_id: OAuth account ID, or None for default

        Returns:
            Tuple of (chatgpt_account_id, oauth_account_id)
            chatgpt_account_id may be None if not available
        """
        credentials, resolved_account_id = await self.get_credentials(account_id)
        # project_id stores the chatgpt_account_id
        return credentials.project_id, resolved_account_id

    def get_cached_id_token_info(self, account_id: str) -> Optional[IdTokenInfo]:
        """
        Get cached ID token info for an account.

        Args:
            account_id: Account ID

        Returns:
            Cached IdTokenInfo or None
        """
        return self._id_token_cache.get(account_id)

    async def _refresh_credentials(
        self,
        account_id: str,
        credentials: OAuthCredentials,
    ) -> OAuthCredentials:
        """
        Refresh expired credentials.

        Args:
            account_id: Account ID
            credentials: Current credentials with refresh token

        Returns:
            Updated credentials

        Raises:
            ValueError: If refresh fails
        """
        print(f"[INFO] Refreshing OpenAI OAuth token for account: {account_id}")

        try:
            new_access_token, new_expires_at, id_token_info = await self.oauth_client.refresh_access_token(
                credentials.refresh_token
            )

            # Update credentials
            credentials.access_token = new_access_token
            credentials.expires_at = new_expires_at
            credentials.updated_at = int(time.time())

            # Update email and account_id if we got new ID token info
            if id_token_info:
                if id_token_info.email:
                    credentials.email = id_token_info.email
                if id_token_info.chatgpt_account_id:
                    credentials.project_id = id_token_info.chatgpt_account_id
                # Cache the ID token info
                self._id_token_cache[account_id] = id_token_info

            # Persist updated credentials
            update_token(OAuthProvider.OPENAI, account_id, credentials)

            return credentials

        except Exception as e:
            print(f"[ERROR] Failed to refresh OpenAI OAuth token: {e}")
            raise ValueError(f"Token refresh failed: {e}")


# Global token manager instance
_token_manager: Optional[OpenAITokenManager] = None


def get_token_manager() -> OpenAITokenManager:
    """
    Get the global OpenAI token manager instance.

    Returns:
        OpenAITokenManager instance
    """
    global _token_manager
    if _token_manager is None:
        _token_manager = OpenAITokenManager()
    return _token_manager


def has_openai_oauth_accounts() -> bool:
    """
    Check if any OpenAI OAuth accounts are configured.

    Returns:
        True if at least one account exists
    """
    return has_accounts(OAuthProvider.OPENAI)
