"""
Todo Write Tool - Create and update persistent todo items.

This tool implements the exact same interface as Claude Code's TodoWrite,
enabling cross-session task tracking and workflow planning.
"""

import logging
from typing import List, Dict, Any
from fastmcp import Context

from backend.infrastructure.mcp.utils.tool_result import ToolResult
from backend.infrastructure.storage.todo_storage import get_todo_storage
from backend.shared.utils.workspace import get_workspace_for_session_sync

logger = logging.getLogger(__name__)


async def todo_write(
    context: Context,
    todos: List[Dict[str, Any]]
) -> ToolResult:
    """
    Use this tool to create and manage a structured task list for your current coding session.

    This helps you track progress, organize complex tasks, and demonstrate thoroughness to the user.
    It also helps the user understand the progress of the task and overall progress of their requests.

    When to Use This Tool:
    - Complex multi-step tasks - When a task requires 3 or more distinct steps or actions
    - Non-trivial and complex tasks - Tasks that require careful planning or multiple operations
    - User explicitly requests todo list - When the user directly asks you to use the todo list
    - User provides multiple tasks - When users provide a list of things to be done
    - After receiving new instructions - Immediately capture user requirements as todos
    - When you start working on a task - Mark it as in_progress BEFORE beginning work
    - After completing a task - Mark it as completed and add any new follow-up tasks

    When NOT to Use This Tool:
    - Single, straightforward task
    - Trivial tasks that tracking provides no organizational benefit
    - Tasks that can be completed in less than 3 trivial steps
    - Purely conversational or informational tasks

    Args:
        context: MCP context containing session_id
        todos: The updated todo list. Each todo must have:
            - content (str): The imperative form describing what needs to be done
              (e.g., "Run tests", "Build the project")
            - status (str): "pending" | "in_progress" | "completed"
            - activeForm (str): The present continuous form shown during execution
              (e.g., "Running tests", "Building the project")

    Returns:
        ToolResult with status and summary

    Task Management Guidelines:
    - Update task status in real-time as you work
    - Mark tasks complete IMMEDIATELY after finishing (don't batch completions)
    - Exactly ONE task must be in_progress at any time (not less, not more)
    - Complete current tasks before starting new ones
    - Remove tasks that are no longer relevant from the list entirely

    Task Completion Requirements:
    - ONLY mark a task as completed when you have FULLY accomplished it
    - If you encounter errors, blockers, or cannot finish, keep the task as in_progress
    - When blocked, create a new task describing what needs to be resolved
    - Never mark a task as completed if:
      * Tests are failing
      * Implementation is partial
      * You encountered unresolved errors
      * You couldn't find necessary files or dependencies

    Examples:
        >>> # Planning a complex feature implementation
        >>> await todo_write(context, [
        ...     {
        ...         "content": "Implement user authentication",
        ...         "status": "in_progress",
        ...         "activeForm": "Implementing user authentication"
        ...     },
        ...     {
        ...         "content": "Write unit tests",
        ...         "status": "pending",
        ...         "activeForm": "Writing unit tests"
        ...     }
        ... ])

        >>> # Updating progress after completing a task
        >>> await todo_write(context, [
        ...     {
        ...         "content": "Implement user authentication",
        ...         "status": "completed",
        ...         "activeForm": "Implementing user authentication"
        ...     },
        ...     {
        ...         "content": "Write unit tests",
        ...         "status": "in_progress",
        ...         "activeForm": "Writing unit tests"
        ...     }
        ... ])
    """
    try:
        # Extract session ID from context (client_id is the session ID in MCP)
        session_id = context.client_id
        if not session_id:
            return ToolResult(
                status="error",
                message="Session ID not found in context",
                llm_content=None,
                data=None
            )

        # Get workspace directory for this session
        workspace = get_workspace_for_session_sync(session_id)

        # Validate todos format (exact same validation as Claude Code)
        for i, todo in enumerate(todos):
            if "content" not in todo:
                return ToolResult(
                    status="error",
                    message=f"Todo at index {i} missing required field 'content'",
                    llm_content=None,
                    data=None
                )
            if "activeForm" not in todo:
                return ToolResult(
                    status="error",
                    message=f"Todo at index {i} missing required field 'activeForm'",
                    llm_content=None,
                    data=None
                )
            if "status" not in todo:
                return ToolResult(
                    status="error",
                    message=f"Todo at index {i} missing required field 'status'",
                    llm_content=None,
                    data=None
                )
            if todo["status"] not in ["pending", "in_progress", "completed"]:
                return ToolResult(
                    status="error",
                    message=f"Todo at index {i} has invalid status '{todo['status']}' (must be pending/in_progress/completed)",
                    llm_content=None,
                    data=None
                )

        # Save todos (full replacement pattern - same as Claude Code)
        storage = get_todo_storage()
        storage.save_todos(workspace, session_id, todos)

        # Build summary
        status_counts = {}
        for todo in todos:
            status = todo["status"]
            status_counts[status] = status_counts.get(status, 0) + 1

        summary_parts = []
        if status_counts.get("pending", 0) > 0:
            summary_parts.append(f"{status_counts['pending']} pending")
        if status_counts.get("in_progress", 0) > 0:
            summary_parts.append(f"{status_counts['in_progress']} in progress")
        if status_counts.get("completed", 0) > 0:
            summary_parts.append(f"{status_counts['completed']} completed")

        summary = ", ".join(summary_parts) if summary_parts else "no todos"

        return ToolResult(
            status="success",
            message=f"Todos have been modified successfully. Ensure that you continue to use the todo list to track your progress. Please proceed with the current tasks if applicable",
            llm_content=f"Todo list updated successfully. Current status: {summary}.",
            data={
                "todo_count": len(todos),
                "session_id": session_id,
                "status_breakdown": status_counts,
                "workspace": str(workspace)
            }
        )

    except Exception as e:
        logger.error(f"Failed to save todos: {e}", exc_info=True)
        return ToolResult(
            status="error",
            message=f"Failed to save todos: {str(e)}",
            llm_content=None,
            data=None
        )
