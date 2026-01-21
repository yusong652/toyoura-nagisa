"""
Anthropic Client Configuration

Unified configuration for Anthropic Claude models including API credentials,
model parameters, and client settings.
"""
import copy
from typing import List, Dict, Any, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AnthropicConfig(BaseSettings):
    """
    Unified Anthropic configuration.

    Combines environment variable loading (API keys) with
    runtime-overridable parameters (model, temperature, etc.).

    Available Models:
    - claude-sonnet-4-5-20250929: Latest Sonnet 4.5 (recommended)
    - claude-haiku-4-5-20251001: Fast and efficient Haiku 4.5
    - claude-opus-4-5-20251101: Most capable Opus 4.5
    - claude-3-7-sonnet-20250219: Sonnet 3.7 with thinking
    """

    # API credentials (from environment variables)
    anthropic_api_key: str = Field(description="Anthropic API key")

    # Model selection (from environment variables, runtime overridable)
    model: str = Field(
        default="claude-sonnet-4-5-20250929",
        description="Default model"
    )
    secondary_model: str = Field(
        default="claude-haiku-4-5-20251001",
        description="Secondary model for SubAgent"
    )

    # Model parameters (runtime overridable)
    max_tokens: int = Field(
        default=1024*16,
        ge=1,
        le=64000,
        description="Maximum number of tokens to generate"
    )
    temperature: float = Field(
        default=1.0,
        ge=0.0,
        le=2.0,
        description="Sampling temperature. Do not set both temperature and top_p."
    )
    top_p: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Nucleus sampling parameter. Do not set both temperature and top_p."
    )
    top_k: Optional[int] = Field(
        default=None,
        ge=1,
        description="Top-K sampling parameter"
    )

    # Thinking configuration (for models that support thinking)
    enable_thinking: bool = Field(
        default=True,
        description="Whether to enable thinking for supported models"
    )
    thinking_budget_tokens: int = Field(
        default=4096,
        ge=1000,
        le=50000,
        description="Budget tokens for thinking process"
    )

    # API settings
    api_version: str = Field(
        default="2023-06-01",
        description="Anthropic API version"
    )
    timeout: int = Field(
        default=60,
        ge=1,
        description="Request timeout in seconds"
    )
    max_retries: int = Field(
        default=3,
        ge=0,
        description="Maximum number of retries for failed requests"
    )

    # Tool settings
    tools_enabled: bool = Field(
        default=True,
        description="Enable tool calling functionality"
    )
    tool_timeout: int = Field(
        default=30,
        ge=1,
        description="Tool execution timeout in seconds"
    )

    # Debug settings
    debug: bool = Field(
        default=False,
        description="Enable debug logging"
    )
    log_requests: bool = Field(
        default=False,
        description="Log API requests and responses"
    )

    model_config = SettingsConfigDict(
        env_file='packages/backend/.env',
        env_nested_delimiter='__',
        case_sensitive=False,
        env_prefix='',
        extra='ignore'
    )

    def supports_thinking(self) -> bool:
        """Check if the current model supports thinking"""
        return (
            self.model.startswith("claude-3-7-") or
            self.model.startswith("claude-sonnet-4-") or
            self.model.startswith("claude-4-") or
            self.model.startswith("claude-opus-")
        )

    def get_api_call_kwargs(
        self,
        system_prompt: str,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Get API call parameters for Anthropic messages.create

        Args:
            system_prompt: System prompt
            messages: Formatted messages for Anthropic API
            tools: Optional tool schemas

        Returns:
            Dict[str, Any]: API call parameters
        """
        # Format system prompt with cache_control for prompt caching
        # See: https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching
        system_with_cache = [
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"}
            }
        ]

        # Add cache_control to the last message for conversation caching
        from .message_formatter import MessageFormatter
        cached_messages = MessageFormatter.add_cache_control_to_messages(messages)

        kwargs = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": cached_messages,
            "system": system_with_cache,
            "temperature": self.temperature,
        }

        # Add optional parameters
        if self.top_p is not None:
            kwargs["top_p"] = self.top_p
        if self.top_k is not None:
            kwargs["top_k"] = self.top_k

        # Add tools with cache_control on the last tool for prompt caching
        # This caches all tool definitions as a single prefix
        if tools and len(tools) > 0:
            # Deep copy to avoid modifying the original tools list
            cached_tools = copy.deepcopy(tools)
            cached_tools[-1]["cache_control"] = {"type": "ephemeral"}
            kwargs["tools"] = cached_tools

        # Add thinking configuration for supported models
        if self.supports_thinking() and self.enable_thinking:
            kwargs["thinking"] = {
                "type": "enabled",
                "budget_tokens": self.thinking_budget_tokens
            }

        return kwargs

    def model_copy(self, **overrides) -> "AnthropicConfig":
        """
        Create a copy with overrides applied.

        Args:
            **overrides: Fields to override

        Returns:
            New AnthropicConfig instance with overrides
        """
        config_dict = self.model_dump()
        config_dict.update(overrides)
        return AnthropicConfig(**config_dict)


def get_anthropic_client_config(**overrides: Any) -> AnthropicConfig:
    """
    Get Anthropic client configuration with optional overrides.

    This function provides backward compatibility and a convenient way
    to create AnthropicConfig with overrides.

    Args:
        **overrides: Configuration overrides. Supports:
            - Direct field overrides: model, temperature, debug, etc.
            - Nested overrides: model_settings={'temperature': 0.8}

    Returns:
        AnthropicConfig instance

    Example:
        >>> config = get_anthropic_client_config(
        ...     model='claude-opus-4-5-20251101',
        ...     temperature=0.8,
        ...     debug=True
        ... )
    """
    # Start with base config from environment
    try:
        base_config = AnthropicConfig()
    except Exception:
        # If env loading fails, use defaults
        base_config = AnthropicConfig(
            anthropic_api_key="",
            model="claude-sonnet-4-5-20250929"
        )

    # Handle nested model_settings overrides for backward compatibility
    if 'model_settings' in overrides:
        model_settings = overrides.pop('model_settings')
        if isinstance(model_settings, dict):
            overrides.update(model_settings)

    # Apply overrides
    if overrides:
        return base_config.model_copy(**overrides)

    return base_config


# Backward compatibility alias
get_anthropic_config = get_anthropic_client_config
