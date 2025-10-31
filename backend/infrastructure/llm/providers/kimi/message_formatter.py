"""
Kimi (Moonshot) Message Formatter

Kimi uses standard OpenAI Chat Completions API format.
For simplicity and maintainability, we directly reuse OpenAI's formatter.

This alias improves code readability while avoiding duplication.
If Kimi-specific formatting is needed in the future, this can be expanded
into a full implementation.
"""

from backend.infrastructure.llm.providers.openai.message_formatter import OpenAIMessageFormatter

# Kimi uses the exact same format as OpenAI Chat Completions API
# This alias provides clear semantics without code duplication
KimiMessageFormatter = OpenAIMessageFormatter

__all__ = ['KimiMessageFormatter']
