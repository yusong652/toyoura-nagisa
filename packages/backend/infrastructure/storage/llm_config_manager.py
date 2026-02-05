"""
Global LLM Configuration Manager

Manages the default LLM provider and model configuration that applies to all new sessions.

Configuration Sources (priority order):
1. data/default_llm.json - User customization via frontend settings
2. config/models.yaml (default section) - System default configuration

Configuration Structure:
{
    "provider": "google",  # LLM provider name
    "model": "gemini-2.5-flash",  # Model identifier
    "secondary_model": "gemini-2.5-flash"  # Optional subagent model identifier
}

Design Principles:
- Two-tier defaults: User preference overrides system default
- User config stored in data/ directory (runtime data, not version controlled)
- System default in config/models.yaml (version controlled)
- Simple: Only provider/model/secondary_model, no other parameters
- Validation: Existing llm.py config validates providers and provides API keys
"""

import json
import os
import yaml
from typing import Any, Dict, Optional

# Configuration file paths
# Note: run.py changes working directory to project root, so paths are relative to root
DEFAULT_LLM_CONFIG_FILE = "data/default_llm.json"  # User customization (root/data/)
MODELS_YAML_FILE = "config/models.yaml"  # System defaults (root/config/)

_API_KEY_ENV_VARS = {
    "google": "GOOGLE_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "gpt": "OPENAI_API_KEY",
    "moonshot": "MOONSHOT_API_KEY",
    "zhipu": "ZHIPU_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
}

_API_KEY_DISPLAY_NAMES = {
    "google": "Google",
    "anthropic": "Anthropic",
    "openai": "OpenAI",
    "gpt": "OpenAI",
    "moonshot": "Moonshot",
    "zhipu": "Zhipu",
    "openrouter": "OpenRouter",
}


def _get_env_api_key(provider: str) -> Optional[str]:
    env_var = _API_KEY_ENV_VARS.get(provider)
    if not env_var:
        return None

    value = os.getenv(env_var)
    if value is None and env_var.lower() != env_var:
        value = os.getenv(env_var.lower())
    if value is None and env_var.upper() != env_var:
        value = os.getenv(env_var.upper())

    if value is None:
        return None

    value = value.strip()
    return value or None


def _get_system_default_config() -> Optional[Dict[str, Any]]:
    """
    Get system default configuration from config/models.yaml.

    Returns:
        Optional[Dict[str, Any]]: System default configuration or None if not defined
    """
    try:
        if not os.path.exists(MODELS_YAML_FILE):
            return None

        with open(MODELS_YAML_FILE, "r", encoding="utf-8") as f:
            models_config = yaml.safe_load(f)

        if not isinstance(models_config, dict):
            return None

        default_config = models_config.get("default")
        if not default_config:
            return None

        # Validate required fields
        if not isinstance(default_config, dict):
            print(f"[WARNING] Invalid system default config in models.yaml: not a dict")
            return None

        if "provider" not in default_config or "model" not in default_config:
            print(f"[WARNING] Invalid system default config: missing provider or model")
            return None

        return default_config

    except Exception as e:
        print(f"[WARNING] Failed to load system default from models.yaml: {e}")
        return None


def get_default_llm_config() -> Optional[Dict[str, Any]]:
    """
    Get the global default LLM configuration.

    Configuration priority:
    1. User customization (data/default_llm.json) - highest priority
    2. System default (config/models.yaml default section)
    3. None if neither exists

    Returns:
        Optional[Dict[str, Any]]: Configuration dict with keys:
            - provider: LLM provider name (e.g., "google", "anthropic")
            - model: Model identifier (e.g., "gemini-2.5-flash")
            - secondary_model: Optional subagent model identifier
        Returns None if no configuration is available.

    Example:
        config = get_default_llm_config()
        if config:
            print(f"Using {config['provider']}/{config['model']}")
        else:
            print("No default configuration available")
    """
    # Priority 1: User customization (data/default_llm.json)
    if os.path.exists(DEFAULT_LLM_CONFIG_FILE):
        try:
            with open(DEFAULT_LLM_CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)

            # Validate required fields
            if not isinstance(config, dict):
                print(f"[WARNING] Invalid user LLM config: not a dict")
            elif "provider" not in config or "model" not in config:
                print(f"[WARNING] Invalid user LLM config: missing provider or model")
            else:
                return config

        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"[WARNING] Failed to load user LLM config: {e}")

    # Priority 2: System default (config/models.yaml)
    system_default = _get_system_default_config()
    if system_default:
        return system_default

    # Priority 3: No configuration available
    return None


