# backend/infrastructure/llm/base.py
# Legacy base file - redirect to new architecture

from .base.client import LLMClientBase

# Re-export for backward compatibility
__all__ = ["LLMClientBase"]