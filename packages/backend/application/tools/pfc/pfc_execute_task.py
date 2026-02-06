"""
PFC Task Execution Tool - MCP tool for executing PFC simulation tasks.

Provides task execution functionality for PFC Python SDK operations.
Each execution creates a versioned snapshot on the pfc-executions branch
for complete traceability ("Script is Context" philosophy).

Task lifecycle is managed by backend's PfcTaskManager:
- Task ID generated before sending to pfc-server
- Foreground mode supports ctrl+b to move task to background
- Status tracked via polling pfc-server (persistent data)
"""

from backend.application.tools.registrar import ToolRegistrar
from backend.application.tools.context import ToolContext
# from fastmcp.server.context import Context
from typing import Dict, Any, cast, Optional
from backend.infrastructure.pfc import get_pfc_client
from backend.infrastructure.pfc.task_manager import get_pfc_task_manager
from backend.infrastructure.pfc.foreground_handle import (
    PfcForegroundExecutionHandle,
    PfcMoveToBackgroundRequest,
    PfcForegroundExecutionResult,
)
from backend.infrastructure.pfc.foreground_registry import get_pfc_foreground_registry
from backend.shared.utils.tool_result import success_response, error_response
from backend.shared.utils.path_normalization import normalize_path_separators
from .utils import (
    create_task_status_data,
    format_task_status_for_llm,
    TaskStatusData,
    DEFAULT_OUTPUT_LINES,
    ScriptPath,
    TaskDescription,
    TimeoutMs,
    RunInBackground,
)


