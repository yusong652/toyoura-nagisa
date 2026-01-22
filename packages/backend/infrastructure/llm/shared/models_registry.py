"""
LLM Models Registry

Centralized registry of available LLM providers and their models.
This module provides the single source of truth for:
- Supported providers
- Available models per provider
- Model metadata (display names, descriptions)

Configuration:
- Loads from config/models.yaml (YAML format)

Usage:
    from backend.infrastructure.llm.shared.models_registry import (
        get_all_providers,
        get_provider_models,
        is_provider_supported
    )

Design:
- YAML-based: Easy to maintain without code changes
- Type-safe: Pydantic models for validation
- Resilient: Returns empty registry if YAML missing
"""

import os
import yaml
from typing import List, Optional
from pydantic import BaseModel, Field, ValidationError


# =====================
# Data Models
# =====================
class ModelInfo(BaseModel):
    """Information about a specific model."""
    id: str = Field(..., description="Model identifier for API calls")
    name: str = Field(..., description="Display name for UI")
    description: Optional[str] = Field(None, description="Model description")
    context_window: Optional[int] = Field(None, description="Context window size (tokens)")


class ProviderInfo(BaseModel):
    """Information about an LLM provider."""
    provider: str = Field(..., description="Provider identifier (matches llm.py config)")
    name: str = Field(..., description="Display name for UI")
    description: str = Field(..., description="Provider description")
    models: List[ModelInfo] = Field(default_factory=list, description="Available models")


# =====================
# YAML Configuration Loader
# =====================
# Note: run.py changes working directory to project root, so path is relative to root
MODELS_YAML_PATH = "config/models.yaml"  # Project root config/models.yaml


def _load_providers_from_yaml() -> List[ProviderInfo]:
    """
    Load providers from YAML configuration file.

    Returns:
        List[ProviderInfo]: Loaded providers (empty if failed)

    The YAML structure should be:
        providers:
          - provider: google
            name: Google Gemini
            description: ...
            models:
              - id: gemini-2.0-flash-exp
                name: Gemini 2.0 Flash
                description: ...
                context_window: 1048576
    """
    if not os.path.exists(MODELS_YAML_PATH):
        print(f"[WARNING] Models config not found: {MODELS_YAML_PATH}")
        return []

    try:
        with open(MODELS_YAML_PATH, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        if not data or 'providers' not in data:
            print(f"[WARNING] Invalid YAML structure in {MODELS_YAML_PATH}")
            return []

        providers = []
        for provider_data in data['providers']:
            # Parse models
            models = []
            for model_data in provider_data.get('models', []):
                try:
                    model = ModelInfo(**model_data)
                    models.append(model)
                except ValidationError as e:
                    print(f"[WARNING] Invalid model in {provider_data.get('provider')}: {e}")
                    continue

            # Parse provider
            try:
                provider = ProviderInfo(
                    provider=provider_data['provider'],
                    name=provider_data['name'],
                    description=provider_data.get('description', ''),
                    models=models
                )
                providers.append(provider)
            except (KeyError, ValidationError) as e:
                print(f"[WARNING] Invalid provider entry: {e}")
                continue

        print(f"[INFO] Loaded {len(providers)} providers from {MODELS_YAML_PATH}")
        return providers

    except yaml.YAMLError as e:
        print(f"[ERROR] Failed to parse {MODELS_YAML_PATH}: {e}")
        return []
    except Exception as e:
        print(f"[ERROR] Failed to load {MODELS_YAML_PATH}: {e}")
        return []


# Initialize registry (YAML only)
PROVIDERS_REGISTRY: List[ProviderInfo] = _load_providers_from_yaml()


# =====================
# Public API
# =====================

def get_all_providers() -> List[ProviderInfo]:
    """
    Get list of all registered providers with their models.

    Returns:
        List[ProviderInfo]: All available providers

    Example:
        providers = get_all_providers()
        for provider in providers:
            print(f"{provider.name}: {len(provider.models)} models")
    """
    return PROVIDERS_REGISTRY


def get_provider_models(provider: str) -> Optional[List[ModelInfo]]:
    """
    Get list of models for a specific provider.

    Args:
        provider: Provider identifier (e.g., "google", "anthropic")

    Returns:
        Optional[List[ModelInfo]]: List of models, None if provider not found

    Example:
        models = get_provider_models("google")
        if models:
            print(f"Google has {len(models)} models")
    """
    for p in PROVIDERS_REGISTRY:
        if p.provider == provider:
            return p.models
    return None


def get_provider_info(provider: str) -> Optional[ProviderInfo]:
    """
    Get complete provider information.

    Args:
        provider: Provider identifier

    Returns:
        Optional[ProviderInfo]: Provider info, None if not found

    Example:
        info = get_provider_info("anthropic")
        if info:
            print(f"{info.name}: {info.description}")
    """
    for p in PROVIDERS_REGISTRY:
        if p.provider == provider:
            return p
    return None


def is_provider_supported(provider: str) -> bool:
    """
    Check if a provider is supported.

    Args:
        provider: Provider identifier to check

    Returns:
        bool: True if provider is supported

    Example:
        if is_provider_supported("google"):
            print("Google is supported")
    """
    return any(p.provider == provider for p in PROVIDERS_REGISTRY)


def is_model_valid_for_provider(provider: str, model: str) -> bool:
    """
    Check if a model is valid for a specific provider.

    Args:
        provider: Provider identifier
        model: Model identifier

    Returns:
        bool: True if model exists for provider

    Example:
        if is_model_valid_for_provider("google", "gemini-2.0-flash-exp"):
            print("Valid model")
    """
    models = get_provider_models(provider)
    if not models:
        return False
    return any(m.id == model for m in models)


def get_supported_provider_ids() -> List[str]:
    """
    Get list of all supported provider identifiers.

    Returns:
        List[str]: Provider IDs

    Example:
        providers = get_supported_provider_ids()
        # ["google", "anthropic", "openai", ...]
    """
    return [p.provider for p in PROVIDERS_REGISTRY]
