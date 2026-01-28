"""
Moonshot LLM Provider

OpenAI-compatible API provider specializing in long-context understanding.
Base URL: https://api.moonshot.ai/v1

Available models:
- kimi-k2.5: Native multimodal model with vision, coding, and agentic capabilities (262K context)
  - Thinking mode (default): Includes reasoning traces, recommended temperature=1.0
  - Instant mode: No reasoning traces, recommended temperature=0.6
- kimi-k2-thinking: Deep reasoning model with extended context (262K)
- kimi-k2-thinking-turbo: Fast thinking model (262K)
- kimi-k2-0905-preview: K2 preview release (262K)

Architecture:
Moonshot uses OpenAI-compatible Chat Completions API (not Responses API).
Key differences from OpenAI provider:
- MoonshotToolManager: Standalone implementation using nested tool schema format
- MoonshotResponseProcessor: Handles ChatCompletion objects (not Response objects)
- MoonshotContextManager: Manages ChatCompletion responses
- MoonshotMessageFormatter: Alias to OpenAI formatter (Chat Completions compatible)
"""

from .client import MoonshotClient
from .config import MoonshotConfig

__all__ = [
    'MoonshotClient',
    'MoonshotConfig',
    'MoonshotMessageFormatter',
    'MoonshotContextManager',
    'MoonshotToolManager',
    'MoonshotResponseProcessor',
    'MoonshotDebugger',
]
