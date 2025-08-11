"""
Memory infrastructure module for aiNagisa.

This module provides the memory management system using Mem0 framework
with automatic context injection capabilities.
"""

from .mem0_manager import Mem0MemoryManager
from .memory_injection import (
    MemoryInjectionMiddleware,
    MemoryPerformanceGuard
)

# Convenience alias for backward compatibility
MemoryManager = Mem0MemoryManager

__all__ = [
    "Mem0MemoryManager",
    "MemoryManager",
    "MemoryInjectionMiddleware", 
    "MemoryPerformanceGuard"
]