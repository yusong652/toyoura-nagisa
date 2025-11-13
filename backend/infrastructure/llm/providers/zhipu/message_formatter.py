"""
Zhipu (智谱) Message Formatter

Zhipu uses standard OpenAI Chat Completions API format via zai SDK.
We use the shared ChatCompletionsMessageFormatter which is designed for
providers implementing the standard Chat Completions API.

Note: This is the same format used by Kimi, using role/content/tool_calls structure.
"""

from backend.infrastructure.llm.shared.chat_completions_formatter import ChatCompletionsMessageFormatter

# Zhipu uses the standard OpenAI Chat Completions API format via zai SDK
# We alias ChatCompletionsMessageFormatter for clear semantics
ZhipuMessageFormatter = ChatCompletionsMessageFormatter

__all__ = ['ZhipuMessageFormatter']
