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
from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional, Tuple
from backend.application.services.confirmation_strategy import ConfirmationStrategy


# Rejection outcome types (subset of ConfirmationOutcome, excluding "approve")
RejectionOutcome = Literal["reject", "reject_and_tell"]


@dataclass
class ToolExecutionResult:
    """Result of tool execution batch."""
    results: List[Optional[Dict]]  # Results indexed by original order
    rejected_tools: List[str]  # Names of rejected tools
    user_rejected: bool  # Whether any tool was user-rejected (reject or reject_and_tell)
    rejection_outcome: Optional[RejectionOutcome] = None  # The type of rejection
    rejection_message: Optional[str] = None  # User's message for rejection


@dataclass
class ClassifiedTools:
    """Tools classified by confirmation requirement."""
    non_confirm: List[Tuple[int, Dict]] = field(default_factory=list)  # (index, tool_call)
    confirm: List[Tuple[int, Dict]] = field(default_factory=list)  # (index, tool_call)


class ToolExecutor:
    """
    Executes tools with classification and cascade blocking.

    Responsibilities:
    - Classify tools by confirmation requirement
    - Execute non-confirmation tools in parallel (conceptually)
    - Execute confirmation tools serially with cascade blocking
    - Notify results via WebSocket
    - Persist results to database
    """

    def __init__(
        self,
        tool_manager: Any,
        session_id: str,
        notification_session_id: Optional[str] = None,
        send_tool_result_notifications: bool = True
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
        """
        self.tool_manager = tool_manager
        self.session_id = session_id
        self.notification_session_id = notification_session_id or session_id
        self.send_tool_result_notifications = send_tool_result_notifications
        self.confirmation_strategy = ConfirmationStrategy(tool_manager)

    def classify_tools(self, tool_calls: List[Dict]) -> ClassifiedTools:
        """
        Classify tools into confirm and non-confirm categories.

        Args:
            tool_calls: List of tool call dicts

        Returns:
            ClassifiedTools with separated lists
        """
        classified = ClassifiedTools()

        for i, tool_call in enumerate(tool_calls):
            tool_name = tool_call.get('name', 'unknown')
            tool_args = tool_call.get('arguments', {})

            if self.confirmation_strategy.requires_confirmation(tool_name, tool_args):
                classified.confirm.append((i, tool_call))
            else:
                classified.non_confirm.append((i, tool_call))

        return classified

    async def execute_all(
        self,
        tool_calls: List[Dict],
        message_id: str,
        agent_profile: str = "general"
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
        # Classify tools
        classified = self.classify_tools(tool_calls)

        # Prepare results storage
        results: List[Optional[Dict]] = [None] * len(tool_calls)
        rejected_tools: List[str] = []
        rejection_outcome: Optional[RejectionOutcome] = None
        rejection_message: Optional[str] = None

        # Execute non-confirmation tools first
        for original_index, tool_call in classified.non_confirm:
            result = await self._execute_single_tool(tool_call, message_id)
            results[original_index] = result
            await self._notify_result(tool_call, result, agent_profile)

        # Execute confirmation tools serially with cascade blocking
        user_rejected = False
        rejected_tool_name: Optional[str] = None

        for original_index, tool_call in classified.confirm:
            tool_name = tool_call.get('name', 'unknown')

            if user_rejected:
                # Cascade block
                result = self._create_cascade_blocked_result(tool_name, rejected_tool_name)
                rejected_tools.append(tool_name)
            else:
                # Request confirmation and execute
                result, outcome, user_message = await self._execute_with_confirmation(
                    tool_call, message_id
                )
                if outcome in ("reject", "reject_and_tell"):
                    user_rejected = True
                    rejected_tool_name = tool_name
                    rejected_tools.append(tool_name)
                    rejection_outcome = outcome
                    rejection_message = user_message

            results[original_index] = result
            await self._notify_result(tool_call, result, agent_profile)

        return ToolExecutionResult(
            results=results,
            rejected_tools=rejected_tools,
            user_rejected=user_rejected,
            rejection_outcome=rejection_outcome,
            rejection_message=rejection_message,
        )

    async def _execute_single_tool(
        self,
        tool_call: Dict,
        message_id: str
    ) -> Dict:
        """Execute a single tool without confirmation."""
        return await self.tool_manager.handle_function_call(
            tool_call, self.session_id, message_id
        )

    async def _execute_with_confirmation(
        self,
        tool_call: Dict,
        message_id: str
    ) -> Tuple[Dict, Optional[str], Optional[str]]:
        """
        Execute tool with user confirmation.

        Returns:
            Tuple[Dict, Optional[str], Optional[str]]: (result, outcome, user_message)
            - outcome is None if approved, "reject" or "reject_and_tell" if rejected
        """
        from backend.infrastructure.mcp.utils.tool_result import user_rejected_response

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

    def _create_cascade_blocked_result(
        self,
        tool_name: str,
        rejected_tool_name: Optional[str]
    ) -> Dict:
        """Create result for cascade-blocked tool."""
        from backend.infrastructure.mcp.utils.tool_result import error_response

        cascade_message = (
            f"The user doesn't want to take this action right now. "
            f"Skipping {tool_name} because {rejected_tool_name} was rejected. "
            f"STOP what you are doing and wait for the user to tell you how to proceed."
        )
        result = error_response(cascade_message)
        result["cascade_blocked"] = True
        return result

    async def _notify_result(
        self,
        tool_call: Dict,
        result: Dict,
        agent_profile: str
    ) -> None:
        """Send WebSocket notification for tool result."""
        # Skip notification if disabled (e.g., for SubAgent internal tools)
        if not self.send_tool_result_notifications:
            return

        from backend.infrastructure.websocket.notification_service import WebSocketNotificationService

        tool_name = tool_call.get('name', 'unknown')

        try:
            await WebSocketNotificationService.send_tool_result_update(
                session_id=self.notification_session_id,
                message_id=tool_call['id'],
                tool_call_id=tool_call['id'],
                tool_name=tool_name,
                tool_result=result
            )
        except Exception as e:
            print(f"[ToolExecutor] Failed to send notification: {e}")

        # Send todo update if todo_write was called
        if tool_name == 'todo_write':
            try:
                from backend.application.services.todo_service import get_todo_service
                todo_service = get_todo_service()
                current_todo = await todo_service.get_current_todo(agent_profile, self.notification_session_id)
                await WebSocketNotificationService.send_todo_update(self.notification_session_id, current_todo)
            except Exception as e:
                print(f"[ToolExecutor] Failed to send todo update: {e}")

    async def save_results_to_context(
        self,
        tool_calls: List[Dict],
        results: List[Optional[Dict]],
        context_manager: Any,
        inject_reminders: bool = True
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
            if result is None:
                continue
            is_last_tool = (i == len(tool_calls) - 1)
            await context_manager.add_tool_result(
                tool_call['id'],
                tool_call['name'],
                result,
                inject_reminders=inject_reminders and is_last_tool
            )

    async def save_results_to_database(
        self,
        tool_calls: List[Dict],
        results: List[Optional[Dict]]
    ) -> None:
        """
        Save tool results to database in original order.

        Args:
            tool_calls: Original tool calls list
            results: Results indexed by original order
        """
        from backend.application.services.message_service import MessageService

        message_service = MessageService()
        for i, tool_call in enumerate(tool_calls):
            result = results[i]
            if result is not None:
                try:
                    message_service.save_tool_result_message(
                        tool_call_id=tool_call['id'],
                        tool_name=tool_call['name'],
                        tool_result=result,
                        session_id=self.session_id
                    )
                except Exception as e:
                    print(f"[ToolExecutor] Failed to save result: {e}")
