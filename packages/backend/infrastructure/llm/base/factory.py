"""
LLM Factory class with proper object-oriented design.

This module provides a modular, object-oriented factory for creating LLM client instances
with proper dependency injection and configuration management.
"""

import logging
from typing import Dict, Optional, Type, Any, List
from backend.infrastructure.llm.base.client import LLMClientBase
from backend.config import get_llm_settings

logger = logging.getLogger(__name__)


class LLMFactory:
    """
    Object-oriented factory for creating and managing LLM client instances.
    
    This factory provides a clean interface for:
    - Client registration and discovery
    - Instance creation with proper configuration
    - Instance caching for performance optimization
    - Configuration management per client type
    """
    
    def __init__(self):
        """Initialize the LLM factory with empty registries."""
        self._clients: Dict[str, Type[LLMClientBase]] = {}
        self._instances: Dict[str, LLMClientBase] = {}
        self._supported_clients: List[str] = []
        
        # Register default clients
        self._register_default_clients()
    
    def _register_default_clients(self):
        """Register the default LLM client implementations."""
        from backend.infrastructure.llm.providers.gemini import GeminiClient
        from backend.infrastructure.llm.providers.anthropic import AnthropicClient
        from backend.infrastructure.llm.providers.openai import OpenAIClient
        from backend.infrastructure.llm.providers.kimi import KimiClient
        from backend.infrastructure.llm.providers.zhipu import ZhipuClient
        from backend.infrastructure.llm.providers.openrouter import OpenRouterClient
        from backend.infrastructure.llm.providers.local.local_llm_client import LocalLLMClient

        self.register_client("gemini", GeminiClient)
        self.register_client("anthropic", AnthropicClient)
        self.register_client("gpt", OpenAIClient)
        self.register_client("openai", OpenAIClient)  # Alias for GPT
        self.register_client("kimi", KimiClient)
        self.register_client("zhipu", ZhipuClient)
        self.register_client("openrouter", OpenRouterClient)
        self.register_client("local_llm", LocalLLMClient)
    
    def register_client(self, name: str, client_class: Type[LLMClientBase]) -> None:
        """
        Register a new LLM client class.
        
        Args:
            name: Unique identifier for the LLM client
            client_class: The LLM client class to register
        """
        self._clients[name] = client_class
        if name not in self._supported_clients:
            self._supported_clients.append(name)
        logger.info(f"Registered LLM client: {name}")
    
    def get_supported_clients(self) -> List[str]:
        """
        Get the list of currently supported LLM clients.
        
        Returns:
            List of supported client names
        """
        return self._supported_clients.copy()
    
    def is_client_supported(self, name: str) -> bool:
        """
        Check if the specified LLM client is supported.
        
        Args:
            name: LLM client name
            
        Returns:
            True if supported, False otherwise
        """
        return name in self._clients
    
    def create_client(self, name: Optional[str] = None, app: Optional[Any] = None, **kwargs) -> LLMClientBase:
        """
        Create or retrieve an LLM client instance.
        
        This method supports multiple cloud and local model clients:
        - gemini: Google Gemini client with enhanced tool calling
        - anthropic: Anthropic Claude client with function calling
        - gpt/openai: OpenAI GPT client with function calling
        - local_llm: Local LLM inference server (includes Ollama support)
        
        Args:
            name: Name of the LLM client to create. If None, uses the configured type.
            app: Optional FastAPI app instance for context injection.
            **kwargs: Arguments to pass to the client constructor
            
        Returns:
            An LLM client instance configured for the current architecture
            
        Raises:
            ValueError: If the requested LLM client is not supported
        """
        # Get LLM configuration
        llm_settings = get_llm_settings()
        
        # Use configured provider if name not specified
        name = name or llm_settings.provider
        
        # Validate client support
        if not self.is_client_supported(name):
            supported_list = ", ".join(self._supported_clients)
            raise ValueError(
                f"❌ Unsupported LLM client: '{name}'\n"
                f"📋 Supported clients: {supported_list}\n"
                f"🚀 Available options:\n"
                f"   - gemini: Cloud-based Gemini API with tool calling\n"
                f"   - anthropic: Anthropic Claude with function calling\n"
                f"   - gpt/openai: OpenAI GPT with function calling\n"
                f"   - kimi: Kimi/Moonshot \n"
                f"   - local_llm: Local LLM inference server (includes Ollama)\n"
                f"💡 Solution: Configure your LLM to use one of the supported clients."
            )
        
        # Prepare client configuration
        client_config = self._prepare_client_config(name, llm_settings, app, **kwargs)
        
        # Generate cache key for instance management
        cache_key = self._generate_cache_key(name, client_config)
        
        # Return cached instance if available
        if cache_key in self._instances:
            logger.debug(f"Reusing cached {name} client instance")
            return self._instances[cache_key]
        
        # Create new client instance
        logger.info(f"Creating new {name} client instance")
        client = self._clients[name](**client_config)
        self._instances[cache_key] = client
        
        return client
    
    def _prepare_client_config(self, name: str, llm_settings: Any, app: Optional[Any], **kwargs) -> Dict[str, Any]:
        """
        Prepare configuration dictionary for client creation.
        
        Args:
            name: Client name
            llm_settings: LLM settings instance
            app: Optional FastAPI app instance
            **kwargs: Additional arguments
            
        Returns:
            Configuration dictionary
        """
        client_config = {
            "extra_config": kwargs
        }
        
        # Add app instance to extra_config if provided
        if app:
            client_config["extra_config"]["app"] = app
        
        # Configure based on client type
        if name == "gemini":
            gemini_config = llm_settings.get_gemini_config()
            client_config["api_key"] = gemini_config.google_api_key
            client_config["extra_config"].update({
                "model": gemini_config.model,
                "temperature": gemini_config.temperature,
                "top_p": gemini_config.top_p,
                "top_k": gemini_config.top_k,
                "max_output_tokens": gemini_config.max_output_tokens,
                "web_search_max_uses": gemini_config.web_search_max_uses,
                "debug": llm_settings.debug,
            })
        elif name == "anthropic":
            anthropic_config = llm_settings.get_anthropic_config()
            client_config["api_key"] = anthropic_config.anthropic_api_key
            client_config["extra_config"].update({
                "model": anthropic_config.model,
                "temperature": anthropic_config.temperature,
                "max_tokens": anthropic_config.max_tokens,
                "top_p": anthropic_config.top_p,
                "top_k": anthropic_config.top_k,
                "web_search_max_uses": anthropic_config.web_search_max_uses,
                "debug": llm_settings.debug,
            })
        elif name in ["gpt", "openai"]:
            openai_config = llm_settings.get_openai_config()

            # Get API key (Responses API only, no OpenRouter support)
            api_key = openai_config.openai_api_key

            if not api_key:
                raise ValueError("OpenAI API key 未配置")

            client_config["api_key"] = api_key

            client_config["extra_config"].update({
                "model": openai_config.model,
                "temperature": openai_config.temperature,
                "top_p": openai_config.top_p,
                "top_k": openai_config.top_k,
                "max_tokens": openai_config.max_tokens,
                "debug": llm_settings.debug,
            })
        elif name == "kimi":
            kimi_config = llm_settings.get_kimi_config()

            # Use Moonshot API key directly
            api_key = kimi_config.moonshot_api_key
            if not api_key:
                raise ValueError("Moonshot API key (MOONSHOT_API_KEY) 未配置")

            client_config["api_key"] = api_key
            client_config["extra_config"].update({
                "model": kimi_config.model,
                "temperature": kimi_config.temperature,
                "top_p": kimi_config.top_p,
                "max_tokens": kimi_config.max_tokens,
                "debug": llm_settings.debug,
            })
        elif name == "zhipu":
            zhipu_config = llm_settings.get_zhipu_config()

            # Get Zhipu API key
            api_key = zhipu_config.zhipu_api_key
            if not api_key:
                raise ValueError("Zhipu API key (ZHIPU_API_KEY) 未配置")

            client_config["api_key"] = api_key
            client_config["extra_config"].update({
                "model": zhipu_config.model,
                "temperature": zhipu_config.temperature,
                "top_p": zhipu_config.top_p,
                "max_tokens": zhipu_config.max_tokens,
                "debug": llm_settings.debug,
            })
        elif name == "openrouter":
            openrouter_config = llm_settings.get_openrouter_config()
            client_config["api_key"] = openrouter_config.openrouter_api_key
            client_config["extra_config"].update({
                "model": openrouter_config.model,
                "temperature": openrouter_config.temperature,
                "top_p": openrouter_config.top_p,
                "max_tokens": openrouter_config.max_tokens,
                "debug": llm_settings.debug,
            })
        elif name == "local_llm":
            local_llm_config = llm_settings.get_local_llm_config()
            client_config.update({
                "server_url": local_llm_config.server_url,
                "api_key": local_llm_config.api_key,
                "model": local_llm_config.model,
                "timeout": local_llm_config.timeout,
            })
            client_config["extra_config"].update({
                "temperature": local_llm_config.temperature,
                "top_p": local_llm_config.top_p,
                "max_tokens": local_llm_config.max_tokens,
            })

        return client_config
    
    def _generate_cache_key(self, name: str, config: Dict[str, Any]) -> str:
        """
        Generate a cache key for client instance management.
        
        Args:
            name: Client name
            config: Client configuration
            
        Returns:
            Cache key string
        """
        # Create a more efficient cache key
        key_parts = [name]
        if "api_key" in config:
            # Use hash of API key instead of full key for security
            key_parts.append(f"key_{hash(config['api_key'])}")
        
        # Add essential config parameters
        extra_config = config.get("extra_config", {})
        if "model" in extra_config:
            key_parts.append(f"model_{extra_config['model']}")
        
        return ":".join(key_parts)
    
    def create_secondary_client(self, app: Optional[Any] = None, **kwargs) -> LLMClientBase:
        """
        Create or retrieve a secondary LLM client instance for SubAgents.

        This client uses a lighter/cheaper model (e.g., gemini-2.5-flash instead of gemini-3-pro,
        or claude-haiku instead of claude-sonnet) to reduce RPM consumption on the primary model.

        Currently supports:
        - gemini: Uses secondary_model from GeminiConfig
        - anthropic: Uses secondary_model from AnthropicConfig
        - openai: Uses secondary_model from OpenAIConfig

        Args:
            app: Optional FastAPI app instance for context injection.
            **kwargs: Arguments to pass to the client constructor

        Returns:
            An LLM client instance configured with the secondary model

        Raises:
            ValueError: If secondary model is not supported for the current provider
        """
        llm_settings = get_llm_settings()
        provider = llm_settings.provider

        if provider == "gemini":
            return self._create_secondary_gemini_client(llm_settings, app, **kwargs)
        elif provider == "anthropic":
            return self._create_secondary_anthropic_client(llm_settings, app, **kwargs)
        elif provider in ["openai", "gpt"]:
            return self._create_secondary_openai_client(llm_settings, app, **kwargs)
        else:
            logger.warning(f"Secondary model not supported for provider '{provider}', using primary client")
            return self.create_client(app=app, **kwargs)

    def _create_secondary_gemini_client(self, llm_settings: Any, app: Optional[Any], **kwargs) -> LLMClientBase:
        """Create secondary Gemini client with lighter model."""
        gemini_config = llm_settings.get_gemini_config()
        secondary_model = gemini_config.secondary_model

        cache_key = f"gemini:secondary:{secondary_model}"
        if cache_key in self._instances:
            logger.debug(f"Reusing cached secondary Gemini client ({secondary_model})")
            return self._instances[cache_key]

        logger.info(f"Creating secondary Gemini client with model: {secondary_model}")

        client_config = {
            "api_key": gemini_config.google_api_key,
            "extra_config": {
                "model": secondary_model,
                "temperature": gemini_config.temperature,
                "top_p": gemini_config.top_p,
                "top_k": gemini_config.top_k,
                "max_output_tokens": gemini_config.max_output_tokens,
                "web_search_max_uses": gemini_config.web_search_max_uses,
                "debug": llm_settings.debug,
            }
        }

        if app:
            client_config["extra_config"]["app"] = app

        from backend.infrastructure.llm.providers.gemini import GeminiClient
        client = GeminiClient(**client_config)
        self._instances[cache_key] = client
        return client

    def _create_secondary_anthropic_client(self, llm_settings: Any, app: Optional[Any], **kwargs) -> LLMClientBase:
        """Create secondary Anthropic client with lighter model (e.g., Haiku)."""
        anthropic_config = llm_settings.get_anthropic_config()
        secondary_model = anthropic_config.secondary_model

        cache_key = f"anthropic:secondary:{secondary_model}"
        if cache_key in self._instances:
            logger.debug(f"Reusing cached secondary Anthropic client ({secondary_model})")
            return self._instances[cache_key]

        logger.info(f"Creating secondary Anthropic client with model: {secondary_model}")

        client_config = {
            "api_key": anthropic_config.anthropic_api_key,
            "extra_config": {
                "model": secondary_model,
                "temperature": anthropic_config.temperature,
                "max_tokens": anthropic_config.max_tokens,
                "top_p": anthropic_config.top_p,
                "top_k": anthropic_config.top_k,
                "web_search_max_uses": anthropic_config.web_search_max_uses,
                "debug": llm_settings.debug,
            }
        }

        if app:
            client_config["extra_config"]["app"] = app

        from backend.infrastructure.llm.providers.anthropic import AnthropicClient
        client = AnthropicClient(**client_config)
        self._instances[cache_key] = client
        return client

    def _create_secondary_openai_client(self, llm_settings: Any, app: Optional[Any], **kwargs) -> LLMClientBase:
        """Create secondary OpenAI client with lighter model (e.g., GPT-5-mini)."""
        openai_config = llm_settings.get_openai_config()
        secondary_model = openai_config.secondary_model

        cache_key = f"openai:secondary:{secondary_model}"
        if cache_key in self._instances:
            logger.debug(f"Reusing cached secondary OpenAI client ({secondary_model})")
            return self._instances[cache_key]

        logger.info(f"Creating secondary OpenAI client with model: {secondary_model}")

        client_config = {
            "api_key": openai_config.openai_api_key,
            "extra_config": {
                "model": secondary_model,
                "temperature": openai_config.temperature,
                "top_p": openai_config.top_p,
                "top_k": openai_config.top_k,
                "max_tokens": openai_config.max_tokens,
                "debug": llm_settings.debug,
            }
        }

        if app:
            client_config["extra_config"]["app"] = app

        from backend.infrastructure.llm.providers.openai import OpenAIClient
        client = OpenAIClient(**client_config)
        self._instances[cache_key] = client
        return client

    def clear_cache(self):
        """Clear all cached client instances."""
        self._instances.clear()
        logger.info("Cleared LLM client instance cache")

    def get_cached_instances(self) -> Dict[str, LLMClientBase]:
        """
        Get all cached client instances.

        Returns:
            Dictionary of cached instances
        """
        return self._instances.copy()


# Factory instance will be created at application startup
default_factory: Optional[LLMFactory] = None

def get_default_factory() -> LLMFactory:
    """
    Get the default factory instance.
    
    Returns:
        The default LLMFactory instance
        
    Raises:
        RuntimeError: If factory has not been initialized
    """
    if default_factory is None:
        raise RuntimeError(
            "LLMFactory has not been initialized. "
            "Call initialize_factory() during application startup."
        )
    return default_factory

def initialize_factory() -> LLMFactory:
    """
    Initialize the default factory instance.
    
    This should be called during application startup to ensure
    proper dependency injection and lifecycle management.
    
    Returns:
        The initialized LLMFactory instance
    """
    global default_factory
    if default_factory is None:
        default_factory = LLMFactory()
        logger.info("LLMFactory initialized successfully")
    return default_factory
