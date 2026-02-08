"""
Tool Executor - Handles tool classification, execution, and cascade blocking.

Extracted tool execution logic for better modularity.
Used by Agent for tool execution during conversation turns.
Designed to support future subagent extensions.

Confirmation outcomes:
- approve: Execute the tool
- reject: Stop execution, user wants to provide input via main input
- reject_and_tell: Don't execute but continue with user's instruction injected
"""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional, Sequence, Tuple

from backend.application.tools.runtime.confirmation_strategy import ConfirmationStrategy
from backend.application.tools.runtime.notification import ToolNotificationService
from backend.application.tools.runtime.persistence import ToolResultPersistence


# Rejection outcome types (subset of ConfirmationOutcome, excluding "approve")
RejectionOutcome = Literal["reject", "reject_and_tell"]


@dataclass
class ToolExecutionResult:
    """Result of tool execution batch."""

    results: List[Dict[str, Any]]  # Results indexed by original order
    rejected_tools: List[str]  # Names of rejected tools
    user_rejected: bool  # Whether any tool was user-rejected (reject or reject_and_tell)
    rejection_outcome: Optional[RejectionOutcome] = None  # The type of rejection
    rejection_message: Optional[str] = None  # User's message for rejection


@dataclass
class ClassifiedTools:
    """Tools classified by confirmation requirement."""

    non_confirm: List[Tuple[int, Dict]] = field(default_factory=list)  # (index, tool_call)
    confirm: List[Tuple[int, Dict]] = field(default_factory=list)  # (index, tool_call)


@dataclass
class PfcExecuteTaskHookState:
    """State carried across pfc_execute_task pre/post hooks."""

    local_task_id: str
    entry_script: str
    description: str
    git_commit: Optional[str] = None


