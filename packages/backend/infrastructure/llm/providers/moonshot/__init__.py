"""
Moonshot LLM Provider

OpenAI-compatible API provider specializing in long-context understanding.
Base URL: https://api.moonshot.cn/v1

Available models:
- moonshot-v1-8k: 8K context window
- moonshot-v1-32k: 32K context window (default)
- moonshot-v1-128k: 128K context window
- kimi-k2-0905-preview: Latest K2 model

Architecture:
Moonshot uses OpenAI-compatible Chat Completions API (not Responses API).
Key differences from OpenAI provider:
- MoonshotToolManager: Standalone implementation using nested tool schema format
- MoonshotResponseProcessor: Handles ChatCompletion objects (not Response objects)
- MoonshotContextManager: Manages ChatCompletion responses
- MoonshotMessageFormatter: Alias to OpenAI formatter (Chat Completions compatible)
"""

from .client import MoonshotClient
from .config import (
    MoonshotConfig,
    get_moonshot_client_config
)
from .message_formatter import MoonshotMessageFormatter
from .context_manager import MoonshotContextManager
from .tool_manager import MoonshotToolManager
from .response_processor import MoonshotResponseProcessor
from .debug import MoonshotDebugger

__all__ = [
    'MoonshotClient',
    'MoonshotConfig',
    'get_moonshot_client_config',
    'MoonshotMessageFormatter',
    'MoonshotContextManager',
    'MoonshotToolManager',
    'MoonshotResponseProcessor',
    'MoonshotDebugger',
]
