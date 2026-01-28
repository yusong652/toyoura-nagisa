"""
LLM Configuration API.

Provides endpoints for managing LLM provider and model configuration.
Global defaults are stored in config/default_llm.json and apply to all new sessions.
Session overrides are stored in session metadata when a session_id is provided.

Routes:
    GET /api/llm-config - Get current LLM configuration (global or session)
    POST /api/llm-config - Update LLM configuration (global or session)
    DELETE /api/llm-config - Clear LLM configuration (global or session)
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
from backend.infrastructure.storage.session_manager import (
    get_session_llm_config,
    update_session_llm_config,
    clear_session_llm_config,
    get_session_thinking_level,
    update_session_thinking_level,
    VALID_THINKING_LEVELS,
)
from backend.infrastructure.llm.shared.models_registry import (
    get_all_providers,
    get_model_info,
    get_model_thinking_config,
    ModelInfo as RegistryModelInfo,
    ProviderInfo as RegistryProviderInfo,
    ThinkingConfig as RegistryThinkingConfig,
)

router = APIRouter(prefix="/api/llm-config", tags=["llm-config"])


# =====================
# Request/Response Models
# =====================
class LLMConfigData(BaseModel):
    """LLM configuration data."""

    provider: str = Field(..., description="LLM provider name (e.g., 'google', 'anthropic')")
    model: str = Field(..., description="Model identifier (e.g., 'gemini-2.0-flash-exp')")
    secondary_model: Optional[str] = Field(None, description="Secondary model identifier for SubAgents")


class LLMConfigUpdateRequest(BaseModel):
    """Request to update LLM configuration."""

    provider: str = Field(..., description="LLM provider name")
    model: str = Field(..., description="Model identifier")
    secondary_model: Optional[str] = Field(None, description="Secondary model identifier for SubAgents")


class ThinkingConfigInfo(BaseModel):
    """Thinking configuration for API response."""

    mode: str = Field(..., description="Thinking mode: 'none', 'always_on', or 'configurable'")
    default: str = Field(..., description="Default thinking level for new sessions")
    options: List[str] = Field(
        default=["default", "low", "high"], description="Available thinking levels (only for 'configurable' mode)"
    )


class ModelInfo(BaseModel):
    """Model information for API response."""

    id: str = Field(..., description="Model identifier")
    name: str = Field(..., description="Display name")
    description: Optional[str] = Field(None, description="Model description")
    context_window: Optional[int] = Field(None, description="Context window size (tokens)")
    thinking: Optional[ThinkingConfigInfo] = Field(None, description="Thinking configuration")


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


class ThinkingConfigRequest(BaseModel):
    """Request to update thinking configuration."""

    thinking_level: str = Field(..., description="Thinking level: 'default' (no thinking params), 'low', or 'high'")


class ThinkingConfigData(BaseModel):
    """Thinking configuration data."""

    thinking_level: str = Field(..., description="Current thinking level: 'default', 'low', or 'high'")
    mode: str = Field(default="configurable", description="Thinking mode: 'none', 'always_on', or 'configurable'")
    options: List[str] = Field(
        default=["default", "low", "high"], description="Available thinking levels for the current model"
    )


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
    try:
        if provider == "google":
            from backend.infrastructure.llm.providers.google.config import GoogleConfig

            cfg = GoogleConfig()
            return bool(cfg.google_api_key)

        elif provider == "anthropic":
            from backend.infrastructure.llm.providers.anthropic.config import AnthropicConfig

            cfg = AnthropicConfig()
            return bool(cfg.anthropic_api_key)

        elif provider in ["openai", "gpt"]:
            from backend.infrastructure.llm.providers.openai.config import OpenAIConfig

            cfg = OpenAIConfig()
            return bool(cfg.openai_api_key)

        elif provider == "moonshot":
            from backend.infrastructure.llm.providers.moonshot.config import MoonshotConfig

            cfg = MoonshotConfig()
            return bool(cfg.moonshot_api_key)

        elif provider == "zhipu":
            from backend.infrastructure.llm.providers.zhipu.config import ZhipuConfig

            cfg = ZhipuConfig()
            return bool(cfg.zhipu_api_key)

        elif provider == "openrouter":
            from backend.infrastructure.llm.providers.openrouter.config import OpenRouterConfig

            cfg = OpenRouterConfig()
            return bool(cfg.openrouter_api_key)

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
        api_models = []
        for m in reg_provider.models:
            # Convert thinking config if present
            thinking_info = None
            if m.thinking:
                thinking_info = ThinkingConfigInfo(
                    mode=m.thinking.mode, default=m.thinking.default, options=m.thinking.options
                )

            api_models.append(
                ModelInfo(
                    id=m.id,
                    name=m.name,
                    description=m.description,
                    context_window=m.context_window,
                    thinking=thinking_info,
                )
            )

        # Create API provider info
        provider_info = ProviderInfo(
            provider=reg_provider.provider,
            name=reg_provider.name,
            description=reg_provider.description,
            models=api_models,
            api_key_configured=has_key,
        )

        result.append(provider_info)

    return result


# =====================
# API Endpoints
# =====================
@router.get("/", response_model=ApiResponse[Optional[LLMConfigData]])
async def get_llm_config(
    session_id: Optional[str] = None,
) -> ApiResponse[Optional[LLMConfigData]]:
    """
    Get current LLM configuration.

    Returns the session override if session_id is provided, otherwise the global default.
    If no configuration is set, returns null (system defaults from llm.py will be used).

    Returns:
        ApiResponse containing LLMConfigData or null
    """
    try:
        if session_id:
            config = get_session_llm_config(session_id)
            if config:
                return ApiResponse(
                    success=True, message="Retrieved session LLM configuration", data=LLMConfigData(**config)
                )

            config = get_default_llm_config()
            if config:
                return ApiResponse(
                    success=True,
                    message="No session LLM override (using global defaults)",
                    data=LLMConfigData(**config),
                )

            return ApiResponse(
                success=True, message="No custom LLM configuration set (using system defaults)", data=None
            )

        config = get_default_llm_config()

        if config:
            return ApiResponse(
                success=True, message="Retrieved default LLM configuration", data=LLMConfigData(**config)
            )

        return ApiResponse(success=True, message="No custom LLM configuration set (using system defaults)", data=None)

    except Exception as e:
        raise InternalServerError(message=f"Failed to get LLM configuration: {str(e)}")


@router.post("/", response_model=ApiResponse[LLMConfigData])
async def update_llm_config(
    request: LLMConfigUpdateRequest,
    session_id: Optional[str] = None,
) -> ApiResponse[LLMConfigData]:
    """
    Update LLM configuration.

    Sets the session override when session_id is provided, otherwise updates the
    global default provider and model for new sessions. The configuration is
    validated before being saved.

    Args:
        request: LLMConfigUpdateRequest with provider and model

    Returns:
        ApiResponse confirming the update

    Raises:
        BadRequestError: If configuration is invalid
    """
    try:
        # Validate configuration
        is_valid, error_message = validate_llm_config(
            request.provider,
            request.model,
            request.secondary_model,
        )
        if not is_valid:
            raise BadRequestError(message=f"Invalid LLM configuration: {error_message}")

        if session_id:
            success = update_session_llm_config(
                session_id,
                request.provider,
                request.model,
                request.secondary_model,
            )
            if not success:
                raise BadRequestError(message=f"Session not found: {session_id}")

            # Notify frontend about the change
            from backend.infrastructure.websocket.notification_service import WebSocketNotificationService

            llm_config = {
                "provider": request.provider,
                "model": request.model,
                "secondary_model": request.secondary_model,
            }
            await WebSocketNotificationService.send_session_llm_config_update(session_id, llm_config)

            return ApiResponse(
                success=True,
                message=f"Updated session LLM to {request.provider}/{request.model}",
                data=LLMConfigData(
                    provider=request.provider,
                    model=request.model,
                    secondary_model=request.secondary_model,
                ),
            )

        success = save_default_llm_config(
            request.provider,
            request.model,
            request.secondary_model,
        )
        if not success:
            raise InternalServerError(message="Failed to save LLM configuration")

        return ApiResponse(
            success=True,
            message=f"Updated default LLM to {request.provider}/{request.model}",
            data=LLMConfigData(
                provider=request.provider,
                model=request.model,
                secondary_model=request.secondary_model,
            ),
        )

    except BadRequestError:
        raise
    except Exception as e:
        raise InternalServerError(message=f"Failed to update LLM configuration: {str(e)}")


@router.delete("/", response_model=ApiResponse[None])
async def clear_llm_config(
    session_id: Optional[str] = None,
) -> ApiResponse[None]:
    """
    Clear LLM configuration.

    Removes the session override when session_id is provided; otherwise clears the
    global default and reverts to defaults from llm.py.

    Returns:
        ApiResponse confirming the deletion
    """
    try:
        if session_id:
            success = clear_session_llm_config(session_id)
            if not success:
                raise BadRequestError(message=f"Session not found: {session_id}")

            # Notify frontend about the change
            from backend.infrastructure.websocket.notification_service import WebSocketNotificationService

            await WebSocketNotificationService.send_session_llm_config_update(session_id, {})

            return ApiResponse(success=True, message="Cleared session LLM override", data=None)

        success = clear_default_llm_config()
        if not success:
            raise InternalServerError(message="Failed to clear LLM configuration")

        return ApiResponse(
            success=True, message="Cleared custom LLM configuration (reverted to system defaults)", data=None
        )

    except Exception as e:
        raise InternalServerError(message=f"Failed to clear LLM configuration: {str(e)}")


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
            success=True, message=f"Retrieved {len(providers)} providers", data=ProviderListData(providers=providers)
        )

    except Exception as e:
        raise InternalServerError(message=f"Failed to get providers: {str(e)}")


@router.get("/model-details", response_model=ApiResponse[ModelInfo])
async def get_model_details_endpoint(provider: str, model: str) -> ApiResponse[ModelInfo]:
    """
    Get detailed information for a specific model, including context window.
    """
    try:
        info = get_model_info(provider, model)
        if not info:
            raise BadRequestError(message=f"Model {model} not found for provider {provider}")

        return ApiResponse(
            success=True,
            message="Model details retrieved",
            data=ModelInfo(
                id=info.id,
                name=info.name,
                description=info.description,
                context_window=info.context_window,
                thinking=ThinkingConfigInfo(
                    mode=info.thinking.mode, default=info.thinking.default, options=info.thinking.options
                )
                if info.thinking
                else None,
            ),
        )
    except BadRequestError:
        raise
    except Exception as e:
        raise InternalServerError(message=f"Failed to get model details: {str(e)}")


# =====================
# Thinking Configuration Endpoints
# =====================
@router.get("/thinking", response_model=ApiResponse[ThinkingConfigData])
async def get_thinking_config(
    session_id: str,
    provider: Optional[str] = None,
    model: Optional[str] = None,
) -> ApiResponse[ThinkingConfigData]:
    """
    Get thinking/reasoning mode configuration for a session.

    Thinking modes:
    - "none": Model does not support thinking
    - "always_on": Model always uses thinking (native thinking model)
    - "configurable": Thinking can be configured via API params

    Thinking levels (for configurable mode):
    - "default": Don't pass thinking params, use API's default behavior
    - "low": Use low reasoning effort
    - "high": Use high reasoning effort

    Args:
        session_id: Session ID to get thinking config for
        provider: Optional model ID to get model-specific options
        model: Optional model ID to get model-specific options

    Returns:
        ApiResponse containing ThinkingConfigData with current thinking_level and mode
    """
    try:
        thinking_level = get_session_thinking_level(session_id)

        # Get model-specific config from models.yaml
        mode = "configurable"  # Default fallback
        options = list(VALID_THINKING_LEVELS)  # Fallback

        if provider and model:
            thinking_config = get_model_thinking_config(provider, model)
            if thinking_config:
                mode = thinking_config.mode
                if mode == "configurable":
                    options = thinking_config.options
                elif mode == "always_on":
                    # Native thinking model - no configurable options
                    options = []
                else:
                    # mode == "none" - only default allowed
                    options = ["default"]

        # Sanitise thinking_level for response
        # If the stored level is not valid for the current model, return "default"
        return ApiResponse(
            success=True,
            message="Retrieved thinking configuration",
            data=ThinkingConfigData(
                thinking_level=thinking_level if thinking_level in options else "default", mode=mode, options=options
            ),
        )

    except Exception as e:
        raise InternalServerError(message=f"Failed to get thinking configuration: {str(e)}")


@router.post("/thinking", response_model=ApiResponse[ThinkingConfigData])
async def update_thinking_config(
    request: ThinkingConfigRequest,
    session_id: str,
    provider: Optional[str] = None,
    model: Optional[str] = None,
) -> ApiResponse[ThinkingConfigData]:
    """
    Update thinking/reasoning mode configuration for a session.

    Sets the LLM's thinking/reasoning level:
    - "default": Don't pass thinking params (OpenAI default is 'none')
    - "low": Low reasoning effort
    - "high": High reasoning effort

    Provider-specific mappings:
    - OpenAI: reasoning.effort = "low" | "high" (default = no param)
    - Anthropic: thinking.budget_tokens varies by level
    - Gemini: thinking_level = LOW | HIGH
    - Moonshot: thinking.type = "enabled" | "disabled"

    Args:
        request: ThinkingConfigRequest with thinking_level string
        session_id: Session ID to update thinking config for
        provider: Optional provider ID for model-specific validation
        model: Optional model ID for model-specific validation

    Returns:
        ApiResponse confirming the update
    """
    try:
        # Validate thinking level
        if request.thinking_level not in VALID_THINKING_LEVELS:
            raise BadRequestError(
                message=f"Invalid thinking level: {request.thinking_level}. "
                f"Must be one of: {', '.join(VALID_THINKING_LEVELS)}"
            )

        success = update_session_thinking_level(session_id, request.thinking_level)

        if not success:
            raise BadRequestError(message=f"Session not found: {session_id}")

        # Notify frontend about the change via WebSocket
        from backend.infrastructure.websocket.notification_service import WebSocketNotificationService

        await WebSocketNotificationService.send_thinking_level_update(session_id, request.thinking_level)

        # Get model-specific config for response
        mode = "configurable"
        options = list(VALID_THINKING_LEVELS)

        if provider and model:
            thinking_config = get_model_thinking_config(provider, model)
            if thinking_config:
                mode = thinking_config.mode
                if mode == "configurable":
                    options = thinking_config.options

        return ApiResponse(
            success=True,
            message=f"Thinking level set to '{request.thinking_level}'",
            data=ThinkingConfigData(thinking_level=request.thinking_level, mode=mode, options=options),
        )

    except BadRequestError:
        raise
    except ValueError as e:
        raise BadRequestError(message=str(e))
    except Exception as e:
        raise InternalServerError(message=f"Failed to update thinking configuration: {str(e)}")
