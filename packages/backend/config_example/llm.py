"""
LLM Configuration Module
Contains all large language model related configurations

Configuration Architecture:
- config/models.yaml: Available providers and models (data definition)
- config/default_llm.json: User's default provider/model choice (runtime config)
- config/llm.py (this file): API keys and provider defaults
- .env: API keys and environment variables (security)
"""
from __future__ import annotations
from typing import Optional
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

    def get_openai_config(self) -> OpenAIConfig:
        """Get OpenAI configuration"""
        return OpenAIConfig()  # type: ignore

    def get_google_config(self) -> GoogleConfig:
        """Get Google configuration"""
        return GoogleConfig()  # type: ignore

    def get_anthropic_config(self) -> AnthropicConfig:
        """Get Anthropic configuration"""
        return AnthropicConfig()  # type: ignore

    def get_moonshot_config(self) -> MoonshotConfig:
        """Get Moonshot configuration"""
        return MoonshotConfig()  # type: ignore

    def get_openrouter_config(self) -> OpenRouterConfig:
        """Get OpenRouter configuration"""
        return OpenRouterConfig()  # type: ignore

    def get_zhipu_config(self) -> ZhipuConfig:
        """Get Zhipu configuration"""
        return ZhipuConfig()  # type: ignore

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


class OpenAIConfig(BaseSettings):
    """OpenAI Configuration"""

    # API Key - set via environment variable OPENAI_API_KEY
    openai_api_key: Optional[str] = Field(default=None, description="OpenAI API Key")

    # Model configuration
    model: str = Field(default="gpt-4o", description="Model name")
    # Available models: gpt-4o, gpt-4o-mini, gpt-4-turbo, o1-preview, o1-mini

    # Secondary model for SubAgents to reduce primary model RPM consumption
    secondary_model: str = Field(
        default="gpt-4o-mini",
        description="Secondary model for SubAgent to reduce primary model RPM usage"
    )

    
    model_config = SettingsConfigDict(
        env_file='.env',
        env_nested_delimiter='__',
        case_sensitive=False,
        env_prefix='',
        extra='ignore'
    )


class GoogleConfig(BaseSettings):
    """Google (Gemini) Configuration"""

    # API Key - set via environment variable GOOGLE_API_KEY
    google_api_key: str = Field(default="", description="Google API Key")

    # Model configuration
    model: str = Field(default="gemini-2.5-flash", description="Model name")
    # Available models: gemini-2.5-pro, gemini-2.5-flash, gemini-2.0-flash, gemini-1.5-pro

    # Secondary model for SubAgents to reduce primary model RPM consumption
    secondary_model: str = Field(
        default="gemini-2.5-flash",
        description="Secondary model for SubAgent to reduce primary model RPM usage"
    )


    model_config = SettingsConfigDict(
        env_file='.env',
        env_nested_delimiter='__',
        case_sensitive=False,
        env_prefix='',
        extra='ignore'
    )


class AnthropicConfig(BaseSettings):
    """Anthropic Configuration"""

    # API Key - set via environment variable ANTHROPIC_API_KEY
    anthropic_api_key: str = Field(default="", description="Anthropic API Key")

    # Model configuration
    model: str = Field(default="claude-3-5-sonnet-20241022", description="Model name")
    # Available models: claude-3-5-sonnet-20241022, claude-3-opus-20240229, claude-3-haiku-20240307

    # Secondary model for SubAgents to reduce primary model RPM consumption
    secondary_model: str = Field(
        default="claude-3-haiku-20240307",
        description="Secondary model for SubAgent to reduce primary model RPM usage"
    )


    model_config = SettingsConfigDict(
        env_file='.env',
        env_nested_delimiter='__',
        case_sensitive=False,
        env_prefix='',
        extra='ignore'
    )


class MoonshotConfig(BaseSettings):
    """Moonshot Configuration"""

    # API Key - set via environment variable MOONSHOT_API_KEY
    moonshot_api_key: Optional[str] = Field(default=None, description="Moonshot API Key")

    # Model configuration
    model: str = Field(default="kimi-k2-thinking", description="Model name")
    # Available models: kimi-k2-thinking, kimi-k2-0905-preview, kimi-k2-turbo-preview
    # Note: K2 Thinking models expose reasoning_content field with intermediate thinking steps

    # Secondary model for SubAgents
    secondary_model: str = Field(
        default="kimi-k2-0905-preview",
        description="Secondary model for SubAgent to reduce primary model RPM usage"
    )


    model_config = SettingsConfigDict(
        env_file='.env',
        env_nested_delimiter='__',
        case_sensitive=False,
        env_prefix='',
        extra='ignore'
    )


class OpenRouterConfig(BaseSettings):
    """OpenRouter Configuration - supports any model via OpenRouter"""

    # API Key - set via environment variable OPENROUTER_API_KEY
    openrouter_api_key: str = Field(default="", description="OpenRouter API Key")

    # Model configuration - supports any OpenRouter model
    model: str = Field(
        default="anthropic/claude-3.5-sonnet",
        description="OpenRouter model name"
    )
    # Popular models:
    # - anthropic/claude-3.5-sonnet
    # - google/gemini-2.5-pro
    # - openai/gpt-4o
    # - moonshotai/kimi-k2-0905
    # Full list: https://openrouter.ai/models

    # Secondary model for SubAgents
    secondary_model: str = Field(
        default="google/gemini-2.5-flash",
        description="Secondary model for SubAgent to reduce primary model RPM usage"
    )

    # OpenRouter specific headers
    openrouter_http_referer: str = Field(
        default="https://github.com/yusong652/toyoura-nagisa",
        description="HTTP-Referer header for OpenRouter requests"
    )
    openrouter_title: str = Field(
        default="toyoura-nagisa Voice Assistant",
        description="X-Title header for OpenRouter requests"
    )


    # Embedding model for memory system
    embedding_model: str = Field(
        default="google/gemini-embedding-001",
        description="OpenRouter embedding model name"
    )

    model_config = SettingsConfigDict(
        env_file='.env',
        env_nested_delimiter='__',
        case_sensitive=False,
        env_prefix='',
        extra='ignore'
    )


class ZhipuConfig(BaseSettings):
    """Zhipu (智谱) Configuration"""

    # API Key - set via environment variable ZHIPU_API_KEY
    zhipu_api_key: str = Field(default="", description="Zhipu API Key")

    # Model configuration
    model: str = Field(
        default="glm-4",
        description="Zhipu model name"
    )
    # Available models:
    # - glm-4: Most capable, suitable for complex tasks
    # - glm-4-air: Balanced version for most tasks
    # - glm-4-flash: Fast model for simple tasks
    # Full list: https://bigmodel.cn/console/modelcenter/square

    # Secondary model for SubAgents
    secondary_model: str = Field(
        default="glm-4-air",
        description="Secondary model for SubAgent to reduce primary model RPM usage"
    )


    model_config = SettingsConfigDict(
        env_file='.env',
        env_nested_delimiter='__',
        case_sensitive=False,
        env_prefix='',
        extra='ignore'
    )


def get_llm_settings() -> LLMSettings:
    """Get LLM configuration instance"""
    return LLMSettings()
