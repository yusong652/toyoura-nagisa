"""
OAuth API.

Provides endpoints for OAuth authentication and account management.
"""

from typing import List, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.application.oauth.oauth_service import OAuthService
from backend.infrastructure.oauth.base.types import OAuthAccountInfo
from backend.presentation.exceptions import BadRequestError, InternalServerError
from backend.presentation.models.api_models import ApiResponse


router = APIRouter(prefix="/api/oauth", tags=["oauth"])
oauth_service = OAuthService()


class OAuthProviderInfo(BaseModel):
    """Provider metadata for UI."""

    id: str = Field(..., description="Provider identifier")
    name: str = Field(..., description="Display name")
    description: str = Field(..., description="Provider description")


class OAuthProviderListData(BaseModel):
    providers: List[OAuthProviderInfo] = Field(..., description="Available OAuth providers")


class OAuthStartData(BaseModel):
    auth_url: str = Field(..., description="Authorization URL")
    state: str = Field(..., description="OAuth state token")
    callback_url: str = Field(..., description="Local callback URL")
    expires_in: int = Field(..., description="State expiration in seconds")


class OAuthCallbackRequest(BaseModel):
    code: str = Field(..., description="Authorization code")
    state: str = Field(..., description="State token")


class OAuthAccountData(BaseModel):
    account_id: str = Field(..., description="Account identifier")
    provider: str = Field(..., description="OAuth provider")
    email: Optional[str] = Field(None, description="Account email")
    is_default: bool = Field(..., description="Whether this is the default account")
    connected_at: int = Field(..., description="Connection time (unix timestamp)")


class OAuthAccountListData(BaseModel):
    accounts: List[OAuthAccountData] = Field(..., description="Connected accounts")


class OAuthDefaultRequest(BaseModel):
    account_id: str = Field(..., description="Account identifier to set as default")


def _to_account_data(account: OAuthAccountInfo) -> OAuthAccountData:
    return OAuthAccountData(
        account_id=account.account_id,
        provider=account.provider.value,
        email=account.email,
        is_default=account.is_default,
        connected_at=account.connected_at,
    )


@router.get("/providers", response_model=ApiResponse[OAuthProviderListData])
async def list_providers() -> ApiResponse[OAuthProviderListData]:
    try:
        providers = [
            OAuthProviderInfo(
                id="google",
                name="Google",
                description="Google OAuth for Gemini and cloudcode-pa quota",
            ),
            OAuthProviderInfo(
                id="openai",
                name="OpenAI",
                description="OpenAI OAuth for Codex API (ChatGPT Pro/Plus)",
            ),
        ]
        return ApiResponse(
            success=True,
            message="Retrieved OAuth providers",
            data=OAuthProviderListData(providers=providers),
        )
    except Exception as e:
        raise InternalServerError(message=f"Failed to list OAuth providers: {str(e)}")


@router.post("/google/start", response_model=ApiResponse[OAuthStartData])
async def start_google_oauth() -> ApiResponse[OAuthStartData]:
    try:
        auth_url, state, callback_url, expires_in = oauth_service.start_google_oauth()
        return ApiResponse(
            success=True,
            message="OAuth flow started",
            data=OAuthStartData(
                auth_url=auth_url,
                state=state,
                callback_url=callback_url,
                expires_in=expires_in,
            ),
        )
    except Exception as e:
        raise InternalServerError(message=f"Failed to start Google OAuth: {str(e)}")


@router.post("/google/callback", response_model=ApiResponse[OAuthAccountData])
async def google_oauth_callback(request: OAuthCallbackRequest) -> ApiResponse[OAuthAccountData]:
    try:
        account = await oauth_service.complete_google_oauth(request.code, request.state)
        return ApiResponse(
            success=True,
            message="OAuth authentication completed",
            data=_to_account_data(account),
        )
    except ValueError as e:
        raise BadRequestError(message=str(e))
    except Exception as e:
        raise InternalServerError(message=f"Failed to complete Google OAuth: {str(e)}")


@router.get("/google/accounts", response_model=ApiResponse[OAuthAccountListData])
async def list_google_accounts() -> ApiResponse[OAuthAccountListData]:
    try:
        accounts = oauth_service.list_google_accounts()
        data = OAuthAccountListData(accounts=[_to_account_data(a) for a in accounts])
        return ApiResponse(
            success=True,
            message="Retrieved Google accounts",
            data=data,
        )
    except Exception as e:
        raise InternalServerError(message=f"Failed to list Google accounts: {str(e)}")