class ToolExecutor:
    """
    Executes tools with classification and cascade blocking.

    Responsibilities:
    - Classify tools by confirmation requirement
    - Execute non-confirmation tools in parallel (conceptually)
    - Execute confirmation tools serially with cascade blocking
    - Delegate notifications to ToolNotificationService
    - Delegate persistence to ToolResultPersistence
    """

    def __init__(
        self,
        tool_manager: Any,
        session_id: str,
        notification_session_id: Optional[str] = None,
        send_tool_result_notifications: bool = True,
        notification_service: ToolNotificationService | None = None,
        result_persistence: ToolResultPersistence | None = None,
    ):
        """
        Initialize ToolExecutor.

        Args:
            tool_manager: ToolManager for tool execution
            session_id: Session ID for context and tool execution
            notification_session_id: Session ID for WebSocket notifications and confirmations.
                                    If None, uses session_id. This allows SubAgents to route
                                    confirmation requests to MainAgent's WebSocket connection.
            send_tool_result_notifications: Whether to send TOOL_RESULT_UPDATE notifications.
                                           Set to False for SubAgents to avoid polluting
                                           MainAgent's message stream with internal tool results.
            notification_service: Optional ToolNotificationService override.
            result_persistence: Optional ToolResultPersistence override.
        """
        self.tool_manager = tool_manager
        self.session_id = session_id
        self.notification_session_id = notification_session_id or session_id
        self.send_tool_result_notifications = send_tool_result_notifications
        self.confirmation_strategy = ConfirmationStrategy(tool_manager)
        self.notification_service = notification_service or ToolNotificationService(
            self.notification_session_id, send_tool_result_notifications
        )
        self.result_persistence = result_persistence or ToolResultPersistence(self.session_id)

    def classify_tools(self, tool_calls: List[Dict], tool_indices: Optional[List[int]] = None) -> ClassifiedTools:
        """
        Classify tools into confirm and non-confirm categories.

        Args:
            tool_calls: List of tool call dicts

        Returns:
            ClassifiedTools with separated lists
        """
        classified = ClassifiedTools()

        for i, tool_call in enumerate(tool_calls):
            original_index = tool_indices[i] if tool_indices else i
            tool_name = tool_call.get("name", "unknown")
            tool_args = tool_call.get("arguments", {})

            if self.confirmation_strategy.requires_confirmation(tool_name, tool_args):
                classified.confirm.append((original_index, tool_call))
            else:
                classified.non_confirm.append((original_index, tool_call))

        return classified

    async def execute_all(
        self, tool_calls: List[Dict], message_id: str, agent_profile="pfc_expert"
    ) -> ToolExecutionResult:
        """
        Execute all tool calls with proper ordering and cascade blocking.

        Args:
            tool_calls: List of tool call dicts
            message_id: Message ID containing tool calls
            agent_profile: Agent profile name for WebSocket notifications

        Returns:
            ToolExecutionResult with all results and rejection info

        Note:
            - reject: Cascade blocks remaining tools, agent should stop
            - reject_and_tell: Cascade blocks remaining tools, but agent continues with instruction
        """
        # Prepare results storage
        results: List[Dict[str, Any]] = [{} for _ in tool_calls]
        rejected_tools: List[str] = []
        rejection_outcome: Optional[RejectionOutcome] = None
        rejection_message: Optional[str] = None

        # Plan/build mode gate: block non-read-only tools in plan mode
        from backend.application.tools.policy import (
            is_tool_allowed_in_mode,
            build_mode_blocked_message,
        )
        from backend.shared.utils.tool_result import error_response
        from backend.infrastructure.storage.session_manager import get_session_mode

        session_mode = get_session_mode(self.session_id)
        allowed_calls: List[Dict] = []
        allowed_indices: List[int] = []

        for i, tool_call in enumerate(tool_calls):
            tool_name = tool_call.get("name", "unknown")
            tool_args = tool_call.get("arguments", {})

            if not is_tool_allowed_in_mode(session_mode, tool_name, tool_args):
                blocked_message = build_mode_blocked_message(session_mode, tool_name)
                result = error_response(
                    blocked_message,
                    blocked_by_mode=True,
                    session_mode=session_mode,
                )
                results[i] = result
                rejected_tools.append(tool_name)
                await self.notification_service.notify_result(tool_call, result, agent_profile)
                continue

            allowed_calls.append(tool_call)
            allowed_indices.append(i)

        # Classify allowed tools
        classified = self.classify_tools(allowed_calls, allowed_indices)

        # Execute non-confirmation tools first
        for original_index, tool_call in classified.non_confirm:
            result = await self._execute_single_tool(tool_call, message_id)
            results[original_index] = result
            await self.notification_service.notify_result(tool_call, result, agent_profile)

        # Execute confirmation tools serially with cascade blocking
        user_rejected = False
        rejected_tool_name: Optional[str] = None

        for original_index, tool_call in classified.confirm:
            tool_name = tool_call.get("name", "unknown")

            if user_rejected:
                # Cascade block
                result = self._create_cascade_blocked_result(tool_name, rejected_tool_name)
                rejected_tools.append(tool_name)
            else:
                # Request confirmation and execute
                result, outcome, user_message = await self._execute_with_confirmation(tool_call, message_id)
                if outcome in ("reject", "reject_and_tell"):
                    user_rejected = True
                    rejected_tool_name = tool_name
                    rejected_tools.append(tool_name)
                    rejection_outcome = outcome
                    rejection_message = user_message

            results[original_index] = result
            await self.notification_service.notify_result(tool_call, result, agent_profile)

        return ToolExecutionResult(
            results=results,
            rejected_tools=rejected_tools,
            user_rejected=user_rejected,
            rejection_outcome=rejection_outcome,
            rejection_message=rejection_message,
        )

    async def _execute_single_tool(self, tool_call: Dict, message_id: str) -> Dict[str, Any]:
        """Execute a single tool without confirmation."""
        tool_name = tool_call.get("name", "unknown")
        tool_args = tool_call.get("arguments", {})

        hook_state = await self._run_pre_tool_hook(tool_name, tool_args)
        result = await self.tool_manager.handle_function_call(tool_call, self.session_id, message_id)
        if result is None:
            from backend.shared.utils.tool_result import error_response

            return error_response("Tool execution returned no result")

        result = self._normalize_tool_result(result, tool_name)
        result = await self._run_post_tool_hook(tool_name, tool_args, result, hook_state)
        return self._normalize_tool_result(result, tool_name)

    async def _run_pre_tool_hook(self, tool_name: str, tool_args: Dict[str, Any]) -> Any:
        """Run tool-specific pre-execution hook."""
        try:
            if tool_name == "pfc_execute_task":
                return await self._pre_pfc_execute_task(tool_args)
        except Exception as exc:
            print(f"[ToolExecutor] Pre-hook failed for {tool_name}: {exc}")
        return None

    async def _run_post_tool_hook(
        self,
        tool_name: str,
        tool_args: Dict[str, Any],
        result: Dict[str, Any],
        hook_state: Any,
    ) -> Dict[str, Any]:
        """Run tool-specific post-execution hook."""
        try:
            if tool_name == "pfc_execute_task":
                return await self._post_pfc_execute_task(tool_args, result, hook_state)
        except Exception as exc:
            print(f"[ToolExecutor] Post-hook failed for {tool_name}: {exc}")
        return result

    async def _pre_pfc_execute_task(self, tool_args: Dict[str, Any]) -> Optional[PfcExecuteTaskHookState]:
        """Best-effort local tracking setup before MCP pfc_execute_task call."""
        from backend.infrastructure.pfc.git_version import get_git_manager
        from backend.infrastructure.pfc.task_manager import get_pfc_task_manager

        task_manager = get_pfc_task_manager()
        entry_script = str(tool_args.get("entry_script", "") or "")
        description = str(tool_args.get("description", "") or "")

        git_commit = None
        try:
            git_manager = get_git_manager(entry_script)
            if git_manager.is_git_available():
                git_commit = git_manager.create_execution_commit(
                    task_id="pre-submit",
                    description=description,
                    entry_script=entry_script,
                )
        except Exception as exc:
            print(f"[ToolExecutor] pfc_execute_task git snapshot skipped: {exc}")

        local_task_id = task_manager.create_task(
            session_id=self.session_id,
            script_path=entry_script,
            description=description,
            git_commit=git_commit,
            source="agent",
        )
        task_manager.update_status(local_task_id, "submitted")

        return PfcExecuteTaskHookState(
            local_task_id=local_task_id,
            entry_script=entry_script,
            description=description,
            git_commit=git_commit,
        )

    async def _post_pfc_execute_task(
        self,
        _tool_args: Dict[str, Any],
        result: Dict[str, Any],
        hook_state: Any,
    ) -> Dict[str, Any]:
        """Update local PFC task tracking after MCP pfc_execute_task call."""
        if not isinstance(hook_state, PfcExecuteTaskHookState):
            return result

        from backend.infrastructure.pfc.task_manager import get_pfc_task_manager

        task_manager = get_pfc_task_manager()
        local_task_id = hook_state.local_task_id

        if result.get("status") == "error":
            error_message = result.get("message") or "MCP pfc_execute_task failed"
            task_manager.update_status(local_task_id, "failed", error=error_message)
        else:
            bridge_task_id = self._extract_bridge_task_id(result)
            task_manager.update_status(local_task_id, "running", bridge_task_id=bridge_task_id)

        return self._enrich_pfc_result_data(result, hook_state)

    def _normalize_tool_result(self, result: Dict[str, Any], tool_name: str) -> Dict[str, Any]:
        """Ensure tool result always contains llm_content.parts."""
        if not isinstance(result, dict):
            return {
                "status": "error",
                "message": f"Tool '{tool_name}' returned invalid result type",
                "llm_content": {
                    "parts": [{"type": "text", "text": f"Tool '{tool_name}' returned invalid result type"}]
                },
            }

        llm_content = result.get("llm_content")
        if isinstance(llm_content, str):
            normalized = result.copy()
            normalized["llm_content"] = {"parts": [{"type": "text", "text": llm_content}]}
            return normalized

        if isinstance(llm_content, dict) and isinstance(llm_content.get("parts"), list):
            return result

        fallback_text = result.get("message")
        if not isinstance(fallback_text, str) or not fallback_text:
            fallback_text = f"Tool '{tool_name}' returned without llm_content"

        normalized = result.copy()
        normalized["llm_content"] = {"parts": [{"type": "text", "text": fallback_text}]}
        return normalized

    def _extract_bridge_task_id(self, result: Dict[str, Any]) -> Optional[str]:
        """Extract bridge task_id from normalized ToolResult."""
        structured_task_id = self._extract_task_id_from_structured(result)
        if structured_task_id:
            return structured_task_id

        text = self._extract_result_text(result)
        if not text:
            return None

        match = re.search(r"(?mi)^-\s*task_id:\s*([^\s]+)\s*$", text)
        return match.group(1).strip() if match else None

    def _extract_task_id_from_structured(self, result: Dict[str, Any]) -> Optional[str]:
        """Extract task_id from MCP structuredContent payload when available."""
        data = result.get("data")
        if not isinstance(data, dict):
            return None

        data_payload = data
        nested_payload = data_payload.get("data")
        if not isinstance(data_payload.get("structuredContent"), dict) and isinstance(nested_payload, dict):
            data_payload = nested_payload

        structured = data_payload.get("structuredContent")
        if not isinstance(structured, dict):
            return None

        payload = structured.get("result") if isinstance(structured.get("result"), dict) else structured
        candidates = [payload]
        if isinstance(payload, dict) and isinstance(payload.get("data"), dict):
            candidates.append(payload.get("data"))

        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            for key in ("task_id", "taskId", "id"):
                value = candidate.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        return None

    def _extract_result_text(self, result: Dict[str, Any]) -> str:
        """Extract concatenated text from llm_content/data content parts."""
        texts: List[str] = []

        llm_content = result.get("llm_content")
        if isinstance(llm_content, dict):
            parts = llm_content.get("parts")
            if isinstance(parts, list):
                for part in parts:
                    if isinstance(part, dict) and part.get("type") == "text":
                        text = part.get("text")
                        if isinstance(text, str) and text:
                            texts.append(text)

        data = result.get("data")
        if isinstance(data, dict):
            data_payload = data
            nested_payload = data_payload.get("data")
            if not isinstance(data_payload.get("content"), list) and isinstance(nested_payload, dict):
                data_payload = nested_payload

            content = data_payload.get("content")
            if isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        text = part.get("text")
                        if isinstance(text, str) and text:
                            texts.append(text)

        return "\n".join(texts)

    def _enrich_pfc_result_data(self, result: Dict[str, Any], hook_state: PfcExecuteTaskHookState) -> Dict[str, Any]:
        """Attach local tracking metadata to pfc_execute_task tool result."""
        enriched = result.copy()
        existing_data = enriched.get("data")
        data = existing_data.copy() if isinstance(existing_data, dict) else {}

        pfc_tracking = {
            "local_task_id": hook_state.local_task_id,
            "bridge_task_id": self._extract_bridge_task_id(result),
            "git_commit": hook_state.git_commit,
            "entry_script": hook_state.entry_script,
        }
        data["pfc_tracking"] = {k: v for k, v in pfc_tracking.items() if v}

        enriched["data"] = data
        return enriched

    async def _execute_with_confirmation(
        self, tool_call: Dict, message_id: str
    ) -> Tuple[Dict[str, Any], Optional[str], Optional[str]]:
        """
        Execute tool with user confirmation.

        Returns:
            Tuple[Dict, Optional[str], Optional[str]]: (result, outcome, user_message)
            - outcome is None if approved, "reject" or "reject_and_tell" if rejected
        """
        from backend.shared.utils.tool_result import user_rejected_response

        # Build confirmation info
        info = await self.confirmation_strategy.build_confirmation_info(tool_call)

        # Request confirmation (use notification_session_id for WebSocket routing)
        confirmation_result = await self.confirmation_strategy.request_confirmation(
            info, self.notification_session_id, message_id
        )

        if confirmation_result.outcome == "approve":
            result = await self._execute_single_tool(tool_call, message_id)
            # Check for SubAgent rejection marker (from invoke_agent)
            # SubAgent rejection is treated as MainAgent tool rejection
            if result.get("_subagent_user_rejected"):
                result["user_rejected"] = True
                result["rejection_outcome"] = "reject"
                return (result, "reject", None)
            return (result, None, None)
        elif confirmation_result.outcome == "reject_and_tell":
            # User wants to continue but with instruction
            result = user_rejected_response(
                user_message=confirmation_result.user_message or f"User rejected {info.tool_name}",
                include_stop_instruction=False,  # Don't tell agent to stop, continue with instruction
            )
            result["user_rejected"] = True
            result["rejection_outcome"] = "reject_and_tell"
            return (result, "reject_and_tell", confirmation_result.user_message)
        else:
            # reject: User wants to stop and provide input via main input
            result = user_rejected_response(
                user_message=confirmation_result.user_message or f"User rejected {info.tool_name}"
            )
            result["user_rejected"] = True
            result["rejection_outcome"] = "reject"
            return (result, "reject", confirmation_result.user_message)

    def _create_cascade_blocked_result(self, tool_name: str, rejected_tool_name: Optional[str]) -> Dict:
        """Create result for cascade-blocked tool."""
        from backend.shared.utils.tool_result import error_response

        cascade_message = (
            f"The user doesn't want to take this action right now. "
            f"Skipping {tool_name} because {rejected_tool_name} was rejected. "
            f"STOP what you are doing and wait for the user to tell you how to proceed."
        )
        result = error_response(cascade_message)
        result["cascade_blocked"] = True
        return result

    async def save_results_to_context(
        self,
        tool_calls: List[Dict],
        results: Sequence[Dict[str, Any]],
        context_manager: Any,
        inject_reminders: bool = True,
    ) -> None:
        """
        Save tool results to context manager in original order.

        Args:
            tool_calls: Original tool calls list
            results: Results indexed by original order
            context_manager: Context manager for adding results
            inject_reminders: Whether to inject reminders on the last tool result.
                             True for MainAgent, False for SubAgent by default.
        """
        for i, tool_call in enumerate(tool_calls):
            result = results[i]
            is_last_tool = i == len(tool_calls) - 1
            await context_manager.add_tool_result(
                tool_call["id"], tool_call["name"], result, inject_reminders=inject_reminders and is_last_tool
            )

    async def save_results_to_database(self, tool_calls: List[Dict], results: Sequence[Dict[str, Any]]) -> None:
        """Save tool results to database in original order."""
        await self.result_persistence.save_results(tool_calls, results)
