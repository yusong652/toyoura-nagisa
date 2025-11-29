"""
PFC Task Status Tool - MCP tool for checking individual task status.

Provides real-time status monitoring and output retrieval for long-running PFC tasks.
"""

import asyncio
from fastmcp import FastMCP
from fastmcp.server.context import Context
from typing import Dict, Any, Optional
from pydantic import Field
from backend.infrastructure.pfc import get_client
from backend.infrastructure.mcp.utils.tool_result import success_response, error_response
from backend.infrastructure.mcp.utils.pagination import format_paginated_output
from backend.infrastructure.mcp.utils.time_utils import format_time_range


def register_pfc_task_status_tool(mcp: FastMCP):
    """
    Register PFC task status tool with the MCP server.

    Args:
        mcp: FastMCP server instance
    """

    @mcp.tool(
        tags={"pfc", "task", "status", "monitoring"},
        annotations={"category": "pfc", "tags": ["pfc", "task", "monitoring"]}
    )
    async def pfc_check_task_status(
        context: Context,
        task_id: str = Field(
            ...,
            description="Task ID from pfc_execute_task (e.g., 'a1b2c3d4')"
        ),
        offset: int = Field(
            0,
            ge=0,
            description="Skip N newest lines (0=most recent, 10=skip 10 newest)"
        ),
        limit: int = Field(
            10,
            ge=1,
            le=100,
            description="Lines to display (default: 10, max: 100)"
        ),
        filter: Optional[str] = Field(
            None,
            description="Optional text filter - only show lines containing this text (case-sensitive)"
        ),
        wait_seconds: float = Field(
            1,
            ge=1,
            le=3600,
            description="Wait N seconds before checking status (0-3600s). Use to avoid frequent polling. Example: wait_seconds=30 for long simulations"
        )
    ) -> Dict[str, Any]:
        """
        Check script status and retrieve output - works for both running and completed tasks.

        Monitor live progress with real-time print() output, or retrieve full output
        from scripts executed earlier (even after running other tasks).

        Pagination helps manage long outputs efficiently. All scripts (foreground/background)
        are tracked and persisted. Use pfc_list_tasks to find task IDs.

        Optional filtering allows focusing on specific output (e.g., errors, warnings).

        Rate limiting: Use wait_seconds to avoid frequent polling (e.g., wait_seconds=30
        waits 30s before checking, useful for long simulations).
        """
        try:
            # Wait before checking (rate limiting for long-running tasks)
            if wait_seconds > 0:
                await asyncio.sleep(wait_seconds)

            # Get current session ID from context (for ownership marking)
            current_session_id = getattr(context, 'client_id', 'unknown')

            # Get WebSocket client (auto-connects if needed)
            client = await get_client()

            # Query task status
            result = await client.check_task_status(task_id)

            status = result.get("status")

            if status == "not_found":
                # Task not found - still a successful tool call
                return success_response(
                    message=f"Task not found: {task_id}",
                    llm_content={
                        "parts": [{
                            "type": "text",
                            "text": (
                                f"**WARNING**: Task not found: {task_id}\n\n"
                                "The task may have expired or the task ID is invalid."
                            )
                        }]
                    },
                    task_id=task_id,
                    task_status="not_found"
                )

            elif status == "running":
                # Task still running
                data = result.get("data", {})
                elapsed_time = data.get("elapsed_time", 0)
                output = data.get("output", "")
                description = data.get("description", "")
                entry_script = data.get("entry_script", data.get("script_path", "unknown"))
                start_time = data.get("start_time")
                exec_commit = data.get("exec_commit")
                task_session_id = data.get("session_id", "unknown")

                # Format paginated output
                output_text, pagination = format_paginated_output(output, offset, limit, filter)

                # Build navigation hints
                nav_hints = []
                if pagination["has_later"]:
                    nav_hints.append(f"newer: offset={max(0, offset - limit)}")
                if pagination["has_earlier"]:
                    nav_hints.append(f"older: offset={offset + limit}")
                nav_hint = " | ".join(nav_hints) if nav_hints else "all output shown"

                # Format time info (start time only for running tasks)
                time_info = format_time_range(start_time)

                # Build session marker (same pattern as pfc_list_tasks)
                if task_session_id == current_session_id:
                    session_marker = " [Your task]"
                else:
                    task_session_id_display = task_session_id[:8] if task_session_id != 'unknown' else 'unknown'
                    session_marker = f" [Session: {task_session_id_display}]"

                # Build version info
                version_marker = f" | Commit: {exec_commit[:8]}" if exec_commit else ""

                # Build filter info
                filter_info = f" | Filter: '{filter}'" if filter else ""

                # Build LLM-friendly text with three-line format
                llm_text = (
                    f"**STATUS**: Running | Task ID: {task_id} | {time_info}{version_marker}{session_marker}\n"
                    f"  Entry: {entry_script}\n"
                    f"  → {description}\n\n"
                    f"Output: {pagination['total_lines']} lines{' (filtered)' if filter else ' total'}{filter_info} | "
                    f"Showing: lines {pagination['line_range']} "
                    f"({'most recent' if offset == 0 else f'offset {offset}'})\n\n"
                    f"━━━ Output ━━━\n"
                    f"{output_text}\n"
                    f"━━━━━━━━━━━━━━\n"
                    f"**NEXT**: {nav_hint}"
                )

                return success_response(
                    message=result.get("message", f"Task running: {task_id}"),
                    llm_content={
                        "parts": [{
                            "type": "text",
                            "text": llm_text
                        }]
                    },
                    task_id=task_id,
                    task_status="running",
                    task_data=data,
                    pagination=pagination
                )

            elif status == "success":
                # Task completed successfully
                data = result.get("data", {})
                elapsed_time = data.get("elapsed_time", 0)
                output = data.get("output", "")
                task_result = data.get("result")
                description = data.get("description", "")
                entry_script = data.get("entry_script", data.get("script_path", "unknown"))
                start_time = data.get("start_time")
                end_time = data.get("end_time")
                exec_commit = data.get("exec_commit")
                task_session_id = data.get("session_id", "unknown")

                # Format paginated output
                output_text, pagination = format_paginated_output(output, offset, limit, filter)

                # Build navigation hints
                nav_hints = []
                if pagination["has_later"]:
                    nav_hints.append(f"newer: offset={max(0, offset - limit)}")
                if pagination["has_earlier"]:
                    nav_hints.append(f"older: offset={offset + limit}")
                nav_hint = " | ".join(nav_hints) if nav_hints else "all output shown"

                # Format time info (start to end time range)
                time_info = format_time_range(start_time, end_time)

                # Build session marker (same pattern as pfc_list_tasks)
                if task_session_id == current_session_id:
                    session_marker = " [Your task]"
                else:
                    task_session_id_display = task_session_id[:8] if task_session_id != 'unknown' else 'unknown'
                    session_marker = f" [Session: {task_session_id_display}]"

                # Build version info
                version_marker = f" | Commit: {exec_commit[:8]}" if exec_commit else ""

                # Build filter info
                filter_info = f" | Filter: '{filter}'" if filter else ""

                # Build LLM-friendly text with three-line format
                llm_text = (
                    f"**STATUS**: Completed | Task ID: {task_id} | {time_info}{version_marker}{session_marker}\n"
                    f"  Entry: {entry_script}\n"
                    f"  → {description}\n\n"
                    f"Result: {task_result}\n"
                    f"Output: {pagination['total_lines']} lines{' (filtered)' if filter else ' total'}{filter_info} | "
                    f"Showing: lines {pagination['line_range']} "
                    f"({'most recent' if offset == 0 else f'offset {offset}'})\n\n"
                    f"━━━ Output ━━━\n"
                    f"{output_text}\n"
                    f"━━━━━━━━━━━━━━\n"
                    f"**NEXT**: {nav_hint}"
                )

                return success_response(
                    message=result.get("message", f"Task completed: {task_id}"),
                    llm_content={
                        "parts": [{
                            "type": "text",
                            "text": llm_text
                        }]
                    },
                    task_id=task_id,
                    task_status="success",
                    task_data=data,
                    pagination=pagination
                )

            elif status == "error":
                # Task failed with error
                data = result.get("data", {})
                elapsed_time = data.get("elapsed_time", 0)
                output = data.get("output", "")
                error_msg = data.get("error", "Unknown error")
                description = data.get("description", "")
                entry_script = data.get("entry_script", data.get("script_path", "unknown"))
                start_time = data.get("start_time")
                end_time = data.get("end_time")
                exec_commit = data.get("exec_commit")
                task_session_id = data.get("session_id", "unknown")

                # Format paginated output
                output_text, pagination = format_paginated_output(output, offset, limit, filter)

                # Build navigation hints
                nav_hints = []
                if pagination["has_later"]:
                    nav_hints.append(f"newer: offset={max(0, offset - limit)}")
                if pagination["has_earlier"]:
                    nav_hints.append(f"older: offset={offset + limit}")
                nav_hint = " | ".join(nav_hints) if nav_hints else "all output shown"

                # Format time info (start to end time range)
                time_info = format_time_range(start_time, end_time)

                # Build session marker (same pattern as pfc_list_tasks)
                if task_session_id == current_session_id:
                    session_marker = " [Your task]"
                else:
                    task_session_id_display = task_session_id[:8] if task_session_id != 'unknown' else 'unknown'
                    session_marker = f" [Session: {task_session_id_display}]"

                # Build version info
                version_marker = f" | Commit: {exec_commit[:8]}" if exec_commit else ""

                # Build filter info
                filter_info = f" | Filter: '{filter}'" if filter else ""

                # Build LLM-friendly text with three-line format
                llm_text = (
                    f"**STATUS**: Failed | Task ID: {task_id} | {time_info}{version_marker}{session_marker}\n"
                    f"  Entry: {entry_script}\n"
                    f"  → {description}\n\n"
                    f"Error: {error_msg}\n"
                    f"Output: {pagination['total_lines']} lines{' (filtered)' if filter else ' total'}{filter_info} | "
                    f"Showing: lines {pagination['line_range']} "
                    f"({'most recent' if offset == 0 else f'offset {offset}'})\n\n"
                    f"━━━ Output before error ━━━\n"
                    f"{output_text}\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"**NEXT**: {nav_hint}"
                )

                return success_response(
                    message=result.get("message", f"Task failed: {task_id}"),
                    llm_content={
                        "parts": [{
                            "type": "text",
                            "text": llm_text
                        }]
                    },
                    task_id=task_id,
                    task_status="error",
                    task_data=data,
                    pagination=pagination
                )

            else:
                # Unknown status
                return success_response(
                    message=f"Unknown task status: {status}",
                    llm_content={
                        "parts": [{
                            "type": "text",
                            "text": f"**WARNING**: Unknown task status: {status}"
                        }]
                    },
                    task_id=task_id,
                    task_status=status
                )

        except ConnectionError as e:
            return error_response(f"Cannot connect to PFC server: {str(e)}")

        except Exception as e:
            return error_response(f"System error querying task status: {str(e)}")

    print(f"[DEBUG] Registered PFC task status tool: pfc_check_task_status")