def save_default_llm_config(
    provider: str,
    model: str,
    secondary_model: Optional[str] = None,
) -> bool:
    """
    Save the global default LLM configuration.

    Updates the default provider and model that will be used for all new sessions.
    Creates the config directory and file if they don't exist.

    Args:
        provider: LLM provider name (e.g., "google", "anthropic", "openai")
        model: Model identifier (e.g., "gemini-2.0-flash-exp", "claude-sonnet-4-5")
        secondary_model: Optional subagent model identifier

    Returns:
        bool: True if save succeeded, False otherwise

    Example:
        success = save_default_llm_config("anthropic", "claude-sonnet-4-5")
        if success:
            print("Default LLM configuration updated")
    """
    try:
        # Ensure config directory exists
        config_dir = os.path.dirname(DEFAULT_LLM_CONFIG_FILE)
        if config_dir:
            os.makedirs(config_dir, exist_ok=True)

        # Build configuration
        config: Dict[str, Any] = {"provider": provider, "model": model}
        if secondary_model:
            config["secondary_model"] = secondary_model

        # Save to file
        with open(DEFAULT_LLM_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4, ensure_ascii=False)

        print(f"[INFO] Saved default LLM config: {provider}/{model}")
        return True

    except Exception as e:
        print(f"[ERROR] Failed to save default LLM config: {e}")
        return False


def clear_default_llm_config() -> bool:
    """
    Clear the global default LLM configuration.

    Removes the configuration file, causing the system to fall back to
    defaults from llm.py configuration.

    Returns:
        bool: True if cleared successfully, False otherwise

    Example:
        success = clear_default_llm_config()
        if success:
            print("Reverted to system default configuration")
    """
    try:
        if os.path.exists(DEFAULT_LLM_CONFIG_FILE):
            os.remove(DEFAULT_LLM_CONFIG_FILE)
            print(f"[INFO] Cleared default LLM config")

        return True

    except Exception as e:
        print(f"[ERROR] Failed to clear default LLM config: {e}")
        return False


def get_provider_secondary_model(provider: str) -> Optional[str]:
    """
    Get secondary model for a provider from its specific configuration.

    Args:
        provider: Provider identifier

    Returns:
        Optional[str]: Secondary model identifier or None if not found
    """
    try:
        if provider == "google":
            from backend.infrastructure.llm.providers.google.config import GoogleConfig

            return GoogleConfig().secondary_model
        if provider == "anthropic":
            from backend.infrastructure.llm.providers.anthropic.config import AnthropicConfig

            return AnthropicConfig().secondary_model
        if provider in ("openai", "gpt"):
            from backend.infrastructure.llm.providers.openai.config import OpenAIConfig

            return OpenAIConfig().secondary_model
        if provider == "moonshot":
            from backend.infrastructure.llm.providers.moonshot.config import MoonshotConfig

            return MoonshotConfig().secondary_model
        if provider == "zhipu":
            from backend.infrastructure.llm.providers.zhipu.config import ZhipuConfig

            return ZhipuConfig().secondary_model
        if provider == "openrouter":
            from backend.infrastructure.llm.providers.openrouter.config import OpenRouterConfig

            return OpenRouterConfig().secondary_model
    except Exception:
        pass

    return None


def build_initial_llm_config() -> Optional[Dict[str, Any]]:
    """
    Build default LLM configuration for new sessions.

    Logic priority:
    1. User customization (data/default_llm.json)
    2. System default (config/models.yaml)
    3. First available provider from registry (fallback)

    Returns:
        Optional[Dict[str, Any]]: Initial configuration dict
    """
    from backend.infrastructure.llm.shared.models_registry import (
        get_all_providers,
        get_provider_models,
        is_model_valid_for_provider,
        is_provider_supported,
    )

    # Try user/system default first
    default_config = get_default_llm_config()
    if isinstance(default_config, dict):
        provider = default_config.get("provider")
        model = default_config.get("model")
        secondary_model = default_config.get("secondary_model")

        if provider and model and is_provider_supported(provider):
            if is_model_valid_for_provider(provider, model):
                # Validate secondary_model
                if secondary_model and not is_model_valid_for_provider(provider, secondary_model):
                    secondary_model = None

                # Fallback to provider's secondary_model or primary model
                if not secondary_model:
                    secondary_model = get_provider_secondary_model(provider) or model

                return {
                    "provider": provider,
                    "model": model,
                    "secondary_model": secondary_model,
                }

    # Fallback to registry
    providers = get_all_providers()
    if not providers:
        return None

    provider = providers[0].provider
    models = get_provider_models(provider)
    if not models:
        return None

    model = models[0].id
    secondary_model = get_provider_secondary_model(provider) or model
    if secondary_model and not is_model_valid_for_provider(provider, secondary_model):
        secondary_model = model

    return {
        "provider": provider,
        "model": model,
        "secondary_model": secondary_model,
    }


