"""
OpenAI GPT LLM client implementation.

Modern OpenAI client built on the unified aiNagisa LLM architecture,
featuring full compatibility with the base client interface and
optimized for GPT-4o and GPT-4 models.
"""

from .client import OpenAIClient
from .config import OpenAIClientConfig, get_openai_client_config

__all__ = [
    'OpenAIClient',
    'OpenAIClientConfig', 
    'get_openai_client_config'
]