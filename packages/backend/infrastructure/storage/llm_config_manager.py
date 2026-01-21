"""
Global LLM Configuration Manager

Manages the default LLM provider and model configuration that applies to all new sessions.
Configuration is stored in a JSON file and automatically loaded when creating new sessions.

Configuration Structure:
{
    "provider": "google",  # LLM provider name
    "model": "gemini-2.0-flash-exp"  # Model identifier
}

Design Principles:
- Global default: One configuration for all sessions
- File-based: Persisted in config directory
- Simple: Only provider and model, no other parameters
- Validation: Existing llm.py config validates providers and provides API keys
"""

import json
import os
from typing import Any, Dict, Optional

# Configuration file path
DEFAULT_LLM_CONFIG_FILE = "config/default_llm.json"


def get_default_llm_config() -> Optional[Dict[str, Any]]:
    """
    Get the global default LLM configuration.

    Returns the default provider and model that should be used for new sessions.
    If no configuration file exists, returns None (use system defaults from llm.py).

    Returns:
        Optional[Dict[str, Any]]: Configuration dict with keys:
            - provider: LLM provider name (e.g., "google", "anthropic")
            - model: Model identifier (e.g., "gemini-2.0-flash-exp")
        Returns None if configuration file doesn't exist.

    Example:
        config = get_default_llm_config()
        if config:
            print(f"Using {config['provider']}/{config['model']}")
        else:
            print("Using system default from llm.py")
    """
    if not os.path.exists(DEFAULT_LLM_CONFIG_FILE):
        return None

    try:
        with open(DEFAULT_LLM_CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = json.load(f)

        # Validate required fields
        if not isinstance(config, dict):
            print(f"[WARNING] Invalid default LLM config: not a dict")
            return None

        if "provider" not in config or "model" not in config:
            print(f"[WARNING] Invalid default LLM config: missing provider or model")
            return None

        return config

    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"[WARNING] Failed to load default LLM config: {e}")
        return None


def save_default_llm_config(provider: str, model: str) -> bool:
    """
    Save the global default LLM configuration.

    Updates the default provider and model that will be used for all new sessions.
    Creates the config directory and file if they don't exist.

    Args:
        provider: LLM provider name (e.g., "google", "anthropic", "openai")
        model: Model identifier (e.g., "gemini-2.0-flash-exp", "claude-sonnet-4-5")

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
        config = {
            "provider": provider,
            "model": model
        }

        # Save to file
        with open(DEFAULT_LLM_CONFIG_FILE, 'w', encoding='utf-8') as f:
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


def validate_llm_config(provider: str, model: str) -> tuple[bool, Optional[str]]:
    """
    Validate LLM configuration against available providers and models.

    Checks:
    1. Provider is supported (exists in models_registry)
    2. Model is valid for the provider
    3. API key/server URL is configured for the provider

    Args:
        provider: LLM provider name to validate
        model: Model identifier to validate

    Returns:
        tuple[bool, Optional[str]]: (is_valid, error_message)
            - is_valid: True if configuration is valid
            - error_message: Error description if invalid, None if valid

    Example:
        is_valid, error = validate_llm_config("anthropic", "claude-sonnet-4-5")
        if not is_valid:
            print(f"Invalid config: {error}")
    """
    from backend.config import get_llm_settings
    from backend.infrastructure.llm.shared.models_registry import (
        is_provider_supported,
        is_model_valid_for_provider
    )

    # Check if provider is supported
    if not is_provider_supported(provider):
        from backend.infrastructure.llm.shared.models_registry import get_supported_provider_ids
        supported = get_supported_provider_ids()
        return False, f"Unsupported provider '{provider}'. Supported: {supported}"

    # Check if model is valid for this provider
    if not is_model_valid_for_provider(provider, model):
        return False, f"Model '{model}' is not available for provider '{provider}'"

    # Check if API key exists for this provider
    try:
        llm_settings = get_llm_settings()

        if provider == "google":
            cfg = llm_settings.get_google_config()
            if not cfg.google_api_key:
                return False, "Google API key not configured"

        elif provider == "anthropic":
            cfg = llm_settings.get_anthropic_config()
            if not cfg.anthropic_api_key:
                return False, "Anthropic API key not configured"

        elif provider in ["openai", "gpt"]:
            cfg = llm_settings.get_openai_config()
            if not cfg.openai_api_key:
                return False, "OpenAI API key not configured"

        elif provider == "moonshot":
            cfg = llm_settings.get_moonshot_config()
            if not cfg.moonshot_api_key:
                return False, "Moonshot API key not configured"

        elif provider == "zhipu":
            cfg = llm_settings.get_zhipu_config()
            if not cfg.zhipu_api_key:
                return False, "Zhipu API key not configured"

        elif provider == "openrouter":
            cfg = llm_settings.get_openrouter_config()
            if not cfg.openrouter_api_key:
                return False, "OpenRouter API key not configured"

    except Exception as e:
        return False, f"Failed to validate configuration: {str(e)}"

    return True, None