def normalize_llm_config(llm_config: Optional[Dict[str, Any]]) -> tuple[Optional[Dict[str, Any]], bool]:
    """
    Normalize and validate an LLM configuration dictionary.
    Fixes missing secondary_model or invalid combinations.

    Args:
        llm_config: Configuration dictionary to validate

    Returns:
        tuple[Optional[Dict[str, Any]], bool]: (Normalized config, whether changes were made)
    """
    from backend.infrastructure.llm.shared.models_registry import (
        is_model_valid_for_provider,
        is_provider_supported,
    )

    if not isinstance(llm_config, dict):
        return build_initial_llm_config(), True

    updated = False
    provider = llm_config.get("provider")
    model = llm_config.get("model")
    secondary_model = llm_config.get("secondary_model")

    if (
        not provider
        or not model
        or not is_provider_supported(provider)
        or not is_model_valid_for_provider(provider, model)
    ):
        return build_initial_llm_config(), True

    # Check secondary_model
    if secondary_model and not is_model_valid_for_provider(provider, secondary_model):
        secondary_model = None
        updated = True

    if not secondary_model:
        secondary_model = get_provider_secondary_model(provider) or model
        updated = True

    if updated:
        llm_config["secondary_model"] = secondary_model

    return llm_config, updated


def is_provider_configured(provider: str) -> tuple[bool, Optional[str]]:
    """
    Check if a provider is configured (API key or OAuth).

    Args:
        provider: Provider identifier

    Returns:
        tuple[bool, Optional[str]]: (is_configured, error_message)
    """
    # OAuth-based providers (google-gemini-cli, google-gemini-antigravity)
    if provider in ("google-gemini-cli", "google-gemini-antigravity"):
        try:
            from backend.infrastructure.oauth.base.types import OAuthProvider
            from backend.infrastructure.storage import oauth_token_storage

            if oauth_token_storage.has_accounts(OAuthProvider.GOOGLE):
                return True, None
        except Exception:
            pass

        return False, "Google OAuth not configured"

    # OAuth-based providers (openai-codex)
    if provider == "openai-codex":
        try:
            from backend.infrastructure.oauth.base.types import OAuthProvider
            from backend.infrastructure.storage import oauth_token_storage

            if oauth_token_storage.has_accounts(OAuthProvider.OPENAI):
                return True, None
        except Exception:
            pass

        return False, "OpenAI OAuth not configured. Use /connects to authenticate with ChatGPT."

    # Check if API key exists for this provider
    if provider in _API_KEY_ENV_VARS:
        if not _get_env_api_key(provider):
            display_name = _API_KEY_DISPLAY_NAMES.get(provider, provider)
            return False, f"{display_name} API key not configured"

    return True, None


def validate_llm_config(
    provider: str,
    model: str,
    secondary_model: Optional[str] = None,
) -> tuple[bool, Optional[str]]:
    """
    Validate LLM configuration against available providers and models.

    Checks:
    1. Provider is supported (exists in models_registry)
    2. Model is valid for the provider
    3. API key/server URL is configured for the provider

    Args:
        provider: LLM provider name to validate
        model: Model identifier to validate
        secondary_model: Optional subagent model identifier to validate

    Returns:
        tuple[bool, Optional[str]]: (is_valid, error_message)
            - is_valid: True if configuration is valid
            - error_message: Error description if invalid, None if valid

    Example:
        is_valid, error = validate_llm_config("anthropic", "claude-sonnet-4-5")
        if not is_valid:
            print(f"Invalid config: {error}")
    """
    from backend.infrastructure.llm.shared.models_registry import is_provider_supported, is_model_valid_for_provider

    # Check if provider is supported
    if not is_provider_supported(provider):
        from backend.infrastructure.llm.shared.models_registry import get_supported_provider_ids

        supported = get_supported_provider_ids()
        return False, f"Unsupported provider '{provider}'. Supported: {supported}"

    # Check if model is valid for this provider
    if not is_model_valid_for_provider(provider, model):
        return False, f"Model '{model}' is not available for provider '{provider}'"

    if secondary_model and not is_model_valid_for_provider(provider, secondary_model):
        return False, (f"Secondary model '{secondary_model}' is not available for provider '{provider}'")

    # Check credentials
    return is_provider_configured(provider)
