"""
PFC Infrastructure Module - Core integration with ITASCA PFC simulation.

Provides:
- MCP-based communication with PFC server (via pfc-mcp)
- Local task lifecycle management
- Git version tracking for execution snapshots
- Foreground execution registry (Ctrl+B support)
"""

from .task_manager import PfcTaskManager, get_pfc_task_manager
from .foreground_registry import PfcForegroundTaskRegistry, get_pfc_foreground_registry

__all__ = [
    "PfcTaskManager",
    "get_pfc_task_manager",
    "PfcForegroundTaskRegistry",
    "get_pfc_foreground_registry",
]
