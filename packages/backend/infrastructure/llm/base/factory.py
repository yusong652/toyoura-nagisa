"""
LLM Factory - Creates LLM client instances based on configuration.
"""

import logging
from typing import Dict, Optional, Type, Any, List
from backend.infrastructure.llm.base.client import LLMClientBase
from backend.config import get_llm_settings

logger = logging.getLogger(__name__)


class LLMFactory:
    """Factory for creating LLM client instances."""

    def __init__(self):
        self._clients: Dict[str, Type[LLMClientBase]] = {}
        self._register_default_clients()

    def _register_default_clients(self):
        """Register default LLM client implementations."""
        from backend.infrastructure.llm.providers.gemini import GeminiClient
        from backend.infrastructure.llm.providers.anthropic import AnthropicClient
        from backend.infrastructure.llm.providers.openai import OpenAIClient
        from backend.infrastructure.llm.providers.moonshot import MoonshotClient
        from backend.infrastructure.llm.providers.zhipu import ZhipuClient
        from backend.infrastructure.llm.providers.openrouter import OpenRouterClient
        from backend.infrastructure.llm.providers.local.local_llm_client import LocalLLMClient

        self._clients = {
            "gemini": GeminiClient,
            "anthropic": AnthropicClient,
            "gpt": OpenAIClient,
            "openai": OpenAIClient,
            "moonshot": MoonshotClient,
            "zhipu": ZhipuClient,
            "openrouter": OpenRouterClient,
            "local_llm": LocalLLMClient,
        }

    def create_client(self, name: Optional[str] = None, app: Optional[Any] = None) -> LLMClientBase:
        """Create an LLM client instance."""
        llm_settings = get_llm_settings()
        name = name or llm_settings.provider

        if name not in self._clients:
            raise ValueError(f"Unsupported LLM client: '{name}'. Supported: {list(self._clients.keys())}")

        config = self._build_config(name, llm_settings, app)
        logger.info(f"Creating {name} client")
        return self._clients[name](**config)

    def create_secondary_client(self, app: Optional[Any] = None) -> LLMClientBase:
        """Create a secondary LLM client for SubAgents (lighter model to reduce RPM)."""
        llm_settings = get_llm_settings()
        provider = llm_settings.provider

        if provider not in self._clients or provider == "local_llm":
            logger.warning(f"Secondary model not supported for '{provider}', using primary")
            return self.create_client(app=app)

        config = self._build_secondary_config(provider, llm_settings, app)
        logger.info(f"Creating secondary {provider} client")
        return self._clients[provider](**config)

    def _build_config(self, name: str, llm_settings: Any, app: Optional[Any]) -> Dict[str, Any]:
        """Build configuration for primary client."""
        extra = {"app": app} if app else {}
        extra["debug"] = llm_settings.debug

        if name == "gemini":
            cfg = llm_settings.get_gemini_config()
            return {
                "api_key": cfg.google_api_key,
                "extra_config": {**extra, "model": cfg.model, "temperature": cfg.temperature,
                                 "top_p": cfg.top_p, "top_k": cfg.top_k,
                                 "max_output_tokens": cfg.max_output_tokens,
                                 "web_search_max_uses": cfg.web_search_max_uses}
            }
        elif name == "anthropic":
            cfg = llm_settings.get_anthropic_config()
            return {
                "api_key": cfg.anthropic_api_key,
                "extra_config": {**extra, "model": cfg.model, "temperature": cfg.temperature,
                                 "max_tokens": cfg.max_tokens, "top_p": cfg.top_p, "top_k": cfg.top_k,
                                 "web_search_max_uses": cfg.web_search_max_uses}
            }
        elif name in ["gpt", "openai"]:
            cfg = llm_settings.get_openai_config()
            if not cfg.openai_api_key:
                raise ValueError("OpenAI API key not configured")
            return {
                "api_key": cfg.openai_api_key,
                "extra_config": {**extra, "model": cfg.model, "temperature": cfg.temperature,
                                 "top_p": cfg.top_p, "top_k": cfg.top_k, "max_tokens": cfg.max_tokens}
            }
        elif name == "moonshot":
            cfg = llm_settings.get_moonshot_config()
            if not cfg.moonshot_api_key:
                raise ValueError("Moonshot API key not configured")
            return {
                "api_key": cfg.moonshot_api_key,
                "extra_config": {**extra, "model": cfg.model, "temperature": cfg.temperature,
                                 "top_p": cfg.top_p, "max_tokens": cfg.max_tokens}
            }
        elif name == "zhipu":
            cfg = llm_settings.get_zhipu_config()
            if not cfg.zhipu_api_key:
                raise ValueError("Zhipu API key not configured")
            return {
                "api_key": cfg.zhipu_api_key,
                "extra_config": {**extra, "model": cfg.model, "temperature": cfg.temperature,
                                 "top_p": cfg.top_p, "max_tokens": cfg.max_tokens}
            }
        elif name == "openrouter":
            cfg = llm_settings.get_openrouter_config()
            return {
                "api_key": cfg.openrouter_api_key,
                "extra_config": {**extra, "model": cfg.model, "temperature": cfg.temperature,
                                 "top_p": cfg.top_p, "max_tokens": cfg.max_tokens}
            }
        elif name == "local_llm":
            cfg = llm_settings.get_local_llm_config()
            return {
                "server_url": cfg.server_url,
                "api_key": cfg.api_key,
                "model": cfg.model,
                "timeout": cfg.timeout,
                "extra_config": {**extra, "temperature": cfg.temperature,
                                 "top_p": cfg.top_p, "max_tokens": cfg.max_tokens}
            }
        raise ValueError(f"Unknown provider: {name}")

    def _build_secondary_config(self, name: str, llm_settings: Any, app: Optional[Any]) -> Dict[str, Any]:
        """Build configuration for secondary client (uses secondary_model)."""
        extra = {"app": app} if app else {}
        extra["debug"] = llm_settings.debug

        if name == "gemini":
            cfg = llm_settings.get_gemini_config()
            logger.info(f"Secondary model: {cfg.secondary_model}")
            return {
                "api_key": cfg.google_api_key,
                "extra_config": {**extra, "model": cfg.secondary_model, "temperature": cfg.temperature,
                                 "top_p": cfg.top_p, "top_k": cfg.top_k,
                                 "max_output_tokens": cfg.max_output_tokens,
                                 "web_search_max_uses": cfg.web_search_max_uses}
            }
        elif name == "anthropic":
            cfg = llm_settings.get_anthropic_config()
            logger.info(f"Secondary model: {cfg.secondary_model}")
            return {
                "api_key": cfg.anthropic_api_key,
                "extra_config": {**extra, "model": cfg.secondary_model, "temperature": cfg.temperature,
                                 "max_tokens": cfg.max_tokens, "top_p": cfg.top_p, "top_k": cfg.top_k,
                                 "web_search_max_uses": cfg.web_search_max_uses}
            }
        elif name in ["gpt", "openai"]:
            cfg = llm_settings.get_openai_config()
            logger.info(f"Secondary model: {cfg.secondary_model}")
            return {
                "api_key": cfg.openai_api_key,
                "extra_config": {**extra, "model": cfg.secondary_model, "temperature": cfg.temperature,
                                 "top_p": cfg.top_p, "top_k": cfg.top_k, "max_tokens": cfg.max_tokens}
            }
        elif name == "moonshot":
            cfg = llm_settings.get_moonshot_config()
            logger.info(f"Secondary model: {cfg.secondary_model}")
            return {
                "api_key": cfg.moonshot_api_key,
                "extra_config": {**extra, "model": cfg.secondary_model, "temperature": cfg.temperature,
                                 "top_p": cfg.top_p, "max_tokens": cfg.max_tokens}
            }
        elif name == "zhipu":
            cfg = llm_settings.get_zhipu_config()
            logger.info(f"Secondary model: {cfg.secondary_model}")
            return {
                "api_key": cfg.zhipu_api_key,
                "extra_config": {**extra, "model": cfg.secondary_model, "temperature": cfg.temperature,
                                 "top_p": cfg.top_p, "max_tokens": cfg.max_tokens}
            }
        elif name == "openrouter":
            cfg = llm_settings.get_openrouter_config()
            logger.info(f"Secondary model: {cfg.secondary_model}")
            return {
                "api_key": cfg.openrouter_api_key,
                "extra_config": {**extra, "model": cfg.secondary_model, "temperature": cfg.temperature,
                                 "top_p": cfg.top_p, "max_tokens": cfg.max_tokens}
            }
        raise ValueError(f"Secondary model not supported for: {name}")


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
