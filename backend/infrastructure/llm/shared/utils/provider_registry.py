"""
Provider registry utilities for dynamic provider component loading.

Provides centralized access to provider-specific components like message formatters,
avoiding circular dependencies and maintaining clean architecture boundaries.
"""

from typing import Type, Any, Optional


def get_message_formatter_class(provider_name: str) -> Type[Any]:
    """
    Get the message formatter class for a specific provider.
    
    Dynamically imports and returns the appropriate message formatter class
    based on the provider name, avoiding circular dependencies.
    
    Args:
        provider_name: Name of the LLM provider ('gemini', 'anthropic', 'openai')
    
    Returns:
        Type[Any]: Provider-specific message formatter class
    
    Raises:
        ValueError: If provider name is unsupported
        ImportError: If provider module cannot be imported
    """
    if provider_name == "gemini":
        from backend.infrastructure.llm.providers.gemini.message_formatter import GeminiMessageFormatter
        return GeminiMessageFormatter
    elif provider_name == "anthropic":
        from backend.infrastructure.llm.providers.anthropic.message_formatter import MessageFormatter
        return MessageFormatter
    elif provider_name == "openai":
        from backend.infrastructure.llm.providers.openai.message_formatter import OpenAIMessageFormatter
        return OpenAIMessageFormatter
    elif provider_name == "kimi":
        from backend.infrastructure.llm.providers.kimi.message_formatter import KimiMessageFormatter
        return KimiMessageFormatter
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
    if provider_name == "gemini":
        from backend.infrastructure.llm.providers.gemini.context_manager import GeminiContextManager
        return GeminiContextManager
    elif provider_name == "anthropic":
        from backend.infrastructure.llm.providers.anthropic.context_manager import AnthropicContextManager
        return AnthropicContextManager
    elif provider_name == "openai":
        from backend.infrastructure.llm.providers.openai.context_manager import OpenAIContextManager
        return OpenAIContextManager
    elif provider_name == "kimi":
        from backend.infrastructure.llm.providers.kimi.context_manager import KimiContextManager
        return KimiContextManager
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
    if provider_name == "gemini":
        from backend.infrastructure.llm.providers.gemini.tool_manager import GeminiToolManager
        return GeminiToolManager
    elif provider_name == "anthropic":
        from backend.infrastructure.llm.providers.anthropic.tool_manager import AnthropicToolManager
        return AnthropicToolManager
    elif provider_name == "openai":
        from backend.infrastructure.llm.providers.openai.tool_manager import OpenAIToolManager
        return OpenAIToolManager
    elif provider_name == "kimi":
        from backend.infrastructure.llm.providers.kimi.tool_manager import KimiToolManager
        return KimiToolManager
    else:
        raise ValueError(f"Unsupported provider: {provider_name}")


# Provider registry for future extensibility
SUPPORTED_PROVIDERS = ["gemini", "anthropic", "openai", "kimi", "local"]


def is_provider_supported(provider_name: str) -> bool:
    """
    Check if a provider is supported.
    
    Args:
        provider_name: Name of the provider to check
    
    Returns:
        bool: True if provider is supported, False otherwise
    """
    return provider_name in SUPPORTED_PROVIDERS