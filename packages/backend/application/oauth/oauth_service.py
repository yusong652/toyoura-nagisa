"""
OAuth Service

Handles OAuth flow orchestration, account management, and quota retrieval.
"""

import time
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from backend.infrastructure.oauth.base.types import OAuthAccountInfo, OAuthCredentials, OAuthProvider
from backend.infrastructure.oauth.google.oauth_client import GoogleOAuthClient, REDIRECT_URI, get_default_oauth_client
from backend.infrastructure.oauth.google.token_manager import GoogleTokenManager
from backend.infrastructure.oauth.google.quota_client import GoogleQuotaClient, QuotaSummary


@dataclass
class PendingOAuthState:
    verifier: str
    created_at: int


class OAuthService:
    """Business logic for OAuth operations."""

    def __init__(self):
        self._oauth_client: GoogleOAuthClient = get_default_oauth_client()
        self._token_manager = GoogleTokenManager(self._oauth_client)
        self._quota_client = GoogleQuotaClient()
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

    def start_google_oauth(self) -> Tuple[str, str, str, int]:
        self._prune_pending_states()
        start_result = self._oauth_client.start_oauth_flow()
        self._pending_states[start_result.state] = PendingOAuthState(
            verifier=start_result.pkce.verifier,
            created_at=int(time.time()),
        )
        return start_result.auth_url, start_result.state, REDIRECT_URI, self._state_ttl_seconds

    async def complete_google_oauth(self, code: str, state: str) -> OAuthAccountInfo:
        self._prune_pending_states()
        pending = self._pending_states.pop(state, None)
        if not pending:
            raise ValueError("OAuth state not found or expired")

        credentials = await self._oauth_client.exchange_code(code, pending.verifier)
        account_id = self._token_manager.save_credentials(credentials)

        account_info = self._token_manager.get_account_info(account_id)
        if account_info:
            return account_info

        default_account = self._token_manager.get_default_account()
        return OAuthAccountInfo(
            account_id=account_id,
            provider=OAuthProvider.GOOGLE,
            email=credentials.email,
            is_default=default_account == account_id,
            connected_at=credentials.created_at,
        )

    def list_google_accounts(self) -> list[OAuthAccountInfo]:
        return self._token_manager.list_accounts()

    def set_google_default_account(self, account_id: str) -> bool:
        return self._token_manager.set_default_account(account_id)

    def delete_google_account(self, account_id: str) -> bool:
        return self._token_manager.delete_account(account_id)

    async def get_google_quota(self, account_id: Optional[str] = None) -> Tuple[QuotaSummary, str, OAuthCredentials]:
        credentials, resolved_account = await self._token_manager.get_credentials(account_id)
        quota = await self._quota_client.fetch_quota(credentials.access_token)
        return quota, resolved_account, credentials
