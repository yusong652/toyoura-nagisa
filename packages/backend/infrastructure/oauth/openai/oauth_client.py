"""
OpenAI OAuth Client with PKCE

Implements OAuth 2.0 Authorization Code Flow with PKCE for CLI applications.
Supports both browser-based OAuth and device code (headless) authentication.

Key Features:
- PKCE code verifier/challenge generation (SHA256)
- Authorization URL construction with OpenAI-specific parameters
- Local HTTP callback server (port 8086)
- Token exchange with OpenAI OAuth2
- ID token parsing for account info and plan type
- Device code flow for headless environments

Reference: OpenAI Codex CLI and opencode implementations
"""

import asyncio
import base64
import hashlib
import json
import secrets
import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple
from urllib.parse import urlencode

import aiohttp

from backend.infrastructure.oauth.base.types import OAuthCredentials


# OAuth Configuration (must match opencode/Codex CLI registration)
CALLBACK_PORT = 1455
CALLBACK_PATH = "/auth/callback"
REDIRECT_URI = f"http://localhost:{CALLBACK_PORT}{CALLBACK_PATH}"
AUTH_URL = "https://auth.openai.com/oauth/authorize"
TOKEN_URL = "https://auth.openai.com/oauth/token"
DEVICE_CODE_URL = "https://auth.openai.com/api/accounts/deviceauth/usercode"
DEVICE_TOKEN_URL = "https://auth.openai.com/api/accounts/deviceauth/token"

# OpenAI Codex Client ID (from official Codex CLI)
CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"

# OAuth Scopes
SCOPES = "openid profile email offline_access"

# Callback server timeout (5 minutes)
CALLBACK_TIMEOUT_SECONDS = 300

# Device code polling interval
DEVICE_POLL_INTERVAL_SECONDS = 5


class PlanType(str, Enum):
    """OpenAI ChatGPT plan types."""
    FREE = "free"
    GO = "go"
    PLUS = "plus"
    PRO = "pro"
    TEAM = "team"
    BUSINESS = "business"
    ENTERPRISE = "enterprise"
    EDU = "edu"
    UNKNOWN = "unknown"


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


@dataclass
class DeviceCodeResult:
    """Result of device code request."""
    device_code: str
    user_code: str
    verification_uri: str
    expires_in: int
    interval: int


@dataclass
class IdTokenInfo:
    """Parsed information from OpenAI ID token."""
    email: Optional[str] = None
    chatgpt_plan_type: Optional[PlanType] = None
    chatgpt_user_id: Optional[str] = None
    chatgpt_account_id: Optional[str] = None
    raw_jwt: str = ""


