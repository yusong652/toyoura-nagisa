"""
Antigravity OAuth Client.

Uses Antigravity-specific credentials and endpoint fallback logic.
"""

from __future__ import annotations

import asyncio
import hashlib
import secrets
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlencode

import aiohttp

from backend.infrastructure.oauth.base.types import OAuthCredentials
from backend.infrastructure.llm.providers.google_gemini_antigravity.constants import (
    ANTIGRAVITY_CLIENT_ID,
    ANTIGRAVITY_CLIENT_SECRET,
    ANTIGRAVITY_REDIRECT_URI,
    ANTIGRAVITY_SCOPES,
    ANTIGRAVITY_CALLBACK_PORT,
    CODE_ASSIST_ENDPOINT_FALLBACKS,
    CODE_ASSIST_HEADERS,
    CODE_ASSIST_API_VERSION,
    DEFAULT_METADATA,
)


AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://www.googleapis.com/oauth2/v1/userinfo"

CALLBACK_TIMEOUT_SECONDS = 300


@dataclass
class PKCEPair:
    """PKCE verifier and challenge pair."""

    verifier: str
    challenge: str


@dataclass
class AntigravityOAuthStartResult:
    """Result of starting Antigravity OAuth flow."""

    auth_url: str
    state: str
    pkce: PKCEPair


@dataclass
class AntigravityOAuthCallbackResult:
    """Result of Antigravity OAuth callback processing."""

    code: str
    state: str


@dataclass
class AntigravityAccountInfo:
    """Account info discovered from Antigravity API."""

    project_id: str
    tier: str  # "free" or "paid"
    tier_id: Optional[str] = None
    tier_name: Optional[str] = None


