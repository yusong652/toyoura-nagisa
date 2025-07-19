"""
Local Model Framework for aiNagisa

This module provides local model inference capabilities including:
- vLLM high-performance inference server
- Ollama lightweight model serving
- HPC remote GPU acceleration
- Mixed local/remote routing
"""

from .base_local_client import BaseLocalClient
from .vllm_client import VLLMClient
from .ollama_client import OllamaClient

__all__ = [
    "BaseLocalClient",
    "VLLMClient", 
    "OllamaClient"
]