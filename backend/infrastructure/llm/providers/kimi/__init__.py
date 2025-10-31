"""
Kimi (Moonshot) LLM Provider

OpenAI-compatible API provider specializing in long-context understanding.
Base URL: https://api.moonshot.cn/v1

Available models:
- moonshot-v1-8k: 8K context window
- moonshot-v1-32k: 32K context window (default)
- moonshot-v1-128k: 128K context window
- kimi-k2-0905-preview: Latest K2 model
"""

from .client import KimiClient
from .config import (
    KimiClientConfig,
    KimiModelSettings,
    get_kimi_client_config
)
from .message_formatter import KimiMessageFormatter

__all__ = [
    'KimiClient',
    'KimiClientConfig',
    'KimiModelSettings',
    'get_kimi_client_config',
    'KimiMessageFormatter',
]
