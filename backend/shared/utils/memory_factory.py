"""
Memory middleware factory utilities.

Provides singleton access to memory injection middleware.
"""

from typing import Optional
from backend.infrastructure.memory import MemoryInjectionMiddleware
from backend.config.memory import MemoryConfig

# Global memory injection middleware instance
_memory_middleware: Optional[MemoryInjectionMiddleware] = None


def get_memory_middleware() -> MemoryInjectionMiddleware:
    """
    Get or create the global memory injection middleware singleton.
    
    This provides centralized access to the memory injection middleware
    across the application, ensuring consistent configuration and
    avoiding multiple instances.
    
    Returns:
        MemoryInjectionMiddleware: Configured middleware instance
    """
    global _memory_middleware
    if _memory_middleware is None:
        # Create with MemoryConfig from settings
        config = MemoryConfig()
        _memory_middleware = MemoryInjectionMiddleware(config=config)
    return _memory_middleware


def reset_memory_middleware() -> None:
    """
    Reset the global memory middleware instance.
    
    Useful for testing or when configuration changes require
    a fresh middleware instance.
    """
    global _memory_middleware
    _memory_middleware = None