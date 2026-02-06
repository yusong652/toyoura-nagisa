"""
Google OAuth Client with PKCE

Implements OAuth 2.0 Authorization Code Flow with PKCE for CLI applications.
Supports both local callback server and manual code entry.

Key Features:
- PKCE code verifier/challenge generation (SHA256)
- Authorization URL construction
- Local HTTP callback server (port 8085)
- Token exchange with Google OAuth2
- User info retrieval
- Project ID discovery via cloudcode-pa API

Reference: OpenClaw extensions/google-gemini-cli-auth/oauth.ts
"""

import asyncio
import hashlib
import secrets
import time
from dataclasses import dataclass
from typing import Optional, Tuple
from urllib.parse import urlencode

import aiohttp

from backend.infrastructure.oauth.base.types import OAuthCredentials


# OAuth Configuration
REDIRECT_URI = "http://localhost:8085/oauth2callback"
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://www.googleapis.com/oauth2/v1/userinfo"
CODE_ASSIST_ENDPOINT = "https://cloudcode-pa.googleapis.com"

# OAuth Scopes for Google Cloud and user info
SCOPES = [
    "https://www.googleapis.com/auth/cloud-platform",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/cclog",
    "https://www.googleapis.com/auth/experimentsandconfigs",
]

# Default project ID if discovery fails
DEFAULT_PROJECT_ID = "rising-fact-p41fc"

# Callback server timeout (5 minutes)
CALLBACK_TIMEOUT_SECONDS = 300


@dataclass
class PKCEPair:
    """PKCE verifier and challenge pair."""

    verifier: str
    challenge: str


@dataclass
class OAuthStartResult:
    """Result of starting OAuth flow."""

    auth_url: str
    state: str
    pkce: PKCEPair


@dataclass
class OAuthCallbackResult:
    """Result of OAuth callback processing."""

    code: str
    state: str


