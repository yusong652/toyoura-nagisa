"""
PFC Tools - ITASCA PFC simulation integration for aiNagisa.

This package provides MCP tools for controlling ITASCA PFC simulations
through a WebSocket connection to a PFC server running in the PFC GUI.

Tools:
- pfc_execute_command: Execute native PFC commands (no return values)
- pfc_execute_script: Execute Python SDK scripts (with return values)
- pfc_check_task_status: Query status of long-running tasks
- pfc_list_tasks: List all tracked long-running tasks
- pfc_query_python_api: Query PFC Python SDK documentation (NEW)
"""

from .pfc_commands import register_pfc_tools
from .pfc_script import register_pfc_script_tool
from .pfc_task_status import register_pfc_task_status_tool
from .pfc_list_tasks import register_pfc_list_tasks_tool
from .pfc_query_python_api import register_pfc_query_python_api_tool

__all__ = [
    "register_pfc_tools",
    "register_pfc_script_tool",
    "register_pfc_task_status_tool",
    "register_pfc_list_tasks_tool",
    "register_pfc_query_python_api_tool",
]