class OpenAIOAuthClient:
    """
    OpenAI OAuth client implementing PKCE flow.

    Usage (Browser-based):
        client = OpenAIOAuthClient()

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

    Usage (Device Code / Headless):
        client = OpenAIOAuthClient()

        # Request device code
        device_code = await client.request_device_code()
        print(f"Go to {device_code.verification_uri} and enter: {device_code.user_code}")

        # Poll for token (blocks until user completes auth)
        credentials = await client.poll_device_token(device_code)
    """

    def __init__(self, client_id: str = CLIENT_ID):
        """
        Initialize OpenAI OAuth client.

        Args:
            client_id: OpenAI OAuth client ID (defaults to official Codex CLI ID)
        """
        self.client_id = client_id

    @staticmethod
    def generate_pkce() -> PKCEPair:
        """
        Generate PKCE verifier and challenge.

        Returns:
            PKCEPair with verifier and SHA256 challenge
        """
        # Generate random verifier (32 bytes = 64 hex characters)
        verifier = secrets.token_urlsafe(32)

        # Create SHA256 challenge (base64url encoded without padding)
        challenge_bytes = hashlib.sha256(verifier.encode("utf-8")).digest()
        challenge = base64.urlsafe_b64encode(challenge_bytes).decode("utf-8").rstrip("=")

        return PKCEPair(verifier=verifier, challenge=challenge)

    @staticmethod
    def generate_state() -> str:
        """Generate random state parameter for CSRF protection."""
        return secrets.token_urlsafe(16)

    def build_auth_url(self, pkce: PKCEPair, state: str) -> str:
        """
        Build OpenAI OAuth authorization URL.

        Args:
            pkce: PKCE pair with challenge
            state: State parameter for CSRF protection

        Returns:
            Full authorization URL to redirect user to
        """
        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": REDIRECT_URI,
            "scope": SCOPES,
            "code_challenge": pkce.challenge,
            "code_challenge_method": "S256",
            "state": state,
            # OpenAI-specific parameters
            "id_token_add_organizations": "true",
            "codex_cli_simplified_flow": "true",
            "originator": "toyoura-nagisa",
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
        app.router.add_get(CALLBACK_PATH, handle_callback)

        runner = web.AppRunner(app)
        await runner.setup()

        site = web.TCPSite(runner, "localhost", CALLBACK_PORT)
        try:
            await site.start()
            print(f"[INFO] OpenAI OAuth callback server started on {REDIRECT_URI}")

            # Wait for callback or timeout
            try:
                result = await asyncio.wait_for(result_future, timeout=timeout)
                return result
            except asyncio.TimeoutError:
                raise asyncio.TimeoutError("OAuth callback timeout - no response received")
        finally:
            await runner.cleanup()

    @staticmethod
    def _parse_id_token(id_token: str) -> IdTokenInfo:
        """
        Parse OpenAI ID token (JWT) to extract user info.

        Args:
            id_token: JWT ID token from OAuth response

        Returns:
            IdTokenInfo with parsed claims
        """
        try:
            # JWT format: header.payload.signature
            parts = id_token.split(".")
            if len(parts) != 3:
                return IdTokenInfo(raw_jwt=id_token)

            # Decode payload (base64url)
            payload = parts[1]
            # Add padding if needed
            padding = 4 - len(payload) % 4
            if padding != 4:
                payload += "=" * padding

            claims = json.loads(base64.urlsafe_b64decode(payload))

            # Extract standard claims
            email = claims.get("email")

            # Extract OpenAI-specific claims
            # These can be at root level or nested under https://api.openai.com/auth
            openai_auth = claims.get("https://api.openai.com/auth", {})

            chatgpt_plan_type_str = (
                claims.get("chatgpt_plan_type")
                or openai_auth.get("chatgpt_plan_type")
            )
            chatgpt_user_id = (
                claims.get("chatgpt_user_id")
                or openai_auth.get("chatgpt_user_id")
            )
            chatgpt_account_id = (
                claims.get("chatgpt_account_id")
                or openai_auth.get("chatgpt_account_id")
            )

            # Also check organizations array for account_id
            if not chatgpt_account_id:
                organizations = claims.get("organizations", [])
                if organizations and len(organizations) > 0:
                    chatgpt_account_id = organizations[0].get("id")

            # Parse plan type
            plan_type = PlanType.UNKNOWN
            if chatgpt_plan_type_str:
                try:
                    plan_type = PlanType(chatgpt_plan_type_str.lower())
                except ValueError:
                    plan_type = PlanType.UNKNOWN

            return IdTokenInfo(
                email=email,
                chatgpt_plan_type=plan_type,
                chatgpt_user_id=chatgpt_user_id,
                chatgpt_account_id=chatgpt_account_id,
                raw_jwt=id_token,
            )
        except Exception as e:
            print(f"[WARNING] Failed to parse ID token: {e}")
            return IdTokenInfo(raw_jwt=id_token)

    async def exchange_code(
        self,
        code: str,
        verifier: str,
    ) -> Tuple[OAuthCredentials, IdTokenInfo]:
        """
        Exchange authorization code for tokens.

        Args:
            code: Authorization code from callback
            verifier: PKCE verifier

        Returns:
            Tuple of (OAuthCredentials, IdTokenInfo)

        Raises:
            ValueError: If token exchange fails
        """
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "client_id": self.client_id,
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
        id_token = token_data.get("id_token", "")
        expires_in = token_data.get("expires_in", 3600)

        if not access_token:
            raise ValueError("No access token in response")
        if not refresh_token:
            raise ValueError("No refresh token in response")

        # Parse ID token for user info
        id_token_info = self._parse_id_token(id_token) if id_token else IdTokenInfo()

        # Calculate expiry with 5 minute buffer
        expires_at = int(time.time()) + expires_in - 300

        credentials = OAuthCredentials(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at,
            email=id_token_info.email,
            project_id=id_token_info.chatgpt_account_id,  # Use account_id as project_id
        )

        return credentials, id_token_info

    async def refresh_access_token(self, refresh_token: str) -> Tuple[str, int, Optional[IdTokenInfo]]:
        """
        Refresh an expired access token.

        Args:
            refresh_token: Refresh token

        Returns:
            Tuple of (new_access_token, expires_at, id_token_info)

        Raises:
            ValueError: If refresh fails
        """
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": self.client_id,
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                TOKEN_URL,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            ) as response:
                if not response.ok:
                    error_text = await response.text()
                    # Check for specific error codes
                    try:
                        error_json = json.loads(error_text)
                        error_code = error_json.get("error", {}).get("code") or error_json.get("code")
                        if error_code in ["refresh_token_expired", "refresh_token_reused", "refresh_token_invalidated"]:
                            raise ValueError(f"Refresh token invalid: {error_code}. Please re-authenticate.")
                    except json.JSONDecodeError:
                        pass
                    raise ValueError(f"Token refresh failed: {error_text}")

                token_data = await response.json()

        access_token = token_data.get("access_token")
        id_token = token_data.get("id_token")
        expires_in = token_data.get("expires_in", 3600)

        if not access_token:
            raise ValueError("No access token in refresh response")

        expires_at = int(time.time()) + expires_in - 300

        # Parse new ID token if provided
        id_token_info = self._parse_id_token(id_token) if id_token else None

        return access_token, expires_at, id_token_info

    # Device Code Flow (Headless)

    async def request_device_code(self) -> DeviceCodeResult:
        """
        Request a device code for headless authentication.

        Returns:
            DeviceCodeResult with device_code, user_code, and verification_uri

        Raises:
            ValueError: If device code request fails
        """
        data = {
            "client_id": self.client_id,
            "scope": SCOPES,
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                DEVICE_CODE_URL,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            ) as response:
                if not response.ok:
                    error_text = await response.text()
                    raise ValueError(f"Device code request failed: {error_text}")

                result = await response.json()

        return DeviceCodeResult(
            device_code=result["device_code"],
            user_code=result["user_code"],
            verification_uri=result.get("verification_uri", "https://auth.openai.com/codex/device"),
            expires_in=result.get("expires_in", 900),
            interval=result.get("interval", DEVICE_POLL_INTERVAL_SECONDS),
        )

    async def poll_device_token(
        self,
        device_code: DeviceCodeResult,
        timeout: int = 300,
    ) -> Tuple[OAuthCredentials, IdTokenInfo]:
        """
        Poll for device token until user completes authentication.

        Args:
            device_code: Device code result from request_device_code
            timeout: Maximum time to wait in seconds

        Returns:
            Tuple of (OAuthCredentials, IdTokenInfo)

        Raises:
            asyncio.TimeoutError: If user doesn't complete auth within timeout
            ValueError: If polling fails
        """
        start_time = time.time()
        interval = max(device_code.interval, DEVICE_POLL_INTERVAL_SECONDS)

        while time.time() - start_time < timeout:
            await asyncio.sleep(interval)

            data = {
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                "device_code": device_code.device_code,
                "client_id": self.client_id,
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    DEVICE_TOKEN_URL,
                    data=data,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                ) as response:
                    result = await response.json()

                    if response.ok:
                        # Success - got tokens
                        access_token = result.get("access_token")
                        refresh_token = result.get("refresh_token")
                        id_token = result.get("id_token", "")
                        expires_in = result.get("expires_in", 3600)

                        if not access_token or not refresh_token:
                            raise ValueError("Missing tokens in response")

                        id_token_info = self._parse_id_token(id_token) if id_token else IdTokenInfo()
                        expires_at = int(time.time()) + expires_in - 300

                        credentials = OAuthCredentials(
                            access_token=access_token,
                            refresh_token=refresh_token,
                            expires_at=expires_at,
                            email=id_token_info.email,
                            project_id=id_token_info.chatgpt_account_id,
                        )

                        return credentials, id_token_info

                    # Check error type
                    error = result.get("error")
                    if error == "authorization_pending":
                        # User hasn't completed auth yet, keep polling
                        continue
                    elif error == "slow_down":
                        # Increase interval
                        interval += 5
                        continue
                    elif error == "expired_token":
                        raise ValueError("Device code expired. Please restart authentication.")
                    elif error == "access_denied":
                        raise ValueError("User denied authorization.")
                    else:
                        raise ValueError(f"Device token error: {error}")

        raise asyncio.TimeoutError("Device authentication timeout")


def get_default_oauth_client() -> OpenAIOAuthClient:
    """
    Get an OpenAIOAuthClient with default configuration.

    Returns:
        Configured OpenAIOAuthClient
    """
    return OpenAIOAuthClient()
