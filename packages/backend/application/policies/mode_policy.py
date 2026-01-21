"""
Session mode policy for tool execution.

Defines read-only tool gating rules for plan mode, including safe shell
command detection. This module is used by ToolExecutor to prevent edits
when the session is in plan mode.
"""

from __future__ import annotations

import shlex
from typing import Any, Dict, Set


READ_ONLY_TOOLS: Set[str] = {
    "read",
    "glob",
    "grep",
    "list",
    "bash_output",
    "web_fetch",
    "web_search",
    "todo_write",
    "pfc_browse_commands",
    "pfc_browse_python_api",
    "pfc_browse_reference",
    "pfc_query_python_api",
    "pfc_query_command",
    "pfc_check_task_status",
    "pfc_list_tasks",
    "pfc_capture_plot",
    "trigger_skill",
    "invoke_agent",  # SubAgents (pfc_explorer, pfc_diagnostic) are read-only
}

READ_ONLY_BASH_COMMANDS: Set[str] = {
    "ls",
    "pwd",
    "whoami",
    "date",
    "cat",
    "grep",
    "head",
    "tail",
    "wc",
    "file",
    "stat",
    "rg",
}

READ_ONLY_GIT_SUBCOMMANDS: Set[str] = {
    "status",
    "diff",
    "log",
    "show",
    "rev-parse",
    "branch",
    "remote",
    "describe",
    "ls-files",
}

BLOCKED_COMMAND_TOKENS = ("&&", ";", "|", ">", "<", "\n")


def is_bash_command_read_only(command: str) -> bool:
    """Return True if a bash command is safe for plan mode."""
    if not command:
        return False

    command = command.strip()
    if not command:
        return False

    if any(token in command for token in BLOCKED_COMMAND_TOKENS):
        return False

    try:
        parts = shlex.split(command)
    except ValueError:
        return False

    if not parts:
        return False

    root = parts[0]
    if root in READ_ONLY_BASH_COMMANDS:
        return True

    if root == "git":
        if len(parts) < 2:
            return False
        return parts[1] in READ_ONLY_GIT_SUBCOMMANDS

    return False


def is_read_only_tool(tool_name: str, tool_args: Dict[str, Any]) -> bool:
    """Return True if a tool call is considered read-only."""
    if tool_name == "bash":
        return is_bash_command_read_only(str(tool_args.get("command", "")))

    return tool_name in READ_ONLY_TOOLS


def is_tool_allowed_in_mode(mode: str, tool_name: str, tool_args: Dict[str, Any]) -> bool:
    """Return True if a tool is allowed in the given session mode."""
    normalized_mode = (mode or "build").lower()
    if normalized_mode != "plan":
        return True

    return is_read_only_tool(tool_name, tool_args)


def build_mode_blocked_message(mode: str, tool_name: str) -> str:
    """Build a user-facing error message for blocked tools."""
    normalized_mode = (mode or "build").upper()
    return (
        f"Tool '{tool_name}' is disabled while session is in {normalized_mode} mode. "
        "Switch to BUILD mode to execute write or execution tools."
    )
