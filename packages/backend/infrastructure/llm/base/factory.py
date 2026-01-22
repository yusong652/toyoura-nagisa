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
        from backend.infrastructure.llm.providers.anthropic import AnthropicClient
        from backend.infrastructure.llm.providers.openai import OpenAIClient
        from backend.infrastructure.llm.providers.moonshot import MoonshotClient
        from backend.infrastructure.llm.providers.zhipu import ZhipuClient
        from backend.infrastructure.llm.providers.openrouter import OpenRouterClient

        self._clients = {
            "google": GoogleClient,
            "anthropic": AnthropicClient,
            "gpt": OpenAIClient,
            "openai": OpenAIClient,
            "moonshot": MoonshotClient,
            "zhipu": ZhipuClient,
            "openrouter": OpenRouterClient,
        }

    def create_client(self, name: Optional[str] = None, app: Optional[Any] = None) -> LLMClientBase:
        """
        DEPRECATED: Use create_client_from_default_config() instead.

        This method is kept for backward compatibility but will be removed.
        """
        logger.warning(
            "create_client() is deprecated. Use create_client_from_default_config() instead."
        )
        return self.create_client_from_default_config(app=app)

    def create_secondary_client(self, app: Optional[Any] = None) -> LLMClientBase:
        """
        DEPRECATED: Use create_secondary_client_from_default_config() instead.

        This method is kept for backward compatibility but will be removed.
        """
        logger.warning(
            "create_secondary_client() is deprecated. "
            "Use create_secondary_client_from_default_config() instead."
        )
        return self.create_secondary_client_from_default_config(app=app)

    def create_client_from_default_config(self, app: Optional[Any] = None) -> LLMClientBase:
        """
        Create LLM client using default configuration.

        Configuration source: config/models.yaml (default section) or data/default_llm.json
        Used by: App startup, title generation, etc.

        Returns:
            LLMClientBase: Configured LLM client instance

        Raises:
            RuntimeError: If no default configuration is available
        """
        from backend.infrastructure.storage.llm_config_manager import get_default_llm_config

        default_config = get_default_llm_config()
        if not default_config:
            raise RuntimeError(
                "No default LLM configuration found. "
                "Please ensure config/models.yaml has a 'default' section."
            )

        return self.create_client_with_config(
            provider=default_config["provider"],
            model=default_config["model"],
            app=app
        )

    def create_secondary_client_from_default_config(self, app: Optional[Any] = None) -> LLMClientBase:
        """
        Create secondary LLM client using default configuration.

        Used by: SubAgents (lighter model to reduce RPM)

        Returns:
            LLMClientBase: Configured secondary LLM client instance

        Raises:
            RuntimeError: If no default configuration is available
        """
        from backend.infrastructure.storage.llm_config_manager import get_default_llm_config

        default_config = get_default_llm_config()
        if not default_config:
            raise RuntimeError("No default LLM configuration found")

        # Use secondary_model if specified, otherwise use primary model
        model = default_config.get("secondary_model") or default_config["model"]

        return self.create_client_with_config(
            provider=default_config["provider"],
            model=model,
            app=app
        )

    def create_client_with_config(
        self,
        provider: str,
        model: str,
        app: Optional[Any] = None
    ) -> LLMClientBase:
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
            raise ValueError(
                f"Unsupported LLM provider: '{provider}'. "
                f"Supported: {list(self._clients.keys())}"
            )

        # Check cache for existing client instance
        # Include app ID in cache key to distinguish clients with/without app context
        cache_key = f"{provider}:{model}:{id(app) if app else 'None'}"
        if cache_key in self._client_cache:
            # logger.debug(f"Reusing cached {provider} client for model: {model}")
            return self._client_cache[cache_key]

        config = self._build_config(provider, model, app)
        logger.info(f"Creating {provider} client with model: {model}")
        client = self._clients[provider](**config)
        
        # Store in cache
        self._client_cache[cache_key] = client
        return client

    def _build_config(
        self,
        provider: str,
        model: str,
        app: Optional[Any]
    ) -> Dict[str, Any]:
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
            cfg = GoogleConfig()
            return {
                "api_key": cfg.google_api_key,
                "extra_config": {**extra, "model": model}
            }
        elif provider == "anthropic":
            from backend.infrastructure.llm.providers.anthropic.config import AnthropicConfig
            cfg = AnthropicConfig()
            return {
                "api_key": cfg.anthropic_api_key,
                "extra_config": {**extra, "model": model}
            }
        elif provider in ["openai", "gpt"]:
            from backend.infrastructure.llm.providers.openai.config import OpenAIConfig
            cfg = OpenAIConfig()
            if not cfg.openai_api_key:
                raise ValueError("OpenAI API key not configured")
            return {
                "api_key": cfg.openai_api_key,
                "extra_config": {**extra, "model": model}
            }
        elif provider == "moonshot":
            from backend.infrastructure.llm.providers.moonshot.config import MoonshotConfig
            cfg = MoonshotConfig()
            if not cfg.moonshot_api_key:
                raise ValueError("Moonshot API key not configured")
            return {
                "api_key": cfg.moonshot_api_key,
                "extra_config": {**extra, "model": model}
            }
        elif provider == "zhipu":
            from backend.infrastructure.llm.providers.zhipu.config import ZhipuConfig
            cfg = ZhipuConfig()
            if not cfg.zhipu_api_key:
                raise ValueError("Zhipu API key not configured")
            return {
                "api_key": cfg.zhipu_api_key,
                "extra_config": {**extra, "model": model}
            }
        elif provider == "openrouter":
            from backend.infrastructure.llm.providers.openrouter.config import OpenRouterConfig
            cfg = OpenRouterConfig()
            if not cfg.openrouter_api_key:
                raise ValueError("OpenRouter API key not configured")
            return {
                "api_key": cfg.openrouter_api_key,
                "extra_config": {**extra, "model": model}
            }

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
