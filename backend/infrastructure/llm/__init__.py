"""
LLM infrastructure package for aiNagisa with unified architecture.

This package provides a unified interface for multiple LLM providers including
Gemini, Anthropic, OpenAI, and local model support using the new base/shared/providers architecture.
"""

from backend.presentation.models.api_models import ErrorResponse
from backend.infrastructure.llm.llm_factory import get_client, register_client, get_supported_clients, is_client_supported
from backend.infrastructure.llm.base import LLMClientBase
from backend.infrastructure.llm.response_models import LLMResponse

# Import specific client implementations for direct use if needed
from backend.infrastructure.llm.providers.gemini import GeminiClient
from backend.infrastructure.llm.providers.anthropic import AnthropicClient
from backend.infrastructure.llm.providers.openai import OpenAIClient

try:
    from backend.infrastructure.llm.local import LocalLLMClient
except ImportError:
    LocalLLMClient = None

# ========== SOTA架构 - 统一导出 ==========
# 导出核心接口和新架构组件

__all__ = [
    # Factory functions
    "get_client",
    "register_client", 
    "get_supported_clients",
    "is_client_supported",
    
    # Base classes and models
    "LLMClientBase",
    "LLMResponse",
    "LLMResponseItem",
    "ErrorResponse",
    
    # Specific client implementations
    "GeminiClient",
    "AnthropicClient",
    "OpenAIClient",
    "LocalLLMClient",
] 