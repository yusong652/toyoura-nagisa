"""
Kimi (Moonshot) Response Processor

Kimi uses standard OpenAI Chat Completions API response format.
For simplicity and maintainability, we directly reuse OpenAI's response processor.

This alias improves code readability while avoiding duplication.
"""

from backend.infrastructure.llm.providers.openai.response_processor import OpenAIResponseProcessor

# Kimi uses the exact same response format as OpenAI Chat Completions API
# This alias provides clear semantics without code duplication
KimiResponseProcessor = OpenAIResponseProcessor

__all__ = ['KimiResponseProcessor']
