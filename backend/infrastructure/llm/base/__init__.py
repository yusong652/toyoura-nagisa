"""
Base module for LLM infrastructure with unified architecture.

This module provides the foundation for all LLM provider implementations,
extracting common patterns and providing shared interfaces.
"""

from .client import LLMClientBase
from .context_manager import BaseContextManager
from .tool_manager import BaseToolManager
from .content_generators.base import BaseContentGenerator
from .message_formatter import BaseMessageFormatter
from .response_processor import BaseResponseProcessor
from .factory import LLMFactory, get_default_factory, initialize_factory

__all__ = [
    "LLMClientBase",
    "BaseContextManager", 
    "BaseToolManager",
    "BaseContentGenerator",
    "BaseMessageFormatter",
    "BaseResponseProcessor",
    "LLMFactory",
    "get_default_factory",
    "initialize_factory"
]