"""
LLM Configuration API.

Provides endpoints for managing global default LLM provider and model configuration.
The configuration is stored in config/default_llm.json and applies to all new sessions.

Routes:
    GET /api/llm-config - Get current default LLM configuration
    POST /api/llm-config - Update default LLM configuration
    DELETE /api/llm-config - Clear default LLM configuration (revert to system defaults)
    GET /api/llm-config/providers - Get available providers and models
"""
from typing import List, Optional
from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.presentation.models.api_models import ApiResponse
from backend.presentation.exceptions import BadRequestError, InternalServerError
from backend.infrastructure.storage.llm_config_manager import (
    get_default_llm_config,
    save_default_llm_config,
    clear_default_llm_config,
    validate_llm_config,
)
from backend.infrastructure.llm.shared.models_registry import (
    get_all_providers,
    ModelInfo as RegistryModelInfo,
    ProviderInfo as RegistryProviderInfo,
)

router = APIRouter(prefix="/api/llm-config", tags=["llm-config"])


# =====================
# Request/Response Models
# =====================
class LLMConfigData(BaseModel):
    """LLM configuration data."""
    provider: str = Field(..., description="LLM provider name (e.g., 'google', 'anthropic')")
    model: str = Field(..., description="Model identifier (e.g., 'gemini-2.0-flash-exp')")


class LLMConfigUpdateRequest(BaseModel):
    """Request to update LLM configuration."""
    provider: str = Field(..., description="LLM provider name")
    model: str = Field(..., description="Model identifier")


class ModelInfo(BaseModel):
    """Model information for API response."""
    id: str = Field(..., description="Model identifier")
    name: str = Field(..., description="Display name")
    description: Optional[str] = Field(None, description="Model description")
    context_window: Optional[int] = Field(None, description="Context window size (tokens)")


class ProviderInfo(BaseModel):
    """Provider information with available models."""
    provider: str = Field(..., description="Provider identifier")
    name: str = Field(..., description="Display name")
    description: str = Field(..., description="Provider description")
    models: List[ModelInfo] = Field(..., description="Available models")
    api_key_configured: bool = Field(..., description="Whether API key is configured")


class ProviderListData(BaseModel):
    """Response data for provider list."""
    providers: List[ProviderInfo] = Field(..., description="Available providers")


# =====================
# Helper Functions
# =====================
def _check_api_key_configured(provider: str) -> bool:
    """
    Check if API key is configured for a provider.

    Args:
        provider: Provider identifier

    Returns:
        bool: True if API key/server URL is configured
    """
    from backend.config import get_llm_settings

    try:
        llm_settings = get_llm_settings()

        if provider == "google":
            cfg = llm_settings.get_google_config()
            return bool(cfg.google_api_key)

        elif provider == "anthropic":
            cfg = llm_settings.get_anthropic_config()
            return bool(cfg.anthropic_api_key)

        elif provider in ["openai", "gpt"]:
            cfg = llm_settings.get_openai_config()
            return bool(cfg.openai_api_key)

        elif provider == "moonshot":
            cfg = llm_settings.get_moonshot_config()
            return bool(cfg.moonshot_api_key)

        elif provider == "zhipu":
            cfg = llm_settings.get_zhipu_config()
            return bool(cfg.zhipu_api_key)

        elif provider == "openrouter":
            cfg = llm_settings.get_openrouter_config()
            return bool(cfg.openrouter_api_key)

        elif provider == "local_llm":
            cfg = llm_settings.get_local_llm_config()
            return bool(cfg.server_url)

        return False

    except Exception:
        return False


