"""
LLM Factory - Creates LLM client instances based on configuration.

Factory now requires explicit provider/model configuration.
Use get_default_llm_config() to get system defaults from config/models.yaml.
"""

import logging
from typing import Dict, Optional, Type, Any
from backend.infrastructure.llm.base.client import LLMClientBase

logger = logging.getLogger(__name__)


class LLMFactory:
    """Factory for creating LLM client instances."""

    def __init__(self):
        self._clients: Dict[str, Type[LLMClientBase]] = {}
        self._client_cache: Dict[str, LLMClientBase] = {}
        self._register_default_clients()

    def _register_default_clients(self):
        """Register default LLM client implementations."""
        from backend.infrastructure.llm.providers.google import GoogleClient
        from backend.infrastructure.llm.providers.google_gemini_cli import GoogleGeminiCliClient
        from backend.infrastructure.llm.providers.google_gemini_antigravity import (
            GoogleGeminiAntigravityClient,
            GoogleClaudeAntigravityClient,
        )
        from backend.infrastructure.llm.providers.anthropic import AnthropicClient
        from backend.infrastructure.llm.providers.openai import OpenAIClient
        from backend.infrastructure.llm.providers.openai_codex import OpenAICodexClient
        from backend.infrastructure.llm.providers.moonshot import MoonshotClient
        from backend.infrastructure.llm.providers.zhipu import ZhipuClient
        from backend.infrastructure.llm.providers.openrouter import OpenRouterClient

        self._clients = {
            "google": GoogleClient,
            "google-gemini-cli": GoogleGeminiCliClient,
            "google-gemini-antigravity": GoogleGeminiAntigravityClient,
            "google-claude-antigravity": GoogleClaudeAntigravityClient,
            "anthropic": AnthropicClient,
            "gpt": OpenAIClient,
            "openai": OpenAIClient,
            "openai-codex": OpenAICodexClient,
            "moonshot": MoonshotClient,
            "zhipu": ZhipuClient,
            "openrouter": OpenRouterClient,
        }

    def create_client_with_config(self, provider: str, model: str, app: Optional[Any] = None) -> LLMClientBase:
        """
        Create an LLM client with explicit configuration.

        API keys are sourced from .env files via provider config classes.
        Provider and model must be explicitly specified.

        Args:
            provider: LLM provider name (e.g., "google", "anthropic", "openai")
            model: Model identifier (e.g., "gemini-2.5-flash", "claude-sonnet-4-5-20250929")
            app: Optional application instance for dependency injection

        Returns:
            LLMClientBase: Configured LLM client instance

        Raises:
            ValueError: If provider is not supported or API key is missing
        """
        if provider not in self._clients:
            raise ValueError(f"Unsupported LLM provider: '{provider}'. Supported: {list(self._clients.keys())}")

        client_class = self._clients[provider]
        if provider == "google-gemini-antigravity" and "claude" in model.lower():
            from backend.infrastructure.llm.providers.google_gemini_antigravity import GoogleClaudeAntigravityClient

            client_class = GoogleClaudeAntigravityClient

        # Check cache for existing client instance
        # Include app ID in cache key to distinguish clients with/without app context
        cache_key = f"{provider}:{model}:{id(app) if app else 'None'}"
        if cache_key in self._client_cache:
            # logger.debug(f"Reusing cached {provider} client for model: {model}")
            return self._client_cache[cache_key]

        config = self._build_config(provider, model, app)
        logger.info(f"Creating {provider} client with model: {model}")
        client = client_class(**config)

        # Store in cache
        self._client_cache[cache_key] = client
        return client

    def _build_config(self, provider: str, model: str, app: Optional[Any]) -> Dict[str, Any]:
        """
        Build configuration for LLM client.

        Directly imports provider config classes to get API keys from .env.
        Debug setting is loaded from config/dev.py.

        Args:
            provider: LLM provider name
            model: Model identifier
            app: Optional application instance

        Returns:
            Dict with api_key and extra_config for client initialization
        """
        from backend.config.dev import get_dev_config

        dev_config = get_dev_config()
        extra = {"app": app} if app else {}
        extra["debug"] = dev_config.debug_mode  # From dev.py instead of llm.py

        if provider == "google":
            from backend.infrastructure.llm.providers.google.config import GoogleConfig

            cfg = GoogleConfig(model=model)
            return {"config": cfg, "extra_config": extra}
        elif provider == "google-gemini-cli":
            from backend.infrastructure.llm.providers.google.config import GoogleConfig

            cfg = GoogleConfig(model=model, use_oauth=True)
            return {"config": cfg, "extra_config": extra}
        elif provider in {"google-gemini-antigravity", "google-claude-antigravity"}:
            from backend.infrastructure.llm.providers.google.config import GoogleConfig

            cfg = GoogleConfig(model=model, use_oauth=True)
            return {"config": cfg, "extra_config": extra}
        elif provider == "anthropic":
            from backend.infrastructure.llm.providers.anthropic.config import AnthropicConfig

            cfg = AnthropicConfig(model=model)
            return {"config": cfg, "extra_config": extra}
        elif provider in ["openai", "gpt"]:
            from backend.infrastructure.llm.providers.openai.config import OpenAIConfig

            cfg = OpenAIConfig(model=model)
            if not cfg.openai_api_key:
                raise ValueError("OpenAI API key not configured")
            return {"config": cfg, "extra_config": extra}
        elif provider == "openai-codex":
            from backend.infrastructure.llm.providers.openai_codex.config import OpenAICodexConfig

            cfg = OpenAICodexConfig(model=model)
            # Subscription compatible - no API key or verification needed
            return {"config": cfg, "extra_config": extra}
        elif provider == "moonshot":
            from backend.infrastructure.llm.providers.moonshot.config import MoonshotConfig

            cfg = MoonshotConfig(model=model)
            if not cfg.moonshot_api_key:
                raise ValueError("Moonshot API key not configured")
            return {"config": cfg, "extra_config": extra}
        elif provider == "zhipu":
            from backend.infrastructure.llm.providers.zhipu.config import ZhipuConfig

            cfg = ZhipuConfig(model=model)
            if not cfg.zhipu_api_key:
                raise ValueError("Zhipu API key not configured")
            return {"config": cfg, "extra_config": extra}
        elif provider == "openrouter":
            from backend.infrastructure.llm.providers.openrouter.config import OpenRouterConfig

            cfg = OpenRouterConfig(model=model)
            if not cfg.openrouter_api_key:
                raise ValueError("OpenRouter API key not configured")
            return {"config": cfg, "extra_config": extra}

        raise ValueError(f"Unknown provider: {provider}")


# Global factory instance
_factory: Optional[LLMFactory] = None


def get_default_factory() -> LLMFactory:
    """Get the default factory instance."""
    if _factory is None:
        raise RuntimeError("LLMFactory not initialized. Call initialize_factory() first.")
    return _factory


def initialize_factory() -> LLMFactory:
    """Initialize the default factory instance."""
    global _factory
    if _factory is None:
        _factory = LLMFactory()
        logger.info("LLMFactory initialized")
    return _factory