@router.post("/google/default", response_model=ApiResponse[OAuthAccountData])
async def set_google_default(request: OAuthDefaultRequest) -> ApiResponse[OAuthAccountData]:
    try:
        success = oauth_service.set_google_default_account(request.account_id)
        if not success:
            raise BadRequestError(message="Account not found")

        accounts = oauth_service.list_google_accounts()
        updated = next((a for a in accounts if a.account_id == request.account_id), None)
        if not updated:
            raise InternalServerError(message="Default account update failed")

        return ApiResponse(
            success=True,
            message="Default account updated",
            data=_to_account_data(updated),
        )
    except BadRequestError:
        raise
    except Exception as e:
        raise InternalServerError(message=f"Failed to set default account: {str(e)}")


@router.delete("/google/accounts/{account_id}", response_model=ApiResponse[None])
async def delete_google_account(account_id: str) -> ApiResponse[None]:
    try:
        success = oauth_service.delete_google_account(account_id)
        if not success:
            raise BadRequestError(message="Account not found")

        return ApiResponse(
            success=True,
            message="Account disconnected",
            data=None,
        )
    except BadRequestError:
        raise
    except Exception as e:
        raise InternalServerError(message=f"Failed to delete account: {str(e)}")


# ========== OpenAI OAuth Endpoints ==========


@router.post("/openai/start", response_model=ApiResponse[OAuthStartData])
async def start_openai_oauth() -> ApiResponse[OAuthStartData]:
    """Start OpenAI OAuth flow for Codex API access."""
    try:
        auth_url, state, callback_url, expires_in = oauth_service.start_openai_oauth()
        return ApiResponse(
            success=True,
            message="OAuth flow started",
            data=OAuthStartData(
                auth_url=auth_url,
                state=state,
                callback_url=callback_url,
                expires_in=expires_in,
            ),
        )
    except Exception as e:
        raise InternalServerError(message=f"Failed to start OpenAI OAuth: {str(e)}")


@router.post("/openai/callback", response_model=ApiResponse[OAuthAccountData])
async def openai_oauth_callback(request: OAuthCallbackRequest) -> ApiResponse[OAuthAccountData]:
    """Complete OpenAI OAuth flow and exchange code for tokens."""
    try:
        account = await oauth_service.complete_openai_oauth(request.code, request.state)
        return ApiResponse(
            success=True,
            message="OAuth authentication completed",
            data=_to_account_data(account),
        )
    except ValueError as e:
        raise BadRequestError(message=str(e))
    except Exception as e:
        raise InternalServerError(message=f"Failed to complete OpenAI OAuth: {str(e)}")


@router.get("/openai/accounts", response_model=ApiResponse[OAuthAccountListData])
async def list_openai_accounts() -> ApiResponse[OAuthAccountListData]:
    """List connected OpenAI OAuth accounts."""
    try:
        accounts = oauth_service.list_openai_accounts()
        data = OAuthAccountListData(accounts=[_to_account_data(a) for a in accounts])
        return ApiResponse(
            success=True,
            message="Retrieved OpenAI accounts",
            data=data,
        )
    except Exception as e:
        raise InternalServerError(message=f"Failed to list OpenAI accounts: {str(e)}")


@router.post("/openai/default", response_model=ApiResponse[OAuthAccountData])
async def set_openai_default(request: OAuthDefaultRequest) -> ApiResponse[OAuthAccountData]:
    """Set the default OpenAI OAuth account."""
    try:
        success = oauth_service.set_openai_default_account(request.account_id)
        if not success:
            raise BadRequestError(message="Account not found")

        accounts = oauth_service.list_openai_accounts()
        updated = next((a for a in accounts if a.account_id == request.account_id), None)
        if not updated:
            raise InternalServerError(message="Default account update failed")

        return ApiResponse(
            success=True,
            message="Default account updated",
            data=_to_account_data(updated),
        )
    except BadRequestError:
        raise
    except Exception as e:
        raise InternalServerError(message=f"Failed to set default account: {str(e)}")


@router.delete("/openai/accounts/{account_id}", response_model=ApiResponse[None])
async def delete_openai_account(account_id: str) -> ApiResponse[None]:
    """Disconnect an OpenAI OAuth account."""
    try:
        success = oauth_service.delete_openai_account(account_id)
        if not success:
            raise BadRequestError(message="Account not found")

        return ApiResponse(
            success=True,
            message="Account disconnected",
            data=None,
        )
    except BadRequestError:
        raise
    except Exception as e:
        raise InternalServerError(message=f"Failed to delete account: {str(e)}")
