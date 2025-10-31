"""
Kimi (Moonshot) Debugger

Kimi uses standard OpenAI Chat Completions API format for debugging.
For simplicity and maintainability, we directly reuse OpenAI's debugger.

This alias improves code readability while avoiding duplication.
"""

from backend.infrastructure.llm.providers.openai.debug import OpenAIDebugger

# Kimi uses the exact same API format as OpenAI, so debugging tools are compatible
# This alias provides clear semantics without code duplication
KimiDebugger = OpenAIDebugger

__all__ = ['KimiDebugger']