class GoogleOAuthClient:
    """
    Google OAuth client implementing PKCE flow.

    Usage:
        client = GoogleOAuthClient(client_id, client_secret)

        # Start OAuth flow
        start_result = client.start_oauth_flow()
        print(f"Open this URL: {start_result.auth_url}")

        # Wait for callback (runs local server)
        callback_result = await client.wait_for_callback(start_result.state)

        # Exchange code for tokens
        credentials = await client.exchange_code(
            callback_result.code,
            start_result.pkce.verifier
        )
    """

    def __init__(
        self,
        client_id: str,
        client_secret: Optional[str] = None,
    ):
        """
        Initialize Google OAuth client.

        Args:
            client_id: Google OAuth client ID
            client_secret: Google OAuth client secret (optional for PKCE flow)
        """
        self.client_id = client_id
        self.client_secret = client_secret

    @staticmethod
    def generate_pkce() -> PKCEPair:
        """
        Generate PKCE verifier and challenge.

        Returns:
            PKCEPair with verifier and SHA256 challenge
        """
        # Generate random verifier (64 bytes = 128 hex characters)
        verifier = secrets.token_hex(32)

        # Create SHA256 challenge (base64url encoded)
        challenge_bytes = hashlib.sha256(verifier.encode("utf-8")).digest()
        # Base64url encoding without padding
        import base64

        challenge = base64.urlsafe_b64encode(challenge_bytes).decode("utf-8").rstrip("=")

        return PKCEPair(verifier=verifier, challenge=challenge)

    @staticmethod
    def generate_state() -> str:
        """Generate random state parameter for CSRF protection."""
        return secrets.token_hex(16)

    def build_auth_url(self, pkce: PKCEPair, state: str) -> str:
        """
        Build Google OAuth authorization URL.

        Args:
            pkce: PKCE pair with challenge
            state: State parameter for CSRF protection

        Returns:
            Full authorization URL to redirect user to
        """
        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": REDIRECT_URI,
            "scope": " ".join(SCOPES),
            "code_challenge": pkce.challenge,
            "code_challenge_method": "S256",
            "state": state,
            "access_type": "offline",  # Request refresh token
            "prompt": "consent",  # Always show consent screen for refresh token
        }
        return f"{AUTH_URL}?{urlencode(params)}"

    def start_oauth_flow(self) -> OAuthStartResult:
        """
        Start OAuth flow by generating PKCE and auth URL.

        Returns:
            OAuthStartResult with auth_url, state, and pkce
        """
        pkce = self.generate_pkce()
        state = self.generate_state()
        auth_url = self.build_auth_url(pkce, state)

        return OAuthStartResult(
            auth_url=auth_url,
            state=state,
            pkce=pkce,
        )

    async def wait_for_callback(
        self,
        expected_state: str,
        timeout: int = CALLBACK_TIMEOUT_SECONDS,
    ) -> OAuthCallbackResult:
        """
        Start local HTTP server and wait for OAuth callback.

        Args:
            expected_state: State parameter to validate
            timeout: Timeout in seconds

        Returns:
            OAuthCallbackResult with code and state

        Raises:
            asyncio.TimeoutError: If callback not received within timeout
            ValueError: If state doesn't match or callback contains error
        """
        from aiohttp import web

        result_future: asyncio.Future[OAuthCallbackResult] = asyncio.Future()

        async def handle_callback(request: web.Request) -> web.Response:
            """Handle OAuth callback request."""
            # Check for error
            error = request.query.get("error")
            if error:
                error_desc = request.query.get("error_description", error)
                result_future.set_exception(ValueError(f"OAuth error: {error_desc}"))
                return web.Response(
                    text=f"<html><body><h2>Authentication Failed</h2><p>{error_desc}</p></body></html>",
                    content_type="text/html",
                )

            # Get code and state
            code = request.query.get("code")
            state = request.query.get("state") or ""

            if not code:
                result_future.set_exception(ValueError("Missing authorization code"))
                return web.Response(
                    text="<html><body><h2>Error</h2><p>Missing authorization code</p></body></html>",
                    content_type="text/html",
                )

            if not state:
                result_future.set_exception(ValueError("Missing state parameter"))
                return web.Response(
                    text="<html><body><h2>Error</h2><p>Missing state parameter</p></body></html>",
                    content_type="text/html",
                )

            if state != expected_state:
                result_future.set_exception(ValueError("State mismatch - possible CSRF attack"))
                return web.Response(
                    text="<html><body><h2>Error</h2><p>Invalid state parameter</p></body></html>",
                    content_type="text/html",
                )

            # Success
            result_future.set_result(OAuthCallbackResult(code=code, state=state))
            return web.Response(
                text="""
                <html>
                <head><meta charset="utf-8"></head>
                <body>
                    <h2>Authentication Complete</h2>
                    <p>You can close this window and return to the terminal.</p>
                    <script>window.close();</script>
                </body>
                </html>
                """,
                content_type="text/html",
            )

        # Create and start server
        app = web.Application()
        app.router.add_get("/oauth2callback", handle_callback)

        runner = web.AppRunner(app)
        await runner.setup()

        site = web.TCPSite(runner, "localhost", 8085)
        try:
            await site.start()
            print(f"[INFO] OAuth callback server started on {REDIRECT_URI}")

            # Wait for callback or timeout
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
        """
        Exchange authorization code for tokens.

        Args:
            code: Authorization code from callback
            verifier: PKCE verifier

        Returns:
            OAuthCredentials with access and refresh tokens

        Raises:
            ValueError: If token exchange fails
        """
        data = {
            "client_id": self.client_id,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": REDIRECT_URI,
            "code_verifier": verifier,
        }
        if self.client_secret:
            data["client_secret"] = self.client_secret

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
            raise ValueError("No refresh token in response - try revoking app access and re-authenticating")

        # Calculate expiry with 5 minute buffer
        expires_at = int(time.time()) + expires_in - 300

        # Get user email
        email = await self.get_user_email(access_token)

        # Discover project ID
        project_id = await self.discover_project_id(access_token)

        return OAuthCredentials(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at,
            email=email,
            project_id=project_id,
        )

    async def refresh_access_token(self, refresh_token: str) -> Tuple[str, int]:
        """
        Refresh an expired access token.

        Args:
            refresh_token: Refresh token

        Returns:
            Tuple of (new_access_token, expires_at)

        Raises:
            ValueError: If refresh fails
        """
        data = {
            "client_id": self.client_id,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }
        if self.client_secret:
            data["client_secret"] = self.client_secret

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
        """
        Get user's email address from Google.

        Args:
            access_token: Valid access token

        Returns:
            Email address or None if unavailable
        """
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

    async def discover_project_id(self, access_token: str) -> str:
        """
        Discover Google Cloud project ID for Code Assist.

        Uses the cloudcode-pa.googleapis.com API to find or create
        a project for the user.

        Args:
            access_token: Valid access token

        Returns:
            Project ID (discovered or default)
        """
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "User-Agent": "toyoura-nagisa/1.0",
            "X-Goog-Api-Client": "gl-python/toyoura-nagisa",
        }

        load_body = {
            "metadata": {
                "ideType": "IDE_UNSPECIFIED",
                "platform": "PLATFORM_UNSPECIFIED",
                "pluginType": "GEMINI",
            }
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{CODE_ASSIST_ENDPOINT}/v1internal:loadCodeAssist",
                    headers=headers,
                    json=load_body,
                ) as response:
                    if response.ok:
                        data = await response.json()

                        # Extract project ID from response
                        project = data.get("cloudaicompanionProject")
                        if isinstance(project, str) and project:
                            return project
                        if isinstance(project, dict) and project.get("id"):
                            return project["id"]

        except Exception as e:
            print(f"[WARNING] Failed to discover project ID: {e}")

        return DEFAULT_PROJECT_ID


# Default OAuth client credentials
# These are extracted from Gemini CLI / Antigravity
# Users can override via environment variables
_DEFAULT_CLIENT_ID = "1071006060591-tmhssin2h21lcre235vtolojh4g403ep.apps.googleusercontent.com"
_DEFAULT_CLIENT_SECRET = "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"


def get_default_oauth_client() -> GoogleOAuthClient:
    """
    Get a GoogleOAuthClient with default credentials.

    Checks environment variables first:
    - GOOGLE_OAUTH_CLIENT_ID
    - GOOGLE_OAUTH_CLIENT_SECRET

    Falls back to hardcoded defaults (from Gemini CLI).
    """
    import os

    client_id = os.getenv("GOOGLE_OAUTH_CLIENT_ID", _DEFAULT_CLIENT_ID)
    client_secret = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", _DEFAULT_CLIENT_SECRET)

    return GoogleOAuthClient(client_id=client_id, client_secret=client_secret)
