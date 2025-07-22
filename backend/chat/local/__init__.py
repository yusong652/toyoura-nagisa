"""
Local Model Framework for aiNagisa

This module provides local model inference capabilities including:
- vLLM client via HTTPS
- Simple configuration and deployment
"""

from .local_llm_client import LocalLLMClient, create_local_llm_client, create_local_llm_client_from_config, get_local_llm_config_dict

__all__ = [
    "LocalLLMClient",
    "create_local_llm_client",
    "create_local_llm_client_from_config",
    "get_local_llm_config_dict"
]

