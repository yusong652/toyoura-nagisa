"""
LLM infrastructure package for toyoura-nagisa with unified architecture.

This package provides a unified interface for multiple LLM providers.
"""

from backend.presentation.models.api_models import ErrorResponse
from backend.infrastructure.llm.base.client import LLMClientBase
from backend.infrastructure.llm.base.factory import LLMFactory, get_default_factory, initialize_factory
from backend.domain.models.response_models import LLMResponse

from backend.infrastructure.llm.providers.google import GoogleClient
from backend.infrastructure.llm.providers.google_gemini_cli import GoogleGeminiCliClient
from backend.infrastructure.llm.providers.google_gemini_antigravity import GoogleGeminiAntigravityClient
from backend.infrastructure.llm.providers.anthropic import AnthropicClient
from backend.infrastructure.llm.providers.openai import OpenAIClient
from backend.infrastructure.llm.providers.moonshot import MoonshotClient
from backend.infrastructure.llm.providers.zhipu import ZhipuClient

__all__ = [
    # New object-oriented factory
    "LLMFactory",
    "get_default_factory",
    "initialize_factory",
    # Base classes and models
    "LLMClientBase",
    "LLMResponse",
    "LLMResponseItem",
    "ErrorResponse",
    # Specific client implementations
    "GoogleClient",
    "GoogleGeminiCliClient",
    "GoogleGeminiAntigravityClient",
    "AnthropicClient",
    "OpenAIClient",
    "MoonshotClient",
    "ZhipuClient",
]
