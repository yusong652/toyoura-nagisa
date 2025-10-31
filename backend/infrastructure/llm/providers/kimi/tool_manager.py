"""
Kimi (Moonshot) Tool Manager

Kimi uses standard OpenAI function calling format for tool management.
For simplicity and maintainability, we directly reuse OpenAI's tool manager.

This alias improves code readability while avoiding duplication.
"""

from backend.infrastructure.llm.providers.openai.tool_manager import OpenAIToolManager

# Kimi uses the exact same tool calling format as OpenAI
# This alias provides clear semantics without code duplication
KimiToolManager = OpenAIToolManager

__all__ = ['KimiToolManager']
