"""
PFC Task Manager - Long-running task tracking and lifecycle management.

This package provides task lifecycle management separate from command execution.
Status queries do not go through the executor as they are not PFC commands.

Public API:
    - TaskManager: Main task registry and management interface
    - Task: Abstract base class for task types (for type hints)
    - CommandTask: Command execution task type
    - ScriptTask: Script execution task type with output capture

Python 3.6 compatible implementation.
"""

# Public API exports (for backward compatibility)
from .manager import TaskManager
from .task_base import Task
from .task_types import CommandTask, ScriptTask

__all__ = [
    "TaskManager",
    "Task",
    "CommandTask",
    "ScriptTask",
]
