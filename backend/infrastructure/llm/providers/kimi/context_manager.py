"""
Kimi (Moonshot) Context Manager

Kimi uses standard OpenAI Chat Completions API format for context management.
For simplicity and maintainability, we directly reuse OpenAI's context manager.

This alias improves code readability while avoiding duplication.
"""

from backend.infrastructure.llm.providers.openai.context_manager import OpenAIContextManager

# Kimi uses the exact same context management as OpenAI Chat Completions API
# This alias provides clear semantics without code duplication
KimiContextManager = OpenAIContextManager

__all__ = ['KimiContextManager']
