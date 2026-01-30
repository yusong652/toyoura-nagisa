"""
Agent - First-class citizen with active behavior.

This module provides the Agent class that encapsulates both
configuration (AgentConfig) and behavior (execute method).

Execution modes (controlled by config.is_main_agent):
- MainAgent: streaming LLM calls, WebSocket notifications, message persistence
- SubAgent: non-streaming calls, context-only storage
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Optional, cast, TYPE_CHECKING

from backend.application.agent.executors import MainAgentExecutor, SubAgentExecutor
from backend.application.contents.title_service import TitleService
from backend.application.session.message_service import MessageService
from backend.domain.models.agent import AgentResult
from backend.domain.models.agent_profiles import AgentConfig
from backend.domain.models.messages import AssistantMessage, UserMessage
from backend.infrastructure.llm.base.client import LLMClientBase
from backend.infrastructure.storage.session_manager import save_token_usage
from backend.infrastructure.websocket.notification_service import WebSocketNotificationService

if TYPE_CHECKING:
    from backend.application.agent.streaming_models import StreamingState
    from backend.application.agent.streaming_processor import StreamingProcessor


class Agent:
    """
    Agent with active behavior - first-class citizen in the system.

    An Agent encapsulates:
    - Configuration (AgentConfig)
    - Unified execution (execute() handles both streaming and non-streaming)
    - State management (context, execution tracking)

    Usage:
        # MainAgent (streaming, WebSocket, persistence)
        from backend.domain.models.agent_profiles import get_agent_config
        config = get_agent_config()
        agent = Agent(config, llm_client, session_id="abc123")
        result = await agent.execute(instruction=user_message)

        # SubAgent (non-streaming, context-only)
        from backend.domain.models.agent_profiles import PFC_EXPLORER
        explorer = Agent(PFC_EXPLORER, llm_client)
        result = await explorer.execute(UserMessage(content="Find ball syntax"))
    """

    _message_id: Optional[str] = None
    _state: Optional["StreamingState"] = None
    _streaming_processor: Optional["StreamingProcessor"] = None

    def __init__(
        self,
        config: AgentConfig,
        llm_client: LLMClientBase,
        session_id: str,
        enable_memory: bool | None = None,
        notification_session_id: str | None = None,
        parent_tool_call_id: str | None = None,
    ):
        """
        Initialize Agent.

        Args:
            config: Agent configuration (main or SubAgent)
            llm_client: LLM client for API calls
            session_id: Session ID (required for both MainAgent and SubAgent).
                       MainAgent uses persistent session ID.
                       SubAgent uses temporary session ID.
            enable_memory: Whether to enable memory persistence.
                          If None, uses config.enable_memory as default.
            notification_session_id: Session ID for WebSocket notifications and confirmations.
                                    If None, uses session_id. This allows SubAgents to route
                                    confirmation requests to MainAgent's WebSocket connection.
            parent_tool_call_id: ID of the parent tool call (invoke_agent) for SubAgent.
                                Used to associate SubAgent tool uses with parent in frontend.
        """
        self.config = config
        self.llm_client = llm_client

        # Execution mode is determined by configuration, not session_id
        self._is_main_agent = self.config.is_main_agent
        self.session_id: str = session_id

        # notification_session_id: for SubAgent, route to parent's WebSocket
        self._notification_session_id = notification_session_id or self.session_id

        # parent_tool_call_id: for SubAgent, associate tool uses with parent invoke_agent
        self._parent_tool_call_id = parent_tool_call_id

        # enable_memory: use provided value or fall back to config default
        self._enable_memory = enable_memory if enable_memory is not None else config.enable_memory

        # Streaming-related runtime attributes (initialized lazily)
        self._message_id = None
        self._state = None
        self._streaming_processor = None

    @property
    def context_manager(self):
        """Get context manager from llm_client (cached by session_id)."""
        return self.llm_client.get_or_create_context_manager(self.session_id)

    @property
    def status_monitor(self):
        """Get status monitor (cached by session_id).

        Storage mode for todos is determined dynamically by agent_profile
        in TodoMonitor.get_reminders(), not at construction time.
        """
        from backend.infrastructure.monitoring import get_status_monitor

        return get_status_monitor(self.session_id)

    @property
    def is_main_agent(self) -> bool:
        """Whether this agent is a MainAgent (with persistent session)."""
        return self._is_main_agent

    @property
    def name(self) -> str:
        """Agent name from definition."""
        return self.config.name

    @property
    def display_name(self) -> str:
        """Agent display name from definition."""
        return self.config.display_name

    def _set_streaming_processor(self, processor: "StreamingProcessor") -> None:
        self._streaming_processor = processor

    def _set_message_id(self, message_id: str) -> None:
        self._message_id = message_id

    def _set_stream_state(self, state: "StreamingState") -> None:
        self._state = state

    def _get_streaming_processor(self) -> "StreamingProcessor":
        processor = getattr(self, "_streaming_processor")
        if processor is None:
            raise RuntimeError("Streaming processor is not initialized")
        return processor

    def _get_message_id(self) -> str:
        message_id = getattr(self, "_message_id")
        if message_id is None:
            raise RuntimeError("Message ID is not initialized")
        return message_id

    def _get_stream_state(self) -> "StreamingState":
        state = getattr(self, "_state")
        if state is None:
            raise RuntimeError("Streaming state is not initialized")
        return state

    async def execute(self, instruction: UserMessage) -> AgentResult:
        """
        Unified agent execution entry point.

        Handles both MainAgent (streaming) and SubAgent (non-streaming) modes:
        - MainAgent: streaming LLM calls, WebSocket notifications, persistence
        - SubAgent: non-streaming calls, activity callbacks, context-only storage

        All configuration comes from self.config (name, enable_memory, etc.)

        Args:
            instruction: UserMessage object containing user input (required)

        Returns:
            AgentResult with execution outcome

        Raises:
            UserRejectionInterruption: When user rejects tool execution (MainAgent only)
        """
        from backend.shared.exceptions import UserRejectionInterruption
        from backend.shared.utils.prompt.builder import build_system_prompt

        start_time = time.time()
        message_service = MessageService()

        try:
            # Configure context manager from definition and instance settings
            self.context_manager.agent_profile = self.config.name
            self.context_manager.enable_memory = self._enable_memory

            # SubAgent: Also register in primary LLM client for tool workspace resolution
            # Tools use get_llm_client() to find agent_profile, so SubAgent must be visible there
            if not self.is_main_agent:
                from backend.infrastructure.llm.session_client import get_session_llm_client

                try:
                    # Resolve primary session LLM client
                    primary_client = get_session_llm_client(self.session_id)
                    primary_ctx = primary_client.get_or_create_context_manager(self.session_id)
                    primary_ctx.agent_profile = self.config.name
                except Exception:
                    pass  # Fallback gracefully if primary client unavailable

            # Build system prompt once (immutable during Agent lifecycle)
            # Memory context is now injected into user messages via ReminderInjector,
            # not in the system prompt (follows modern LLM best practices)
            self._system_prompt = await build_system_prompt(
                agent_profile=self.config.name,  # Use config.name for SubAgent prompt lookup
                session_id=self.session_id,
                include_expression=self.is_main_agent,  # SubAgent: no expression instructions
            )

            # Add instruction to context
            await self.context_manager.add_user_message(instruction)

            # MainAgent: persist to database
            if self.is_main_agent:
                timestamp_ms = int(instruction.timestamp.timestamp() * 1000) if instruction.timestamp else None
                message_service.save_user_message(
                    content=cast(list[dict[str, Any]], instruction.content),
                    session_id=self.session_id,
                    timestamp=timestamp_ms,
                    message_id=instruction.id,
                )

            # Execute unified loop
            final_response = await self._execute_loop()

            # Format result based on mode
            if final_response is None:
                return AgentResult(
                    status="max_iterations",
                    iterations_used=self.config.max_iterations,
                    execution_time_seconds=time.time() - start_time,
                )

            processor = self.llm_client._get_response_processor()
            if self.is_main_agent:
                # MainAgent: use processor for storage format
                final_message = processor.format_response_for_storage(final_response)
                streaming_message_id = getattr(self.context_manager, "streaming_message_id", None)
            else:
                # SubAgent: check for special markers first
                if isinstance(final_response, dict):
                    # Check for user rejection marker
                    # Note: rejection context is already saved by _execute_iteration
                    # MainAgent will see this as invoke_agent rejection
                    if "_subagent_rejected" in final_response:
                        return AgentResult(
                            status="user_rejected",
                            message=AssistantMessage(
                                role="assistant",
                                content=[{"type": "text", "text": "SubAgent operation was rejected by user."}],
                            ),
                            execution_time_seconds=time.time() - start_time,
                        )

                    # Check for iteration limit marker
                    if "_iteration_limit_text" in final_response:
                        # Iteration limit reached - use pre-formatted text
                        response_text = final_response["_iteration_limit_text"]
                        return AgentResult(
                            status="max_iterations",
                            message=AssistantMessage(
                                role="assistant", content=[{"type": "text", "text": response_text}]
                            ),
                            iterations_used=self.config.max_iterations,
                            execution_time_seconds=time.time() - start_time,
                        )

                # SubAgent: extract text content from LLM response
                response_text = processor.extract_text_content(final_response)
                final_message = AssistantMessage(role="assistant", content=[{"type": "text", "text": response_text}])
                streaming_message_id = None

                # SubAgent: check for empty response (domain-level validation)
                # Some LLM APIs return whitespace-only content as "empty" response
                if not response_text or not response_text.strip():
                    return AgentResult(
                        status="empty_response",
                        message=final_message,
                        iterations_used=self.config.max_iterations,
                        execution_time_seconds=time.time() - start_time,
                    )

            return AgentResult(
                status="success",
                message=final_message,
                message_id=streaming_message_id,
                execution_time_seconds=time.time() - start_time,
            )

        except UserRejectionInterruption:
            # MainAgent: re-raise user rejection
            raise

        except Exception as e:
            if self.is_main_agent:
                # MainAgent: clean up placeholder message on error
                import traceback

                print(f"[Agent] Exception: {e}")
                print(f"[Agent] Traceback: {traceback.format_exc()}")

                streaming_message_id = getattr(self.context_manager, "streaming_message_id", None)
                if streaming_message_id:
                    try:
                        message_service = MessageService()
                        await message_service.delete_message_async(self.session_id, streaming_message_id)
                    except Exception as cleanup_error:
                        print(f"[Agent] Failed to clean up placeholder: {cleanup_error}")

                raise Exception(f"Agent execution failed: {e}") from e
            else:
                # SubAgent: return error result
                error_message = AssistantMessage(
                    role="assistant", content=[{"type": "text", "text": f"Error: {str(e)}"}]
                )
                return AgentResult(
                    status="error",
                    message=error_message,
                    execution_time_seconds=time.time() - start_time,
                )

        finally:
            # Reset iteration context to prevent stale warnings in next conversation turn
            self.status_monitor.reset_iteration_context()

    async def _execute_loop(self) -> Any:
        """Delegate execution loop to the mode-specific executor."""
        executor = MainAgentExecutor(self) if self.is_main_agent else SubAgentExecutor(self)
        return await executor.execute_loop()

    async def _save_rejection_context(
        self, rejected_tools: list, rejection_message: str | None, is_subagent: bool = False
    ) -> None:
        """
        Save rejection context for next message injection.

        When user rejects a tool, we save the context so that the next message
        can include information about what was rejected. This helps the agent
        understand the context when user provides their next input.

        Args:
            rejected_tools: List of rejected tool names
            rejection_message: Optional message from user
            is_subagent: Whether this is a SubAgent rejection
        """
        from backend.infrastructure.storage.session_manager import update_runtime_state

        rejection_context = {
            "rejected_tools": rejected_tools,
            "rejection_message": rejection_message,
            "is_subagent": is_subagent,
        }

        # Use notification_session_id for SubAgent (MainAgent's session)
        target_session_id = self._notification_session_id if is_subagent else self.session_id
        update_runtime_state(target_session_id, "rejection_context", rejection_context)

    async def _handle_stream_interruption(self, iteration: int) -> Any:
        """Handle user interruption during streaming."""
        print(f"[Agent.stream] Interrupted by user at iteration {iteration}")

        self.status_monitor.set_interrupt_flag()

        # Construct partial response
        processor = self.llm_client._get_response_processor()
        processor.construct_response_from_chunks(self._get_stream_state().collected_chunks)

        # Delete placeholder message
        await MessageService().delete_message_async(self.session_id, self._get_stream_state().message_id)

        # Send final update with interrupted=True
        await WebSocketNotificationService.send_streaming_update(
            session_id=self.session_id,
            message_id=self._get_stream_state().message_id,
            content=self._get_stream_state().get_content_blocks(),
            streaming=False,
            interrupted=True,
        )

        # Trigger title generation
        asyncio.create_task(TitleService().try_generate_title_if_needed_async(self.session_id, self.llm_client))
        return None

    async def _finalize_stream_response(self, response: Any) -> Any:
        """Finalize streaming response without tool calls."""
        # Add to context
        self.context_manager.add_response(response)

        # Format and save (format_for_storage always returns AssistantMessage with List content)
        final_message = self._get_streaming_processor().format_for_storage(response)
        content = final_message.content
        MessageService().update_assistant_message(self._get_message_id(), content, self.session_id)

        usage = self._get_streaming_processor().extract_usage(self._get_stream_state())

        # Send final update
        await WebSocketNotificationService.send_streaming_update(
            session_id=self.session_id,
            message_id=self._get_message_id(),
            content=content,
            streaming=False,
            usage=usage,
        )

        # Save usage
        if usage:
            save_token_usage(self.session_id, usage)

        # Trigger title generation
        asyncio.create_task(TitleService().try_generate_title_if_needed_async(self.session_id, self.llm_client))

        return response

    async def _update_stream_tool_message(self, response: Any, tool_calls: list) -> None:
        """Update streaming message with tool call content."""
        try:
            tool_call_message = self._get_streaming_processor().format_for_storage(response, tool_calls)
            content = tool_call_message.content
            MessageService().update_assistant_message(self._get_message_id(), content, self.session_id)

            usage = self._get_streaming_processor().extract_usage(self._get_stream_state())

            # Send streaming update and WAIT for completion
            await WebSocketNotificationService.send_streaming_update(
                session_id=self.session_id,
                message_id=self._get_message_id(),
                content=content,
                streaming=True,
                usage=usage,
            )

            if usage:
                save_token_usage(self.session_id, usage)

            # Trigger title generation
            asyncio.create_task(TitleService().try_generate_title_if_needed_async(self.session_id, self.llm_client))

        except Exception as e:
            print(f"[Agent.stream] Failed to update streaming message: {e}")

    async def _handle_iteration_limit(self, tool_calls: list) -> Any:
        """Handle iteration limit for both MainAgent and SubAgent."""
        if self.is_main_agent:
            from backend.shared.utils.tool_result import error_response
            from backend.infrastructure.monitoring.status_monitor import StatusMonitor

            print(f"[Agent.stream] Reached iteration limit ({self.config.max_iterations})")

            stop_message = StatusMonitor.get_iteration_limit_tool_message(self.config.max_iterations)

            message_service = MessageService()
            for i, tool_call in enumerate(tool_calls):
                is_last_tool = i == len(tool_calls) - 1

                limit_result = error_response(
                    stop_message, llm_content={"parts": [{"type": "text", "text": stop_message}]}
                )

                await self.context_manager.add_tool_result(
                    tool_call["id"], tool_call["name"], limit_result, inject_reminders=is_last_tool
                )

                try:
                    result_message_id = message_service.save_tool_result_message(
                        tool_call_id=tool_call["id"],
                        tool_name=tool_call["name"],
                        tool_result=limit_result,
                        session_id=self.session_id,
                    )

                    await WebSocketNotificationService.send_tool_result_update(
                        session_id=self.session_id,
                        message_id=result_message_id,
                        tool_call_id=tool_call["id"],
                        tool_name=tool_call["name"],
                        tool_result=limit_result,
                    )
                except Exception as e:
                    print(f"[Agent.stream] Failed to save iteration limit result: {e}")
            return None

        print(
            f"[SubAgent] Reached iteration limit ({self.config.max_iterations}), "
            f"skipping {len(tool_calls)} pending tool calls"
        )

        pending_tools = [tc.get("name", "unknown") for tc in tool_calls]

        summary_text = (
            f"SubAgent reached iteration limit ({self.config.max_iterations} iterations).\n\n"
            f"Pending tool calls (NOT executed): {', '.join(pending_tools)}\n\n"
            f"Note: The subagent was warned multiple times before reaching the limit. "
            f"Consider breaking the task into smaller sub-tasks or providing more specific instructions."
        )

        return {"_iteration_limit_text": summary_text}
