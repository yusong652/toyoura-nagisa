"""
OpenRouter Message Formatter

OpenRouter uses standard OpenAI Chat Completions API format.
For simplicity and maintainability, we directly reuse OpenAI's formatter.

This alias improves code readability while avoiding duplication.
"""

from backend.infrastructure.llm.providers.openai.message_formatter import OpenAIMessageFormatter

# OpenRouter uses the exact same format as OpenAI Chat Completions API
# This alias provides clear semantics without code duplication
OpenRouterMessageFormatter = OpenAIMessageFormatter

__all__ = ['OpenRouterMessageFormatter']
