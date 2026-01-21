"""
LLM Models Registry

Centralized registry of available LLM providers and their models.
This module provides the single source of truth for:
- Supported providers
- Available models per provider
- Model metadata (display names, descriptions)

Configuration:
- Primary: Loads from config/models.yaml (YAML format)
- Fallback: Uses hardcoded defaults if YAML not found

Usage:
    from backend.infrastructure.llm.shared.models_registry import (
        get_all_providers,
        get_provider_models,
        is_provider_supported
    )

Design:
- YAML-based: Easy to maintain without code changes
- Type-safe: Pydantic models for validation
- Resilient: Falls back to defaults if YAML missing
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
# Models Registry
# =====================

# Google Gemini
GOOGLE_MODELS = [
    ModelInfo(
        id="gemini-2.0-flash-exp",
        name="Gemini 2.0 Flash (Experimental)",
        description="Latest experimental model with enhanced capabilities",
        context_window=1_048_576  # 1M tokens
    ),
    ModelInfo(
        id="gemini-2.0-flash-thinking-exp-01-21",
        name="Gemini 2.0 Flash Thinking (01-21)",
        description="Experimental model with extended thinking capabilities",
        context_window=1_048_576
    ),
    ModelInfo(
        id="gemini-exp-1206",
        name="Gemini Experimental 1206",
        description="Experimental release from December 2024",
        context_window=200_000
    ),
    ModelInfo(
        id="gemini-2.5-flash",
        name="Gemini 2.5 Flash",
        description="Fast and efficient model for everyday tasks",
        context_window=1_048_576
    ),
]

# Anthropic Claude
ANTHROPIC_MODELS = [
    ModelInfo(
        id="claude-sonnet-4-5-20250929",
        name="Claude Sonnet 4.5",
        description="Latest Sonnet model with improved performance",
        context_window=200_000
    ),
    ModelInfo(
        id="claude-3-7-sonnet-20250219",
        name="Claude 3.7 Sonnet",
        description="Claude 3.7 Sonnet released February 2025",
        context_window=200_000
    ),
    ModelInfo(
        id="claude-3-5-sonnet-20241022",
        name="Claude 3.5 Sonnet",
        description="Previous generation Sonnet model",
        context_window=200_000
    ),
]

# OpenAI GPT
OPENAI_MODELS = [
    ModelInfo(
        id="gpt-4o",
        name="GPT-4o",
        description="Latest GPT-4 optimized model",
        context_window=128_000
    ),
    ModelInfo(
        id="gpt-4-turbo",
        name="GPT-4 Turbo",
        description="Fast and efficient GPT-4",
        context_window=128_000
    ),
    ModelInfo(
        id="gpt-4",
        name="GPT-4",
        description="Original GPT-4 model",
        context_window=8_192
    ),
]

# Moonshot AI
MOONSHOT_MODELS = [
    ModelInfo(
        id="moonshot-v1-8k",
        name="Moonshot v1 8K",
        description="8K context window",
        context_window=8_000
    ),
    ModelInfo(
        id="moonshot-v1-32k",
        name="Moonshot v1 32K",
        description="32K context window",
        context_window=32_000
    ),
    ModelInfo(
        id="moonshot-v1-128k",
        name="Moonshot v1 128K",
        description="128K context window",
        context_window=128_000
    ),
]

# Zhipu AI
ZHIPU_MODELS = [
    ModelInfo(
        id="glm-4-plus",
        name="GLM-4 Plus",
        description="Enhanced GLM-4 with better performance",
        context_window=128_000
    ),
    ModelInfo(
        id="glm-4",
        name="GLM-4",
        description="Latest GLM generation",
        context_window=128_000
    ),
    ModelInfo(
        id="glm-4-air",
        name="GLM-4 Air",
        description="Lightweight GLM-4 variant",
        context_window=128_000
    ),
]

# OpenRouter
OPENROUTER_MODELS = [
    ModelInfo(
        id="anthropic/claude-3.5-sonnet",
        name="Claude 3.5 Sonnet (via OpenRouter)",
        description="Anthropic Claude via OpenRouter",
        context_window=200_000
    ),
    ModelInfo(
        id="google/gemini-2.0-flash-exp:free",
        name="Gemini 2.0 Flash (via OpenRouter)",
        description="Google Gemini via OpenRouter (free tier)",
        context_window=1_048_576
    ),
    ModelInfo(
        id="openai/gpt-4o",
        name="GPT-4o (via OpenRouter)",
        description="OpenAI GPT-4o via OpenRouter",
        context_window=128_000
    ),
]

# Local LLM
LOCAL_LLM_MODELS = [
    ModelInfo(
        id="local-model",
        name="Local Model",
        description="Model running on local server (vLLM/Ollama)",
        context_window=None  # Depends on local setup
    ),
]


# =====================
# Provider Registry (Fallback Defaults)
# =====================
_DEFAULT_PROVIDERS_REGISTRY: List[ProviderInfo] = [
    ProviderInfo(
        provider="google",
        name="Google Gemini",
        description="Google's Gemini models with advanced reasoning and long context",
        models=GOOGLE_MODELS
    ),
    ProviderInfo(
        provider="anthropic",
        name="Anthropic Claude",
        description="Anthropic's Claude models with strong tool use and analysis",
        models=ANTHROPIC_MODELS
    ),
    ProviderInfo(
        provider="openai",
        name="OpenAI GPT",
        description="OpenAI's GPT models",
        models=OPENAI_MODELS
    ),
    ProviderInfo(
        provider="moonshot",
        name="Moonshot AI",
        description="Moonshot's Kimi models with extended context",
        models=MOONSHOT_MODELS
    ),
    ProviderInfo(
        provider="zhipu",
        name="Zhipu AI",
        description="Zhipu's GLM models",
        models=ZHIPU_MODELS
    ),
    ProviderInfo(
        provider="openrouter",
        name="OpenRouter",
        description="Access to multiple model providers through OpenRouter",
        models=OPENROUTER_MODELS
    ),
    ProviderInfo(
        provider="local_llm",
        name="Local LLM",
        description="Self-hosted LLM via vLLM or Ollama",
        models=LOCAL_LLM_MODELS
    ),
]


# =====================
# YAML Configuration Loader
# =====================
MODELS_YAML_PATH = "config/models.yaml"


def _load_providers_from_yaml() -> Optional[List[ProviderInfo]]:
    """
    Load providers from YAML configuration file.

    Returns:
        Optional[List[ProviderInfo]]: Loaded providers, None if failed

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
        print(f"[INFO] Models config not found: {MODELS_YAML_PATH}, using defaults")
        return None

    try:
        with open(MODELS_YAML_PATH, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        if not data or 'providers' not in data:
            print(f"[WARNING] Invalid YAML structure in {MODELS_YAML_PATH}")
            return None

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
        return None
    except Exception as e:
        print(f"[ERROR] Failed to load {MODELS_YAML_PATH}: {e}")
        return None


# Initialize registry (try YAML first, fall back to defaults)
PROVIDERS_REGISTRY: List[ProviderInfo] = (
    _load_providers_from_yaml() or _DEFAULT_PROVIDERS_REGISTRY
)


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