class AntigravityOAuthClient:
    """
    Antigravity OAuth client implementing PKCE flow.

    Uses Antigravity-specific credentials and endpoint fallback logic.
    """

    def __init__(
        self,
        client_id: str = ANTIGRAVITY_CLIENT_ID,
        client_secret: str = ANTIGRAVITY_CLIENT_SECRET,
        redirect_uri: str = ANTIGRAVITY_REDIRECT_URI,
        scopes: Optional[List[str]] = None,
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.scopes = scopes or list(ANTIGRAVITY_SCOPES)

    @staticmethod
    def generate_pkce() -> PKCEPair:
        """Generate PKCE verifier and challenge."""
        verifier = secrets.token_hex(32)
        challenge_bytes = hashlib.sha256(verifier.encode("utf-8")).digest()
        import base64

        challenge = base64.urlsafe_b64encode(challenge_bytes).decode("utf-8").rstrip("=")
        return PKCEPair(verifier=verifier, challenge=challenge)

    @staticmethod
    def generate_state() -> str:
        """Generate random state parameter for CSRF protection."""
        return secrets.token_hex(16)

    def build_auth_url(self, pkce: PKCEPair, state: str) -> str:
        """Build Google OAuth authorization URL."""
        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": self.redirect_uri,
            "scope": " ".join(self.scopes),
            "code_challenge": pkce.challenge,
            "code_challenge_method": "S256",
            "state": state,
            "access_type": "offline",
            "prompt": "consent",
        }
        return f"{AUTH_URL}?{urlencode(params)}"

    def start_oauth_flow(self) -> AntigravityOAuthStartResult:
        """Start OAuth flow by generating PKCE and auth URL."""
        pkce = self.generate_pkce()
        state = self.generate_state()
        auth_url = self.build_auth_url(pkce, state)

        return AntigravityOAuthStartResult(
            auth_url=auth_url,
            state=state,
            pkce=pkce,
        )

    async def wait_for_callback(
        self,
        expected_state: str,
        timeout: int = CALLBACK_TIMEOUT_SECONDS,
    ) -> AntigravityOAuthCallbackResult:
        """Start local HTTP server and wait for OAuth callback."""
        from aiohttp import web

        result_future: asyncio.Future[AntigravityOAuthCallbackResult] = asyncio.Future()

        async def handle_callback(request: web.Request) -> web.Response:
            error = request.query.get("error")
            if error:
                error_desc = request.query.get("error_description", error)
                result_future.set_exception(ValueError(f"OAuth error: {error_desc}"))
                return web.Response(
                    text=f"<html><body><h2>Authentication Failed</h2><p>{error_desc}</p></body></html>",
                    content_type="text/html",
                )

            code = request.query.get("code")
            state = request.query.get("state")

            if not code:
                result_future.set_exception(ValueError("Missing authorization code"))
                return web.Response(
                    text="<html><body><h2>Error</h2><p>Missing authorization code</p></body></html>",
                    content_type="text/html",
                )

            if state != expected_state:
                result_future.set_exception(ValueError("State mismatch - possible CSRF attack"))
                return web.Response(
                    text="<html><body><h2>Error</h2><p>Invalid state parameter</p></body></html>",
                    content_type="text/html",
                )

            result_future.set_result(AntigravityOAuthCallbackResult(code=code, state=state))
            return web.Response(
                text="""
                <html>
                <head><meta charset="utf-8"></head>
                <body>
                    <h2>Antigravity Authentication Complete</h2>
                    <p>You can close this window and return to the terminal.</p>
                    <script>window.close();</script>
                </body>
                </html>
                """,
                content_type="text/html",
            )

        app = web.Application()
        app.router.add_get("/oauth-callback", handle_callback)

        runner = web.AppRunner(app)
        await runner.setup()

        site = web.TCPSite(runner, "localhost", ANTIGRAVITY_CALLBACK_PORT)
        try:
            await site.start()
            print(f"[INFO] Antigravity OAuth callback server started on {self.redirect_uri}")

            try:
                result = await asyncio.wait_for(result_future, timeout=timeout)
                return result
            except asyncio.TimeoutError:
                raise asyncio.TimeoutError("OAuth callback timeout - no response received")
        finally:
            await runner.cleanup()

    async def exchange_code(
        self,
        code: str,
        verifier: str,
    ) -> OAuthCredentials:
        """Exchange authorization code for tokens."""
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": self.redirect_uri,
            "code_verifier": verifier,
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                TOKEN_URL,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            ) as response:
                if not response.ok:
                    error_text = await response.text()
                    raise ValueError(f"Token exchange failed: {error_text}")

                token_data = await response.json()

        access_token = token_data.get("access_token")
        refresh_token = token_data.get("refresh_token")
        expires_in = token_data.get("expires_in", 3600)

        if not access_token:
            raise ValueError("No access token in response")
        if not refresh_token:
            raise ValueError("No refresh token in response")

        expires_at = int(time.time()) + expires_in - 300

        # Get user info
        email = await self.get_user_email(access_token)

        # Discover project ID and tier using endpoint fallback
        account_info = await self.fetch_account_info(access_token)

        return OAuthCredentials(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at,
            email=email,
            project_id=account_info.project_id,
        )

    async def refresh_access_token(self, refresh_token: str) -> Tuple[str, int]:
        """Refresh an expired access token."""
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                TOKEN_URL,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            ) as response:
                if not response.ok:
                    error_text = await response.text()
                    raise ValueError(f"Token refresh failed: {error_text}")

                token_data = await response.json()

        access_token = token_data.get("access_token")
        expires_in = token_data.get("expires_in", 3600)

        if not access_token:
            raise ValueError("No access token in refresh response")

        expires_at = int(time.time()) + expires_in - 300
        return access_token, expires_at

    async def get_user_email(self, access_token: str) -> Optional[str]:
        """Get user's email address from Google."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{USERINFO_URL}?alt=json",
                    headers={"Authorization": f"Bearer {access_token}"},
                ) as response:
                    if response.ok:
                        data = await response.json()
                        return data.get("email")
        except Exception as e:
            print(f"[WARNING] Failed to get user email: {e}")
        return None

    async def fetch_account_info(self, access_token: str) -> AntigravityAccountInfo:
        """
        Discover project ID and account tier from Antigravity API.

        Tries multiple endpoints in fallback order.
        """
        errors: List[str] = []
        detected_tier = "free"
        detected_tier_id: Optional[str] = None
        detected_tier_name: Optional[str] = None

        headers: Dict[str, str] = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            **CODE_ASSIST_HEADERS,
        }

        for base_endpoint in CODE_ASSIST_ENDPOINT_FALLBACKS:
            try:
                url = f"{base_endpoint}/{CODE_ASSIST_API_VERSION}:loadCodeAssist"
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        url,
                        headers=headers,
                        json={"metadata": DEFAULT_METADATA},
                    ) as response:
                        if not response.ok:
                            message = await response.text()
                            errors.append(f"loadCodeAssist {response.status} at {base_endpoint}: {message[:200]}")
                            continue

                        data = await response.json()
                        project_id = ""

                        # Extract Project ID
                        cai_project = data.get("cloudaicompanionProject")
                        if isinstance(cai_project, str) and cai_project:
                            project_id = cai_project
                        elif isinstance(cai_project, dict) and cai_project.get("id"):
                            project_id = cai_project["id"]

                        # Extract tier info from currentTier
                        current_tier = data.get("currentTier")
                        if isinstance(current_tier, dict):
                            detected_tier_id = current_tier.get("id")
                            detected_tier_name = current_tier.get("name")
                            if detected_tier_id and detected_tier_id not in ("free-tier", "legacy-tier"):
                                if "free" not in detected_tier_id.lower():
                                    detected_tier = "paid"

                        # Also check allowedTiers
                        allowed_tiers = data.get("allowedTiers")
                        if isinstance(allowed_tiers, list):
                            for tier in allowed_tiers:
                                if isinstance(tier, dict) and tier.get("isDefault"):
                                    tier_id = tier.get("id", "")
                                    if tier_id not in ("free-tier", "legacy-tier"):
                                        if "free" not in tier_id.lower():
                                            detected_tier = "paid"
                                    break

                        # Check paidTier
                        paid_tier = data.get("paidTier")
                        if isinstance(paid_tier, dict) and paid_tier.get("id"):
                            paid_id = paid_tier.get("id", "")
                            if "free" not in paid_id.lower():
                                detected_tier = "paid"

                        if project_id:
                            return AntigravityAccountInfo(
                                project_id=project_id,
                                tier=detected_tier,
                                tier_id=detected_tier_id,
                                tier_name=detected_tier_name,
                            )

                        errors.append(f"loadCodeAssist missing project id at {base_endpoint}")

            except Exception as e:
                errors.append(f"loadCodeAssist error at {base_endpoint}: {e}")

        if errors:
            print(f"[WARNING] Failed to resolve Antigravity account info: {'; '.join(errors)}")

        return AntigravityAccountInfo(project_id="", tier=detected_tier)


def get_antigravity_oauth_client() -> AntigravityOAuthClient:
    """Get an AntigravityOAuthClient with default credentials."""
    import os

    client_id = os.getenv("ANTIGRAVITY_CLIENT_ID", ANTIGRAVITY_CLIENT_ID)
    client_secret = os.getenv("ANTIGRAVITY_CLIENT_SECRET", ANTIGRAVITY_CLIENT_SECRET)

    return AntigravityOAuthClient(client_id=client_id, client_secret=client_secret)
