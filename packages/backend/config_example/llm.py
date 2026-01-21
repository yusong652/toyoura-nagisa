"""
LLM Configuration Module
Contains all large language model related configurations

Configuration Architecture:
- config/models.yaml: Available providers and models (data definition)
- config/default_llm.json: User's default provider/model choice (runtime config)
- config/llm.py (this file): API keys and provider defaults
- .env: API keys and environment variables (security)
"""
from typing import Optional, Any
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict



class LLMSettings(BaseSettings):
    """
    LLM Configuration - Unified Configuration Reader

    Reads configuration from environment variables with a safe fallback
    provider for bootstrap (app startup, tooling).
    """

    # Environment variable override (LLM_PROVIDER in .env)
    env_provider_override: Optional[str] = Field(
        default=None,
        alias="PROVIDER",  # Maps to LLM_PROVIDER env variable
        description="Provider from environment variable"
    )

    debug: bool = Field(default=False, description="Debug mode")

    model_config = SettingsConfigDict(
        env_file='.env',
        env_nested_delimiter='_',
        case_sensitive=False,
        env_prefix='LLM_',
        extra='ignore'
    )

    @property
    def provider(self) -> str:
        """
        Get the current LLM provider.

        Returns:
            str: Provider identifier (e.g., "google", "anthropic")
        """
        if self.env_provider_override:
            return self.env_provider_override

        return "google"

    def get_openai_config(self) -> Any:
        """Get OpenAI configuration"""
        from backend.infrastructure.llm.providers.openai.config import OpenAIConfig as ProviderOpenAIConfig

        return ProviderOpenAIConfig()  # type: ignore

    def get_google_config(self) -> Any:
        """Get Google configuration"""
        from backend.infrastructure.llm.providers.google.config import GoogleConfig as ProviderGoogleConfig

        return ProviderGoogleConfig()  # type: ignore

    def get_anthropic_config(self) -> Any:
        """Get Anthropic configuration"""
        from backend.infrastructure.llm.providers.anthropic.config import AnthropicConfig as ProviderAnthropicConfig

        return ProviderAnthropicConfig()  # type: ignore

    def get_moonshot_config(self) -> Any:
        """Get Moonshot configuration"""
        from backend.infrastructure.llm.providers.moonshot.config import MoonshotConfig as ProviderMoonshotConfig

        return ProviderMoonshotConfig()  # type: ignore

    def get_openrouter_config(self) -> Any:
        """Get OpenRouter configuration"""
        from backend.infrastructure.llm.providers.openrouter.config import OpenRouterConfig as ProviderOpenRouterConfig

        return ProviderOpenRouterConfig()  # type: ignore

    def get_zhipu_config(self) -> Any:
        """Get Zhipu configuration"""
        from backend.infrastructure.llm.providers.zhipu.config import ZhipuConfig as ProviderZhipuConfig

        return ProviderZhipuConfig()  # type: ignore

    def get_current_llm_config(self):
        """
        Get current LLM configuration based on provider.

        Returns:
            Configuration object for current provider
        """
        config_map = {
            "openai": self.get_openai_config,
            "google": self.get_google_config,
            "anthropic": self.get_anthropic_config,
            "moonshot": self.get_moonshot_config,
            "openrouter": self.get_openrouter_config,
            "zhipu": self.get_zhipu_config,
        }

        config_getter = config_map.get(self.provider)
        if not config_getter:
            raise ValueError(f"Unsupported LLM provider: {self.provider}")

        return config_getter()

    def validate_current_llm(self):
        """
        Validate current LLM configuration - fail fast.

        Returns:
            Validated configuration object

        Raises:
            ValueError: When configuration validation fails
        """
        try:
            config = self.get_current_llm_config()
            return config
        except Exception as e:
            raise ValueError(f"Current LLM configuration validation failed: {e}")

    def get_current_model(self) -> str:
        """
        Get current model name for the selected provider.

        Returns:
            Current model name
        """
        config = self.get_current_llm_config()
        return config.model

def get_llm_settings() -> LLMSettings:
    """Get LLM configuration instance"""
    return LLMSettings()
