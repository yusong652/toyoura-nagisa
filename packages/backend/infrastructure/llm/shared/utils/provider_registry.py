"""
Provider registry utilities for dynamic provider component loading.

Provides centralized access to provider-specific components like message formatters,
avoiding circular dependencies and maintaining clean architecture boundaries.
"""

from typing import Type, Any, Optional


def _normalize_provider_name(provider_name: str) -> str:
    if provider_name == "googlegeminicli":
        return "google-gemini-cli"
    if provider_name == "googlegeminiantigravity":
        return "google-gemini-antigravity"
    if provider_name in {"google-claude-antigravity", "googleclaudeantigravity"}:
        return "google-gemini-antigravity"
    return provider_name


def get_message_formatter_class(provider_name: str) -> Type[Any]:
    """
    Get the message formatter class for a specific provider.

    Dynamically imports and returns the appropriate message formatter class
    based on the provider name, avoiding circular dependencies.

    Args:
        provider_name: Name of the LLM provider ('google', 'anthropic', 'openai')

    Returns:
        Type[Any]: Provider-specific message formatter class

    Raises:
        ValueError: If provider name is unsupported
        ImportError: If provider module cannot be imported
    """
    provider_name = _normalize_provider_name(provider_name)

    if provider_name == "google":
        from backend.infrastructure.llm.providers.google.message_formatter import GoogleMessageFormatter

        return GoogleMessageFormatter
    if provider_name in {"google-gemini-cli", "google-gemini-antigravity", "google-claude-antigravity"}:
        from backend.infrastructure.llm.providers.google_gemini_cli.message_formatter import (
            GoogleGeminiCliMessageFormatter,
        )

        return GoogleGeminiCliMessageFormatter
    elif provider_name == "anthropic":
        from backend.infrastructure.llm.providers.anthropic.message_formatter import AnthropicMessageFormatter

        return AnthropicMessageFormatter
    elif provider_name in {"openai", "openai-codex"}:
        from backend.infrastructure.llm.providers.openai.message_formatter import OpenAIMessageFormatter

        return OpenAIMessageFormatter
    elif provider_name == "moonshot":
        from backend.infrastructure.llm.providers.moonshot.message_formatter import MoonshotMessageFormatter

        return MoonshotMessageFormatter
    elif provider_name == "zhipu":
        from backend.infrastructure.llm.providers.zhipu.message_formatter import ZhipuMessageFormatter

        return ZhipuMessageFormatter
    elif provider_name == "openrouter":
        from backend.infrastructure.llm.providers.openrouter.message_formatter import OpenRouterMessageFormatter

        return OpenRouterMessageFormatter
    else:
        raise ValueError(f"Unsupported provider: {provider_name}")


def get_context_manager_class(provider_name: str) -> Type[Any]:
    """
    Get the context manager class for a specific provider.

    Args:
        provider_name: Name of the LLM provider

    Returns:
        Type[Any]: Provider-specific context manager class

    Raises:
        ValueError: If provider name is unsupported
    """
    provider_name = _normalize_provider_name(provider_name)

    if provider_name == "google":
        from backend.infrastructure.llm.providers.google.context_manager import GoogleContextManager

        return GoogleContextManager
    if provider_name in {"google-gemini-cli", "google-gemini-antigravity", "google-claude-antigravity"}:
        from backend.infrastructure.llm.providers.google_gemini_cli.context_manager import (
            GoogleGeminiCliContextManager,
        )

        return GoogleGeminiCliContextManager
    elif provider_name == "anthropic":
        from backend.infrastructure.llm.providers.anthropic.context_manager import AnthropicContextManager

        return AnthropicContextManager
    elif provider_name in {"openai", "openai-codex"}:
        from backend.infrastructure.llm.providers.openai.context_manager import OpenAIContextManager

        return OpenAIContextManager
    elif provider_name == "moonshot":
        from backend.infrastructure.llm.providers.moonshot.context_manager import MoonshotContextManager

        return MoonshotContextManager
    elif provider_name == "zhipu":
        from backend.infrastructure.llm.providers.zhipu.context_manager import ZhipuContextManager

        return ZhipuContextManager
    elif provider_name == "openrouter":
        from backend.infrastructure.llm.providers.openrouter.context_manager import OpenRouterContextManager

        return OpenRouterContextManager
    else:
        raise ValueError(f"Unsupported provider: {provider_name}")


def get_tool_manager_class(provider_name: str) -> Type[Any]:
    """
    Get the tool manager class for a specific provider.

    Args:
        provider_name: Name of the LLM provider

    Returns:
        Type[Any]: Provider-specific tool manager class

    Raises:
        ValueError: If provider name is unsupported
    """
    provider_name = _normalize_provider_name(provider_name)

    if provider_name in {"google", "google-gemini-cli", "google-gemini-antigravity", "google-claude-antigravity"}:
        from backend.infrastructure.llm.providers.google.tool_manager import GoogleToolManager

        return GoogleToolManager
    elif provider_name == "anthropic":
        from backend.infrastructure.llm.providers.anthropic.tool_manager import AnthropicToolManager

        return AnthropicToolManager
    elif provider_name in {"openai", "openai-codex"}:
        from backend.infrastructure.llm.providers.openai.tool_manager import OpenAIToolManager

        return OpenAIToolManager
    elif provider_name == "moonshot":
        from backend.infrastructure.llm.providers.moonshot.tool_manager import MoonshotToolManager

        return MoonshotToolManager
    elif provider_name == "zhipu":
        from backend.infrastructure.llm.providers.zhipu.tool_manager import ZhipuToolManager

        return ZhipuToolManager
    elif provider_name == "openrouter":
        from backend.infrastructure.llm.providers.openrouter.tool_manager import OpenRouterToolManager

        return OpenRouterToolManager
    else:
        raise ValueError(f"Unsupported provider: {provider_name}")


# Provider registry for future extensibility
SUPPORTED_PROVIDERS = [
    "google",
    "google-gemini-cli",
    "google-gemini-antigravity",
    "google-claude-antigravity",
    "anthropic",
    "openai",
    "openai-codex",
    "moonshot",
    "zhipu",
    "openrouter",
    "local",
]


def is_provider_supported(provider_name: str) -> bool:
    """
    Check if a provider is supported.

    Args:
        provider_name: Name of the provider to check

    Returns:
        bool: True if provider is supported, False otherwise
    """
    return provider_name in SUPPORTED_PROVIDERS
