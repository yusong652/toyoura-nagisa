"""
Quota API.

Provides endpoints for querying provider usage/quota.
"""

from typing import List, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.application.oauth.oauth_service import OAuthService
from backend.presentation.exceptions import BadRequestError, InternalServerError
from backend.presentation.models.api_models import ApiResponse


router = APIRouter(prefix="/api/quota", tags=["quota"])
oauth_service = OAuthService()


class QuotaWindowData(BaseModel):
    label: str = Field(..., description="Quota bucket label")
    used_percent: float = Field(..., description="Used percent")
    remaining_percent: float = Field(..., description="Remaining percent")
    remaining_fraction: float = Field(..., description="Remaining fraction (0-1)")


class GoogleQuotaData(BaseModel):
    provider: str = Field(..., description="Provider identifier")
    account_id: str = Field(..., description="Account identifier")
    email: Optional[str] = Field(None, description="Account email")
    project_id: Optional[str] = Field(None, description="Project ID")
    windows: List[QuotaWindowData] = Field(..., description="Quota windows")


@router.get("/google", response_model=ApiResponse[GoogleQuotaData])
async def get_google_quota() -> ApiResponse[GoogleQuotaData]:
    try:
        quota, account_id, credentials = await oauth_service.get_google_quota()
        return ApiResponse(
            success=True,
            message="Retrieved Google quota",
            data=GoogleQuotaData(
                provider="google",
                account_id=account_id,
                email=credentials.email,
                project_id=credentials.project_id,
                windows=[
                    QuotaWindowData(
                        label=window.label,
                        used_percent=window.used_percent,
                        remaining_percent=window.remaining_percent,
                        remaining_fraction=window.remaining_fraction,
                    )
                    for window in quota.windows
                ],
            ),
        )
    except ValueError as e:
        raise BadRequestError(message=str(e))
    except Exception as e:
        raise InternalServerError(message=f"Failed to retrieve Google quota: {str(e)}")
