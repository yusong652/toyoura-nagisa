"""
PFC Tools - ITASCA PFC simulation integration for toyoura-nagisa.

This package provides MCP tools for controlling ITASCA PFC simulations
through a WebSocket connection to a PFC server running in the PFC GUI.

Execution Tools:
- pfc_execute_task: Execute PFC simulation tasks with version tracking
- pfc_check_task_status: Query status of long-running tasks
- pfc_list_tasks: List all tracked long-running tasks

Documentation Browse Tools (like glob + cat):
- pfc_browse_commands: Navigate command hierarchy and retrieve docs by command
- pfc_browse_contact_models: Navigate contact model properties (separate from commands)
- pfc_browse_python_api: Navigate Python SDK hierarchy and retrieve docs by API path

Documentation Query Tools (like grep):
- pfc_query_python_api: Search PFC Python SDK documentation by keywords
- pfc_query_command: Search PFC command documentation by keywords

Usage Pattern:
    - Use browse tools to explore documentation boundaries and navigate by path
    - Use query tools for keyword search when path is unknown
    - browse = "I know where to look" / query = "I know what to search for"

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
from .pfc_browse_commands import register_pfc_browse_commands_tool
from .pfc_browse_contact_models import register_pfc_browse_contact_models_tool
from .pfc_browse_python_api import register_pfc_browse_python_api_tool

__all__ = [
    "register_pfc_task_tool",
    "register_pfc_task_status_tool",
    "register_pfc_list_tasks_tool",
    "register_pfc_query_python_api_tool",
    "register_pfc_query_command_tool",
    "register_pfc_browse_commands_tool",
    "register_pfc_browse_contact_models_tool",
    "register_pfc_browse_python_api_tool",
]
