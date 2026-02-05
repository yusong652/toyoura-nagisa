"""
OAuth Service

Handles OAuth flow orchestration, account management, and quota retrieval.
Supports multiple OAuth providers: Google and OpenAI.
"""

import time
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from backend.infrastructure.oauth.base.types import OAuthAccountInfo, OAuthCredentials, OAuthProvider
from backend.infrastructure.oauth.google.oauth_client import (
    GoogleOAuthClient,
    REDIRECT_URI as GOOGLE_REDIRECT_URI,
    get_default_oauth_client as get_default_google_oauth_client,
)
from backend.infrastructure.oauth.google.token_manager import GoogleTokenManager
from backend.infrastructure.oauth.google.quota_client import GoogleQuotaClient, QuotaSummary
from backend.infrastructure.oauth.openai.oauth_client import (
    OpenAIOAuthClient,
    REDIRECT_URI as OPENAI_REDIRECT_URI,
    get_default_oauth_client as get_default_openai_oauth_client,
    IdTokenInfo,
)
from backend.infrastructure.oauth.openai.token_manager import OpenAITokenManager


@dataclass
class PendingOAuthState:
    """Pending OAuth state for PKCE flow."""
    verifier: str
    created_at: int
    provider: str  # "google" or "openai"


class OAuthService:
    """Business logic for OAuth operations."""

    def __init__(self):
        # Google OAuth
        self._google_oauth_client: GoogleOAuthClient = get_default_google_oauth_client()
        self._google_token_manager = GoogleTokenManager(self._google_oauth_client)
        self._quota_client = GoogleQuotaClient()

        # OpenAI OAuth
        self._openai_oauth_client: OpenAIOAuthClient = get_default_openai_oauth_client()
        self._openai_token_manager = OpenAITokenManager(self._openai_oauth_client)

        # Shared pending states for all providers
        self._pending_states: Dict[str, PendingOAuthState] = {}
        self._state_ttl_seconds = 600

    def _prune_pending_states(self) -> None:
        now = int(time.time())
        expired = [
            state
            for state, pending in self._pending_states.items()
            if now - pending.created_at > self._state_ttl_seconds
        ]
        for state in expired:
            self._pending_states.pop(state, None)

    # ========== Google OAuth Methods ==========

    def start_google_oauth(self) -> Tuple[str, str, str, int]:
        self._prune_pending_states()
        start_result = self._google_oauth_client.start_oauth_flow()
        self._pending_states[start_result.state] = PendingOAuthState(
            verifier=start_result.pkce.verifier,
            created_at=int(time.time()),
            provider="google",
        )
        return start_result.auth_url, start_result.state, GOOGLE_REDIRECT_URI, self._state_ttl_seconds

    async def complete_google_oauth(self, code: str, state: str) -> OAuthAccountInfo:
        self._prune_pending_states()
        pending = self._pending_states.pop(state, None)
        if not pending:
            raise ValueError("OAuth state not found or expired")
        if pending.provider != "google":
            raise ValueError("OAuth state provider mismatch")

        credentials = await self._google_oauth_client.exchange_code(code, pending.verifier)
        account_id = self._google_token_manager.save_credentials(credentials)

        account_info = self._google_token_manager.get_account_info(account_id)
        if account_info:
            return account_info

        default_account = self._google_token_manager.get_default_account()
        return OAuthAccountInfo(
            account_id=account_id,
            provider=OAuthProvider.GOOGLE,
            email=credentials.email,
            is_default=default_account == account_id,
            connected_at=credentials.created_at,
        )

    def list_google_accounts(self) -> list[OAuthAccountInfo]:
        return self._google_token_manager.list_accounts()

    def set_google_default_account(self, account_id: str) -> bool:
        return self._google_token_manager.set_default_account(account_id)

    def delete_google_account(self, account_id: str) -> bool:
        return self._google_token_manager.delete_account(account_id)

    async def get_google_quota(self, account_id: Optional[str] = None) -> Tuple[QuotaSummary, str, OAuthCredentials]:
        credentials, resolved_account = await self._google_token_manager.get_credentials(account_id)
        quota = await self._quota_client.fetch_quota(credentials.access_token)
        return quota, resolved_account, credentials

    # ========== OpenAI OAuth Methods ==========

    def start_openai_oauth(self) -> Tuple[str, str, str, int]:
        """
        Start OpenAI OAuth flow.

        Returns:
            Tuple of (auth_url, state, callback_url, expires_in)
        """
        self._prune_pending_states()
        start_result = self._openai_oauth_client.start_oauth_flow()
        self._pending_states[start_result.state] = PendingOAuthState(
            verifier=start_result.pkce.verifier,
            created_at=int(time.time()),
            provider="openai",
        )
        return start_result.auth_url, start_result.state, OPENAI_REDIRECT_URI, self._state_ttl_seconds

    async def complete_openai_oauth(self, code: str, state: str) -> OAuthAccountInfo:
        """
        Complete OpenAI OAuth flow.

        Args:
            code: Authorization code from callback
            state: OAuth state token

        Returns:
            OAuthAccountInfo for the connected account
        """
        self._prune_pending_states()
        pending = self._pending_states.pop(state, None)
        if not pending:
            raise ValueError("OAuth state not found or expired")
        if pending.provider != "openai":
            raise ValueError("OAuth state provider mismatch")

        credentials, id_token_info = await self._openai_oauth_client.exchange_code(code, pending.verifier)
        account_id = self._openai_token_manager.save_credentials(credentials, id_token_info)

        account_info = self._openai_token_manager.get_account_info(account_id)
        if account_info:
            return account_info

        default_account = self._openai_token_manager.get_default_account()
        return OAuthAccountInfo(
            account_id=account_id,
            provider=OAuthProvider.OPENAI,
            email=credentials.email,
            is_default=default_account == account_id,
            connected_at=credentials.created_at,
        )

    def list_openai_accounts(self) -> list[OAuthAccountInfo]:
        """List all connected OpenAI OAuth accounts."""
        return self._openai_token_manager.list_accounts()

    def set_openai_default_account(self, account_id: str) -> bool:
        """Set the default OpenAI OAuth account."""
        return self._openai_token_manager.set_default_account(account_id)

    def delete_openai_account(self, account_id: str) -> bool:
        """Delete an OpenAI OAuth account."""
        return self._openai_token_manager.delete_account(account_id)

    def get_openai_plan_info(self, account_id: Optional[str] = None) -> Optional[IdTokenInfo]:
        """
        Get OpenAI plan info for an account (from cached ID token).

        Args:
            account_id: Account ID (uses default if not specified)

        Returns:
            IdTokenInfo with plan details, or None if not cached
        """
        resolved_account = account_id or self._openai_token_manager.get_default_account()
        if not resolved_account:
            return None
        return self._openai_token_manager.get_cached_id_token_info(resolved_account)
