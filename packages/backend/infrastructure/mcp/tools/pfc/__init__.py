"""
PFC Tools - ITASCA PFC simulation integration for aiNagisa.

This package provides MCP tools for controlling ITASCA PFC simulations
through a WebSocket connection to a PFC server running in the PFC GUI.

Execution Tools:
- pfc_execute_task: Execute PFC simulation tasks with version tracking
- pfc_check_task_status: Query status of long-running tasks
- pfc_list_tasks: List all tracked long-running tasks

Documentation Query Tools:
- pfc_query_python_api: Query PFC Python SDK documentation (115 APIs, modules, objects)
- pfc_query_command: Query PFC command documentation (115 commands + model properties)

Version Tracking:
    Each pfc_execute_task creates a git snapshot for traceability.
    Use git_commit in task info to trace code versions.

Note: All PFC command execution is done through Python scripts using itasca.command().
      Query pfc_query_command for command syntax, then use in scripts.
"""

from .pfc_execute_task import register_pfc_task_tool
from .pfc_task_status import register_pfc_task_status_tool
from .pfc_list_tasks import register_pfc_list_tasks_tool
from .pfc_query_python_api import register_pfc_query_python_api_tool
from .pfc_query_command import register_pfc_query_command_tool

__all__ = [
    "register_pfc_task_tool",
    "register_pfc_task_status_tool",
    "register_pfc_list_tasks_tool",
    "register_pfc_query_python_api_tool",
    "register_pfc_query_command_tool",
]
