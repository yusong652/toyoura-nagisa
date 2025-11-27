"""
Kimi (Moonshot) LLM Provider

OpenAI-compatible API provider specializing in long-context understanding.
Base URL: https://api.moonshot.cn/v1

Available models:
- moonshot-v1-8k: 8K context window
- moonshot-v1-32k: 32K context window (default)
- moonshot-v1-128k: 128K context window
- kimi-k2-0905-preview: Latest K2 model

Architecture:
Kimi uses OpenAI-compatible Chat Completions API (not Responses API).
Key differences from OpenAI provider:
- KimiToolManager: Standalone implementation using nested tool schema format
- KimiResponseProcessor: Handles ChatCompletion objects (not Response objects)
- KimiContextManager: Manages ChatCompletion responses
- KimiMessageFormatter: Alias to OpenAI formatter (Chat Completions compatible)
"""

from .client import KimiClient
from .config import (
    KimiClientConfig,
    KimiModelSettings,
    get_kimi_client_config
)
from .message_formatter import KimiMessageFormatter
from .context_manager import KimiContextManager
from .tool_manager import KimiToolManager
from .response_processor import KimiResponseProcessor
from .debug import KimiDebugger

__all__ = [
    'KimiClient',
    'KimiClientConfig',
    'KimiModelSettings',
    'get_kimi_client_config',
    'KimiMessageFormatter',
    'KimiContextManager',
    'KimiToolManager',
    'KimiResponseProcessor',
    'KimiDebugger',
]
