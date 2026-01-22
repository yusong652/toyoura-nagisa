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


def _get_system_default_config() -> Optional[Dict[str, Any]]:
    """
    Get system default configuration from config/models.yaml.

    Returns:
        Optional[Dict[str, Any]]: System default configuration or None if not defined
    """
    try:
        if not os.path.exists(MODELS_YAML_FILE):
            return None

        with open(MODELS_YAML_FILE, 'r', encoding='utf-8') as f:
            models_config = yaml.safe_load(f)

        if not isinstance(models_config, dict):
            return None

        default_config = models_config.get('default')
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
            with open(DEFAULT_LLM_CONFIG_FILE, 'r', encoding='utf-8') as f:
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
        config: Dict[str, Any] = {
            "provider": provider,
            "model": model
        }
        if secondary_model:
            config["secondary_model"] = secondary_model

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

    if secondary_model and not is_model_valid_for_provider(provider, secondary_model):
        return False, (
            f"Secondary model '{secondary_model}' is not available for provider '{provider}'"
        )

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
