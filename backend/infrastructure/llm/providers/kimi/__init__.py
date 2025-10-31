"""
Kimi (Moonshot) LLM Provider

OpenAI-compatible API provider specializing in long-context understanding.
Base URL: https://api.moonshot.cn/v1

Available models:
- moonshot-v1-8k: 8K context window
- moonshot-v1-32k: 32K context window (default)
- moonshot-v1-128k: 128K context window
"""

from .config import (
    KimiClientConfig,
    KimiModelSettings,
    get_kimi_client_config
)

__all__ = [
    'KimiClientConfig',
    'KimiModelSettings',
    'get_kimi_client_config',
]
