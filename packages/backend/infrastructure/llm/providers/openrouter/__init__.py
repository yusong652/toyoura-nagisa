"""
OpenRouter LLM Provider

Universal API gateway providing access to 100+ LLMs from multiple providers.
Base URL: https://openrouter.ai/api/v1

Supported Models (examples):
- anthropic/claude-sonnet-4-5: Anthropic Claude Sonnet 4.5
- google/gemini-2.5-pro: Google Gemini 2.5 Pro
- meta-llama/llama-3.3-70b-instruct: Meta Llama 3.3 70B
- moonshotai/kimi-k2-0905: Kimi K2 (via OpenRouter)
- deepseek/deepseek-chat: DeepSeek Chat
- And many more... See: https://openrouter.ai/models

Architecture:
OpenRouter uses OpenAI-compatible Chat Completions API (not Responses API).
This provider is based on Moonshot implementation with these differences:
- OpenRouterToolManager: Uses nested tool schema format (OpenAI compatible)
- OpenRouterResponseProcessor: Handles ChatCompletion objects
- OpenRouterContextManager: Manages ChatCompletion responses
- OpenRouterMessageFormatter: Alias to OpenAI formatter (Chat Completions compatible)
- No provider-specific features (like Moonshot's $web_search)

Use Cases:
- Quick access to multiple LLM providers without separate integrations
- Cost optimization through model routing
- Testing different models with unified interface
- Fallback when native provider APIs are unavailable
"""

from .client import OpenRouterClient
from .config import (
    OpenRouterClientConfig,
    OpenRouterModelSettings,
    get_openrouter_client_config
)
from .message_formatter import OpenRouterMessageFormatter
from .context_manager import OpenRouterContextManager
from .tool_manager import OpenRouterToolManager
from .response_processor import OpenRouterResponseProcessor
from .debug import OpenRouterDebugger

__all__ = [
    'OpenRouterClient',
    'OpenRouterClientConfig',
    'OpenRouterModelSettings',
    'get_openrouter_client_config',
    'OpenRouterMessageFormatter',
    'OpenRouterContextManager',
    'OpenRouterToolManager',
    'OpenRouterResponseProcessor',
    'OpenRouterDebugger',
]
