"""
PFC Tools - ITASCA PFC simulation integration for toyoura-nagisa.

This package provides MCP tools for controlling ITASCA PFC simulations
through a WebSocket connection to a PFC server running in the PFC GUI.

Execution Tools:
- pfc_execute_task: Execute PFC simulation tasks with version tracking
- pfc_check_task_status: Query status of long-running tasks
- pfc_list_tasks: List all tracked long-running tasks
- pfc_interrupt_task: Request interrupt for running tasks

Diagnostic Tools:
- pfc_capture_plot: Capture plot screenshots for multimodal visual diagnosis

Documentation Browse Tools (like glob + cat - navigate by path):
- pfc_browse_commands: Navigate command hierarchy (e.g., "ball create")
- pfc_browse_reference: Navigate reference docs (e.g., "contact-models linear")
- pfc_browse_python_api: Navigate Python SDK hierarchy (e.g., "itasca.ball.Ball.pos")

Documentation Query Tools (like grep - search by keywords):
- pfc_query_python_api: Search Python SDK by keywords → returns API paths
- pfc_query_command: Search commands by keywords → returns command paths

Usage Pattern:
    Browse vs Query are PARALLEL tools (not sequential):
    - Browse = "I know where to look" → navigate directly to documentation
    - Query = "I have keywords" → search and get paths, then browse for details

    Typical workflow:
    1. Query: pfc_query_python_api("ball velocity") → finds "itasca.ball.Ball.vel"
    2. Browse: pfc_browse_python_api("itasca.ball.Ball.vel") → full documentation

    Or directly browse if you know the path:
    - pfc_browse_commands("ball create") → full command documentation
    - pfc_browse_python_api("itasca.ball.create") → full API documentation

Version Tracking:
    Each pfc_execute_task creates a git snapshot for traceability.
    Use git_commit in task info to trace code versions.
    Snapshots are stored on a special 'pfc-executions' branch.

IMPORTANT - Git Branch Warning:
    NEVER checkout or switch to the 'pfc-executions' branch in PFC project repositories.
    This branch is automatically managed by the version tracking system and contains
    execution snapshots. Working on this branch will cause git snapshot creation to fail.
    If you accidentally end up on this branch, switch back to 'master' or 'main':
        git checkout master

Note: All PFC command execution is done through Python scripts using itasca.command().
"""

from .pfc_execute_task import register_pfc_task_tool
from .pfc_check_task_status import register_pfc_task_status_tool
from .pfc_list_tasks import register_pfc_list_tasks_tool
from .pfc_interrupt_task import register_pfc_interrupt_task_tool
from .pfc_query_python_api import register_pfc_query_python_api_tool
from .pfc_query_command import register_pfc_query_command_tool
from .pfc_browse_commands import register_pfc_browse_commands_tool
from .pfc_browse_reference import register_pfc_browse_reference_tool
from .pfc_browse_python_api import register_pfc_browse_python_api_tool
from .pfc_capture_plot import register_pfc_capture_plot_tool

__all__ = [
    "register_pfc_task_tool",
    "register_pfc_task_status_tool",
    "register_pfc_list_tasks_tool",
    "register_pfc_interrupt_task_tool",
    "register_pfc_query_python_api_tool",
    "register_pfc_query_command_tool",
    "register_pfc_browse_commands_tool",
    "register_pfc_browse_reference_tool",
    "register_pfc_browse_python_api_tool",
    "register_pfc_capture_plot_tool",
]
