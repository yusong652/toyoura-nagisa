"""
Kimi (Moonshot) Message Formatter

Kimi uses standard OpenAI Chat Completions API format.
We use the shared ChatCompletionsMessageFormatter which is designed for
providers implementing the standard Chat Completions API.

Note: This is different from OpenAI's Responses API used by the OpenAI provider.
- Chat Completions API: Standard role/content/tool_calls format (used by Kimi)
- Responses API: Uses types like "message", "reasoning", "function_call" (used by OpenAI provider)
"""

from backend.infrastructure.llm.shared.chat_completions_formatter import ChatCompletionsMessageFormatter

# Kimi uses the standard OpenAI Chat Completions API format
# We alias ChatCompletionsMessageFormatter for clear semantics
KimiMessageFormatter = ChatCompletionsMessageFormatter

__all__ = ['KimiMessageFormatter']