def _get_available_providers() -> List[ProviderInfo]:
    """
    Get list of available providers with their models.

    Loads providers from models_registry and enriches with API key status.

    Returns:
        List[ProviderInfo]: Available providers with models and API key status
    """
    registry_providers = get_all_providers()
    result = []

    for reg_provider in registry_providers:
        # Check API key configuration
        has_key = _check_api_key_configured(reg_provider.provider)

        # Convert registry models to API models
        api_models = [
            ModelInfo(
                id=m.id,
                name=m.name,
                description=m.description,
                context_window=m.context_window
            )
            for m in reg_provider.models
        ]

        # Create API provider info
        provider_info = ProviderInfo(
            provider=reg_provider.provider,
            name=reg_provider.name,
            description=reg_provider.description,
            models=api_models,
            api_key_configured=has_key
        )

        result.append(provider_info)

    return result


# =====================
# API Endpoints
# =====================
@router.get("/", response_model=ApiResponse[Optional[LLMConfigData]])
async def get_llm_config() -> ApiResponse[Optional[LLMConfigData]]:
    """
    Get current default LLM configuration.

    Returns the global default provider and model that will be used for new sessions.
    If no configuration is set, returns null (system defaults from llm.py will be used).

    Returns:
        ApiResponse containing LLMConfigData or null
    """
    try:
        config = get_default_llm_config()

        if config:
            return ApiResponse(
                success=True,
                message="Retrieved default LLM configuration",
                data=LLMConfigData(**config)
            )
        else:
            return ApiResponse(
                success=True,
                message="No custom LLM configuration set (using system defaults)",
                data=None
            )

    except Exception as e:
        raise InternalServerError(
            message=f"Failed to get LLM configuration: {str(e)}"
        )


@router.post("/", response_model=ApiResponse[LLMConfigData])
async def update_llm_config(request: LLMConfigUpdateRequest) -> ApiResponse[LLMConfigData]:
    """
    Update default LLM configuration.

    Sets the global default provider and model that will be used for all new sessions.
    The configuration is validated before being saved.

    Args:
        request: LLMConfigUpdateRequest with provider and model

    Returns:
        ApiResponse confirming the update

    Raises:
        BadRequestError: If configuration is invalid
    """
    try:
        # Validate configuration
        is_valid, error_message = validate_llm_config(request.provider, request.model)
        if not is_valid:
            raise BadRequestError(message=f"Invalid LLM configuration: {error_message}")

        # Save configuration
        success = save_default_llm_config(request.provider, request.model)
        if not success:
            raise InternalServerError(message="Failed to save LLM configuration")

        return ApiResponse(
            success=True,
            message=f"Updated default LLM to {request.provider}/{request.model}",
            data=LLMConfigData(provider=request.provider, model=request.model)
        )

    except BadRequestError:
        raise
    except Exception as e:
        raise InternalServerError(
            message=f"Failed to update LLM configuration: {str(e)}"
        )


@router.delete("/", response_model=ApiResponse[None])
async def clear_llm_config() -> ApiResponse[None]:
    """
    Clear default LLM configuration.

    Removes the custom configuration, causing the system to revert to defaults from llm.py.

    Returns:
        ApiResponse confirming the deletion
    """
    try:
        success = clear_default_llm_config()
        if not success:
            raise InternalServerError(message="Failed to clear LLM configuration")

        return ApiResponse(
            success=True,
            message="Cleared custom LLM configuration (reverted to system defaults)",
            data=None
        )

    except Exception as e:
        raise InternalServerError(
            message=f"Failed to clear LLM configuration: {str(e)}"
        )


@router.get("/providers", response_model=ApiResponse[ProviderListData])
async def get_available_providers_endpoint() -> ApiResponse[ProviderListData]:
    """
    Get list of available LLM providers and their models.

    Returns information about each provider including:
    - Provider metadata (name, description)
    - Available models
    - Whether API key is configured

    This endpoint helps the frontend display configuration options.

    Returns:
        ApiResponse containing list of providers
    """
    try:
        providers = _get_available_providers()

        return ApiResponse(
            success=True,
            message=f"Retrieved {len(providers)} providers",
            data=ProviderListData(providers=providers)
        )

    except Exception as e:
        raise InternalServerError(
            message=f"Failed to get providers: {str(e)}"
        )
