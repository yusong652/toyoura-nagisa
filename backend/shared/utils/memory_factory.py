"""
Memory middleware factory utilities.

Provides singleton access to memory injection middleware.
"""

from typing import Optional
from backend.infrastructure.memory import MemoryInjectionMiddleware
from backend.infrastructure.memory.mem0_manager import Mem0MemoryManager
from backend.config.memory import MemoryConfig

# Global instances
_memory_middleware: Optional[MemoryInjectionMiddleware] = None
_memory_manager: Optional[Mem0MemoryManager] = None


def get_memory_manager() -> Mem0MemoryManager:
    """
    Get or create the global memory manager singleton.
    
    Returns:
        Mem0MemoryManager: Singleton memory manager instance
    """
    global _memory_manager
    if _memory_manager is None:
        config = MemoryConfig()
        _memory_manager = Mem0MemoryManager(config=config)
    return _memory_manager


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
        # Create with shared memory manager to ensure consistency
        config = MemoryConfig()
        memory_manager = get_memory_manager()  # Use singleton manager
        _memory_middleware = MemoryInjectionMiddleware(
            memory_manager=memory_manager,
            config=config
        )
    return _memory_middleware


def reset_memory_middleware() -> None:
    """
    Reset the global memory middleware instance.
    
    Useful for testing or when configuration changes require
    a fresh middleware instance.
    """
    global _memory_middleware, _memory_manager
    _memory_middleware = None
    _memory_manager = None