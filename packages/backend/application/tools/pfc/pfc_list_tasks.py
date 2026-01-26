"""
PFC List Tasks Tool - MCP tool for listing all tracked tasks.

Provides task overview functionality for managing multiple concurrent PFC simulations.
"""

from backend.application.tools.registrar import ToolRegistrar
from fastmcp.server.context import Context
from typing import Annotated, Dict, Any, Optional
from pydantic import Field
from backend.infrastructure.pfc import get_pfc_client
from backend.shared.utils.tool_result import success_response, error_response
from backend.shared.utils.time_utils import format_time_range
from .utils import OutputOffset, TaskListLimit


def register_pfc_list_tasks_tool(registrar: ToolRegistrar):
    """
    Register PFC list tasks tool with the registrar.

    Args:
        registrar: Tool registrar instance
    """

    @registrar.tool(
        tags={"pfc", "task", "list", "monitoring"},
        annotations={"category": "pfc", "tags": ["pfc", "task", "monitoring"]}
    )
    async def pfc_list_tasks(
        context: Context,
        session_id: Annotated[Optional[str], Field(
            default=None,
            description="Filter by session ID (None = all sessions)"
        )] = None,
        offset: OutputOffset = 0,
        limit: TaskListLimit = 32,
    ) -> Dict[str, Any]:
        """
        List tracked PFC tasks with pagination support.

        Returns overview of script tasks (running, completed, failed) tracked by PFC server.
        Supports filtering by session and pagination for large task histories.

        Pagination pattern (same as pfc_check_task_status):
        - offset=0, limit=32: Most recent 32 tasks
        - offset=32, limit=32: Next 32 tasks (older)

        Note:
            - Shows tasks submitted via pfc_execute_task
            - Tasks sorted by start time (newest first)
            - Tasks persisted across server restarts (historical tasks marked [Historical])
            - Use pfc_check_task_status for detailed output of specific scripts
        """
        try:
            # Get caller's session ID from context (truncate to 8 chars for display)
            # Architecture guarantee: tool_manager.py always injects _meta.client_id
            caller_session_id = context.client_id
            caller_session_id_display = caller_session_id[:8] if caller_session_id else 'unknown'

            # Get WebSocket client (auto-connects if needed)
            client = await get_pfc_client()

            # Query task list with pagination
            result = await client.list_tasks(
                session_id=session_id,
                offset=offset,
                limit=limit
            )

            data = result.get("data", [])
            pagination = result.get("pagination", {})
            total_count = pagination.get("total_count", len(data))
            displayed_count = pagination.get("displayed_count", len(data))
            has_more = pagination.get("has_more", False)

            # Format task summary for LLM
            if total_count == 0:
                task_summary = "No tasks currently tracked."
            elif displayed_count == 0:
                task_summary = f"No tasks at offset {offset}. Total tasks available: {total_count}."
            else:
                task_lines = []
                for task in data:
                    task_id = task.get("task_id", "unknown")
                    task_session_id = task.get("session_id", "unknown")
                    entry_script = task.get("entry_script", task.get("script_path", task.get("name", "unknown")))
                    description = task.get("description", "")
                    status = task.get("status", "unknown")
                    elapsed = task.get("elapsed_time", 0)
                    start_time = task.get("start_time")
                    end_time = task.get("end_time")
                    git_commit = task.get("git_commit")
                    is_historical = task.get("historical", False)

                    status_text = {
                        "pending": "Pending",
                        "running": "Running",
                        "completed": "Completed",
                        "failed": "Failed",
                        "interrupted": "Interrupted"
                    }.get(status, "Unknown")

                    # Mark task ownership: only show session_id for non-current sessions
                    if task_session_id == caller_session_id:
                        session_marker = " [Your task]"
                    else:
                        # Show session_id for other sessions (truncated to 8 chars)
                        task_session_id_display = task_session_id[:8] if task_session_id != 'unknown' else 'unknown'
                        session_marker = f" [Session: {task_session_id_display}]"

                    historical_marker = " [Historical]" if is_historical else ""

                    # Version info (git_commit)
                    version_marker = f" | git_commit: {git_commit[:8]}" if git_commit else ""

                    # Format time info with date
                    time_info = format_time_range(start_time, end_time)

                    # Build task entry
                    task_entry = (
                        f"[{status_text}] task_id: {task_id} | {elapsed:.1f}s | {time_info}{version_marker}{session_marker}{historical_marker}\n"
                        f"  Entry: {entry_script}\n"
                        f"  → {description}"
                    )

                    # Add error summary for failed tasks (first line only)
                    error = task.get("error")
                    if status == "failed" and error:
                        # Extract first line of error for summary
                        error_first_line = error.split('\n')[0][:80]
                        if len(error.split('\n')[0]) > 80:
                            error_first_line += "..."
                        task_entry += f"\n  ⚠ {error_first_line}"

                    task_lines.append(task_entry)

                # Build navigation hints
                nav_hints = []
                if offset > 0:
                    nav_hints.append(f"newer: offset={max(0, offset - (limit or 20))}")
                if has_more:
                    nav_hints.append(f"older: offset={offset + displayed_count}")
                nav_hint = " | ".join(nav_hints) if nav_hints else "all tasks shown"

                # Build session filter info (truncate session_id to 8 chars)
                if session_id:
                    session_id_display = session_id[:8] if len(session_id) >= 8 else session_id
                    filter_info = f"**FILTER**: session {session_id_display}"
                else:
                    filter_info = "**FILTER**: None (all sessions)"

                task_summary = (
                    f"Tasks: {total_count} total | Showing: {displayed_count} ({'most recent' if offset == 0 else f'offset {offset}'})\n"
                    f"{filter_info}\n"
                    f"Your session: {caller_session_id_display}\n\n" +
                    "\n\n".join(task_lines) +
                    f"\n\n**NEXT**: {nav_hint}"
                )

            return success_response(
                message=result.get("message", f"Listed {displayed_count} of {total_count} tasks"),
                llm_content={
                    "parts": [{
                        "type": "text",
                        "text": task_summary
                    }]
                },
                total_count=total_count,
                displayed_count=displayed_count,
                caller_session_id=caller_session_id,
                tasks=data,
                pagination=pagination
            )

        except ConnectionError as e:
            return error_response(f"Cannot connect to PFC server: {str(e)}")

        except Exception as e:
            return error_response(f"System error listing tasks: {str(e)}")
