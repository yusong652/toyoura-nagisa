"""
Anthropic Claude Client Module

This module provides integration with the Anthropic Claude API, using an architecture similar to the Gemini client.
Key Features:
- Internal loop handling for tool calls, avoiding API layer recursion
- MCP tool integration
- Session-isolated tool caching
- Unified message processing workflow
- Modular architecture: message formatting, response processing, content generation, and debugging tools

Components:
- AnthropicClient: Main client class
- AnthropicMessageFormatter: Message format conversion
- AnthropicResponseProcessor: Response processing and parsing
- ContentGenerators: Title generation, image prompts, etc.
- AnthropicDebugger: Debugging and logging tools
- Config & Constants: Configuration management and constant definitions
"""

from .client import AnthropicClient
from .message_formatter import AnthropicMessageFormatter
from .response_processor import AnthropicResponseProcessor
from .debug import AnthropicDebugger
from .config import AnthropicConfig
from .constants import SUPPORTED_MODELS, DEFAULT_MODEL

__all__ = [
    "AnthropicClient",
    "AnthropicMessageFormatter",
    "AnthropicResponseProcessor",
    "AnthropicDebugger",
    "AnthropicConfig",
    "SUPPORTED_MODELS",
    "DEFAULT_MODEL"
]