def register_pfc_task_tool(registrar: ToolRegistrar):
    """
    Register PFC task execution tool with the registrar.

    Args:
        registrar: Tool registrar instance
    """

    @registrar.tool(
        tags={"pfc", "simulation", "python", "task", "sdk"},
        annotations={"category": "pfc", "tags": ["pfc", "simulation", "python", "sdk"]}
    )
    async def pfc_execute_task(
        context: ToolContext,
        entry_script: ScriptPath,
        description: TaskDescription,
        timeout: TimeoutMs = None,
        run_in_background: RunInBackground = True,
    ) -> Dict[str, Any]:
        """
        Execute a PFC simulation task.

        Returns task_id for tracking. Scripts can print progress during execution,
        monitor real-time output via pfc_check_task_status(task_id).

        Note: Query pfc_query_command for command syntax before writing scripts.
        """
        try:
            # Get session ID from MCP context for task isolation
            # Architecture guarantee: tool_manager.py always injects _meta.client_id
            session_id = cast(str, context.session_id)

            # Parameters are pre-validated by Pydantic Annotated types
            # Normalize path separators for cross-platform compatibility
            script_path = normalize_path_separators(entry_script, target_platform='linux')

            # Get task manager and create task (generates task_id)
            task_manager = get_pfc_task_manager()
            task_id = task_manager.create_task(
                session_id=session_id,
                script_path=script_path,
                description=description,
                source="agent",
            )

            # Update status to submitted
            task_manager.update_status(task_id, "submitted")

            # Get WebSocket client (auto-connects if needed)
            client = await get_pfc_client()

            # Always submit to pfc-server with run_in_background=True
            # For foreground mode, we poll for completion on backend side
            result = await client.execute_task(
                script_path=script_path,
                description=description,
                task_id=task_id,
                timeout_ms=timeout,
                run_in_background=True,  # Always background on server side
                session_id=session_id
            )

            # Validate server accepted the task
            status = result.get("status")
            data = result.get("data")
            server_message = result.get("message", "")

            if status != "pending":
                # Pass through server's error message (e.g., "Script file not found: ...")
                error_detail = server_message or f"Server returned status={status}"
                task_manager.update_status(task_id, "failed", error=error_detail)
                return error_response(error_detail)

            # Update task manager with initial response
            git_commit = data.get("git_commit") if data else None
            task_manager.update_status(task_id, "running")
            task = task_manager.get_task(task_id)
            if task and git_commit:
                task.git_commit = git_commit

            # Get notification service for frontend updates
            from backend.application.notifications.pfc_task_notification_service import (
                get_pfc_task_notification_service
            )
            notification_service = get_pfc_task_notification_service()

            # ===== Background Mode: Return immediately and start polling =====
            if run_in_background:
                # Start background polling for frontend notifications
                if notification_service:
                    await notification_service.start_polling(session_id)

                task_data = TaskStatusData(
                    task_id=task_id,
                    status="submitted",
                    description=description,
                    entry_script=script_path,
                    git_commit=git_commit,
                )

                formatted = format_task_status_for_llm(
                    data=task_data,
                    skip_newest=0,
                    limit=DEFAULT_OUTPUT_LINES,
                )

                return success_response(
                    message=f"Task submitted: {script_path}",
                    llm_content={"parts": [{"type": "text", "text": formatted.text}]},
                    entry_script=script_path,
                    task_id=task_id,
                    git_commit=git_commit,
                    pagination=formatted.pagination,
                )

            # ===== Foreground Mode: Wait with ctrl+b support =====
            # Uses unified polling service for both frontend notifications and handle signaling
            registry = get_pfc_foreground_registry()

            # Create foreground handle (no polling - waits for signals from notification service)
            timeout_seconds = timeout / 1000.0 if timeout else None
            handle = PfcForegroundExecutionHandle(
                task_id=task_id,
                timeout_seconds=timeout_seconds,
            )

            # Register handle for ctrl+b signal handling
            registry.register(session_id, handle)

            # Register handle with notification service for completion signaling
            # Foreground mode: NO frontend notifications (like bash)
            # - Polling only signals foreground handle, doesn't notify frontend
            # - Frontend notifications start only after ctrl+b (backgrounded)
            if notification_service:
                notification_service.register_foreground_handle(
                    task_id=task_id,
                    session_id=session_id,
                    script_path=script_path,
                    description=description,
                    git_commit=git_commit,
                    handle=handle,
                )
                # Start polling (for foreground handle signaling only, no frontend updates)
                await notification_service.start_polling(session_id)

            try:
                wait_result = await handle.wait()
            finally:
                registry.unregister(session_id)
                if notification_service:
                    notification_service.unregister_foreground_handle(task_id)

            # ===== Handle Move-to-Background Request (ctrl+b or timeout) =====
            if isinstance(wait_result, PfcMoveToBackgroundRequest):
                # Send backgrounded notification (polling continues for frontend updates)
                if notification_service:
                    await notification_service.notify_foreground_backgrounded(
                        session_id=session_id,
                        task_id=task_id,
                        script_path=script_path,
                        reason=wait_result.reason,
                        elapsed_seconds=handle._elapsed_seconds,
                        description=description,
                        git_commit=git_commit,
                    )
                    # Note: polling already running, will continue for frontend updates

                # Build LLM content based on reason (similar to bash tool)
                if wait_result.reason == "user_request":
                    llm_text = (
                        f"Task was manually backgrounded by user with ID: {task_id}. "
                        f"Use pfc_check_task_status('{task_id}') to check output."
                    )
                else:
                    llm_text = (
                        f"Task timed out and continues in background with ID: {task_id}. "
                        f"Use pfc_check_task_status('{task_id}') to check output."
                    )

                return success_response(
                    message=llm_text,
                    llm_content={"parts": [{"type": "text", "text": llm_text}]},
                    entry_script=script_path,
                    task_id=task_id,
                    git_commit=git_commit,
                    backgrounded=True,
                    background_reason=wait_result.reason,
                )

            # ===== Handle Normal Completion =====
            # (Frontend notification already sent by unified polling service)
            exec_result: PfcForegroundExecutionResult = wait_result

            # Update local task manager with final state
            task_manager.update_status(
                task_id,
                exec_result.status,
                result=exec_result.result,
                error=exec_result.error,
            )
            if exec_result.output:
                task_manager.set_output(task_id, exec_result.output)

            # Build response
            task_data = TaskStatusData(
                task_id=task_id,
                status=exec_result.status,
                description=description,
                entry_script=script_path,
                git_commit=exec_result.git_commit or git_commit,
                output=exec_result.output,
                result=exec_result.result,
                error=exec_result.error,
                start_time=exec_result.start_time,
                end_time=exec_result.end_time,
                elapsed_time=exec_result.elapsed_seconds,
            )

            formatted = format_task_status_for_llm(
                data=task_data,
                skip_newest=0,
                limit=DEFAULT_OUTPUT_LINES,
            )

            response_kwargs: Dict[str, Any] = {
                "message": f"Task {exec_result.status}: {script_path}",
                "llm_content": {"parts": [{"type": "text", "text": formatted.text}]},
                "entry_script": script_path,
                "task_id": task_id,
                "git_commit": task_data.git_commit,
                "pagination": formatted.pagination,
            }

            if exec_result.status == "completed":
                response_kwargs["script_result"] = exec_result.result
            elif exec_result.status == "failed":
                response_kwargs["script_error"] = exec_result.error

            return success_response(**response_kwargs)

        except ConnectionError as e:
            # Update task status on connection failure
            if 'task_id' in locals():
                task_manager.update_status(task_id, "failed", error=str(e))
            return error_response(f"Cannot connect to PFC server: {str(e)}")

        except Exception as e:
            # Update task status on unexpected error
            if 'task_id' in locals():
                task_manager.update_status(task_id, "failed", error=str(e))
            return error_response(f"System error executing task: {str(e)}")
