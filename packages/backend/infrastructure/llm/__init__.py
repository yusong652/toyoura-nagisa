"""
LLM infrastructure package for toyoura-nagisa with unified architecture.

This package provides a unified interface for multiple LLM providers including
Gemini, Anthropic, OpenAI, and local model support using the new base/shared/providers architecture.
"""

from backend.presentation.models.api_models import ErrorResponse
from backend.infrastructure.llm.base.client import LLMClientBase
from backend.infrastructure.llm.base.factory import LLMFactory, get_default_factory, initialize_factory
from backend.domain.models.response_models import LLMResponse

# Import specific client implementations for direct use if needed
from backend.infrastructure.llm.providers.google import GoogleClient
from backend.infrastructure.llm.providers.anthropic import AnthropicClient
from backend.infrastructure.llm.providers.openai import OpenAIClient
from backend.infrastructure.llm.providers.moonshot import MoonshotClient
from backend.infrastructure.llm.providers.zhipu import ZhipuClient

try:
    from backend.infrastructure.llm.providers.local import LocalLLMClient
except ImportError:
    LocalLLMClient = None

# ========== SOTA架构 - 统一导出 ==========
# 导出核心接口和新架构组件

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
    "AnthropicClient",
    "OpenAIClient",
    "MoonshotClient",
    "ZhipuClient",
    "LocalLLMClient",
] 