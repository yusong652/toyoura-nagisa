"""
Agent hierarchy with inheritance-based separation.

This module provides:
- BaseAgent: Shared infrastructure (config, llm_client, context_manager)
- MainAgent: Streaming execution, WebSocket notifications, message persistence
- SubAgent: Non-streaming execution, context-only storage

Each agent type has focused responsibilities following the Single Responsibility Principle.
"""

from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
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


class BaseAgent(ABC):
    """
    Base agent with shared infrastructure.

    Provides common functionality for all agent types:
    - Configuration management
    - LLM client access
    - Context manager (cached by session_id)
    - Status monitor for iteration tracking

    Subclasses implement execution-specific behavior.
    """

    def __init__(
        self,
        config: AgentConfig,
        llm_client: LLMClientBase,
        session_id: str,
        enable_memory: bool | None = None,
    ):
        """
        Initialize base agent.

        Args:
            config: Agent configuration
            llm_client: LLM client for API calls
            session_id: Session ID for context management
            enable_memory: Whether to enable memory persistence.
                          If None, uses config.enable_memory as default.
        """
        self.config = config
        self.llm_client = llm_client
        self.session_id = session_id
        self._enable_memory = enable_memory if enable_memory is not None else config.enable_memory
        self._system_prompt: str = ""
        # Default notification session is self (MainAgent uses this)
        self._notification_session_id = session_id

    @property
    def context_manager(self):
        """Get context manager from llm_client (cached by session_id)."""
        return self.llm_client.get_or_create_context_manager(self.session_id)

    @property
    def status_monitor(self):
        """Get status monitor (cached by session_id)."""
        from backend.infrastructure.monitoring import get_status_monitor

        return get_status_monitor(self.session_id)

    @property
    def name(self) -> str:
        """Agent name from configuration."""
        return self.config.name

    @property
    def display_name(self) -> str:
        """Agent display name from configuration."""
        return self.config.display_name

    async def execute(self, instruction: UserMessage) -> AgentResult:
        """
        Execute agent with given instruction.

        Template method that defines the execution skeleton:
        1. Prepare context (system prompt, context manager)
        2. Pre-execute hook (subclass-specific setup)
        3. Execute loop (subclass-specific execution)
        4. Build result (subclass-specific result formatting)

        Args:
            instruction: UserMessage object containing user input

        Returns:
            AgentResult with execution outcome
        """
        from backend.shared.exceptions import UserRejectionInterruption

        start_time = time.time()

        try:
            await self._prepare_context(instruction)
            await self._pre_execute(instruction)
            response = await self._execute_loop()
            return await self._build_result(response, start_time)

        except UserRejectionInterruption:
            raise

        except Exception as e:
            return await self._handle_error(e, start_time)

        finally:
            self.status_monitor.reset_iteration_context()

    async def _prepare_context(self, instruction: UserMessage) -> None:
        """Prepare context manager and build system prompt."""
        from backend.shared.utils.prompt.builder import build_system_prompt

        self.context_manager.agent_profile = self.config.name
        self.context_manager.enable_memory = self._enable_memory

        self._system_prompt = await build_system_prompt(
            agent_profile=self.config.name,
            session_id=self.session_id,
            include_expression=self._include_expression_in_prompt(),
        )

        await self.context_manager.add_user_message(instruction)

    def _include_expression_in_prompt(self) -> bool:
        """Whether to include expression instructions in system prompt."""
        return True  # Default: include expression

    @abstractmethod
    async def _pre_execute(self, instruction: UserMessage) -> None:
        """Subclass-specific setup before execution loop."""
        pass

    @abstractmethod
    async def _execute_loop(self) -> Any:
        """Execute the agent loop. Returns LLM response or special marker dict."""
        pass

    @abstractmethod
    async def _build_result(self, response: Any, start_time: float) -> AgentResult:
        """Build AgentResult from execution response."""
        pass

    @abstractmethod
    async def _handle_error(self, error: Exception, start_time: float) -> AgentResult:
        """Handle execution error."""
        pass

    async def _save_rejection_context(
        self, rejected_tools: list, rejection_message: str | None, is_subagent: bool = False
    ) -> None:
        """Save rejection context for next message injection."""
        from backend.infrastructure.storage.session_manager import update_runtime_state

        rejection_context = {
            "rejected_tools": rejected_tools,
            "rejection_message": rejection_message,
            "is_subagent": is_subagent,
        }

        target_session_id = self._get_notification_session_id() if is_subagent else self.session_id
        update_runtime_state(target_session_id, "rejection_context", rejection_context)

    def _get_notification_session_id(self) -> str:
        """Get session ID for WebSocket notifications. Override in SubAgent."""
        return self.session_id


class MainAgent(BaseAgent):
    """
    Main agent with streaming execution and full persistence.

    Features:
    - Streaming LLM calls with real-time WebSocket updates
    - Message persistence to database
    - Title generation
    - User interruption handling

    Usage:
        from backend.domain.models.agent_profiles import get_agent_config
        config = get_agent_config()
        agent = MainAgent(config, llm_client, session_id="abc123")
        result = await agent.execute(instruction=user_message)
    """

    _message_id: Optional[str] = None
    _state: Optional["StreamingState"] = None
    _streaming_processor: Optional["StreamingProcessor"] = None

    async def _pre_execute(self, instruction: UserMessage) -> None:
        """Persist user message to database."""
        timestamp_ms = int(instruction.timestamp.timestamp() * 1000) if instruction.timestamp else None
        MessageService().save_user_message(
            content=cast(list[dict[str, Any]], instruction.content),
            session_id=self.session_id,
            timestamp=timestamp_ms,
            message_id=instruction.id,
        )

    async def _execute_loop(self) -> Any:
        """Execute streaming loop via MainAgentExecutor."""
        return await MainAgentExecutor(self).execute_loop()

    async def _build_result(self, response: Any, start_time: float) -> AgentResult:
        """Build result with storage format and message_id."""
        if response is None:
            return AgentResult(
                status="max_iterations",
                iterations_used=self.config.max_iterations,
                execution_time_seconds=time.time() - start_time,
            )

        processor = self.llm_client._get_response_processor()
        final_message = processor.format_response_for_storage(response)
        streaming_message_id = getattr(self.context_manager, "streaming_message_id", None)

        return AgentResult(
            status="success",
            message=final_message,
            message_id=streaming_message_id,
            execution_time_seconds=time.time() - start_time,
        )

    async def _handle_error(self, error: Exception, start_time: float) -> AgentResult:
        """Clean up placeholder message and re-raise."""
        import traceback

        print(f"[MainAgent] Exception: {error}")
        print(f"[MainAgent] Traceback: {traceback.format_exc()}")

        streaming_message_id = getattr(self.context_manager, "streaming_message_id", None)
        if streaming_message_id:
            try:
                await MessageService().delete_message_async(self.session_id, streaming_message_id)
            except Exception as cleanup_error:
                print(f"[MainAgent] Failed to clean up placeholder: {cleanup_error}")

        raise Exception(f"Agent execution failed: {error}") from error

    # Streaming-specific methods

    def _set_streaming_processor(self, processor: "StreamingProcessor") -> None:
        self._streaming_processor = processor

    def _set_message_id(self, message_id: str) -> None:
        self._message_id = message_id

    def _set_stream_state(self, state: "StreamingState") -> None:
        self._state = state

    def _get_streaming_processor(self) -> "StreamingProcessor":
        if self._streaming_processor is None:
            raise RuntimeError("Streaming processor is not initialized")
        return self._streaming_processor

    def _get_message_id(self) -> str:
        if self._message_id is None:
            raise RuntimeError("Message ID is not initialized")
        return self._message_id

    def _get_stream_state(self) -> "StreamingState":
        if self._state is None:
            raise RuntimeError("Streaming state is not initialized")
        return self._state

    async def _handle_stream_interruption(self, iteration: int) -> Any:
        """Handle user interruption during streaming."""
        print(f"[MainAgent] Interrupted by user at iteration {iteration}")

        self.status_monitor.set_interrupt_flag()

        processor = self.llm_client._get_response_processor()
        processor.construct_response_from_chunks(self._get_stream_state().collected_chunks)

        await MessageService().delete_message_async(self.session_id, self._get_stream_state().message_id)

        await WebSocketNotificationService.send_streaming_update(
            session_id=self.session_id,
            message_id=self._get_stream_state().message_id,
            content=self._get_stream_state().get_content_blocks(),
            streaming=False,
            interrupted=True,
        )

        asyncio.create_task(TitleService().try_generate_title_if_needed_async(self.session_id, self.llm_client))
        return None

    async def _finalize_stream_response(self, response: Any) -> Any:
        """Finalize streaming response without tool calls."""
        self.context_manager.add_response(response)

        final_message = self._get_streaming_processor().format_for_storage(response)
        content = final_message.content
        MessageService().update_assistant_message(self._get_message_id(), content, self.session_id)

        usage = self._get_streaming_processor().extract_usage(self._get_stream_state())

        await WebSocketNotificationService.send_streaming_update(
            session_id=self.session_id,
            message_id=self._get_message_id(),
            content=content,
            streaming=False,
            usage=usage,
        )

        if usage:
            save_token_usage(self.session_id, usage)

        asyncio.create_task(TitleService().try_generate_title_if_needed_async(self.session_id, self.llm_client))

        return response

    async def _update_stream_tool_message(self, response: Any, tool_calls: list) -> None:
        """Update streaming message with tool call content."""
        try:
            tool_call_message = self._get_streaming_processor().format_for_storage(response, tool_calls)
            content = tool_call_message.content
            MessageService().update_assistant_message(self._get_message_id(), content, self.session_id)

            usage = self._get_streaming_processor().extract_usage(self._get_stream_state())

            await WebSocketNotificationService.send_streaming_update(
                session_id=self.session_id,
                message_id=self._get_message_id(),
                content=content,
                streaming=True,
                usage=usage,
            )

            if usage:
                save_token_usage(self.session_id, usage)

            asyncio.create_task(TitleService().try_generate_title_if_needed_async(self.session_id, self.llm_client))

        except Exception as e:
            print(f"[MainAgent] Failed to update streaming message: {e}")

    async def _handle_iteration_limit(self, tool_calls: list) -> Any:
        """Handle iteration limit by returning error results for pending tools."""
        from backend.shared.utils.tool_result import error_response
        from backend.infrastructure.monitoring.status_monitor import StatusMonitor

        print(f"[MainAgent] Reached iteration limit ({self.config.max_iterations})")

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
                print(f"[MainAgent] Failed to save iteration limit result: {e}")

        return None


class SubAgent(BaseAgent):
    """
    Sub-agent with non-streaming execution and context-only storage.

    Features:
    - Non-streaming LLM calls for efficiency
    - Context-only storage (no database persistence)
    - Routes WebSocket notifications to parent MainAgent
    - Reports tool usage to parent for frontend display

    Usage:
        from backend.domain.models.agent_profiles import PFC_EXPLORER
        agent = SubAgent(
            PFC_EXPLORER, llm_client, session_id="temp_123",
            notification_session_id="parent_abc",
            parent_tool_call_id="tool_xyz"
        )
        result = await agent.execute(UserMessage(content="Find ball syntax"))
    """

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
        Initialize SubAgent.

        Args:
            config: SubAgent configuration
            llm_client: LLM client for API calls
            session_id: Temporary session ID for this SubAgent
            enable_memory: Whether to enable memory persistence
            notification_session_id: Parent MainAgent's session ID for WebSocket routing
            parent_tool_call_id: ID of invoke_agent tool call for frontend association
        """
        super().__init__(config, llm_client, session_id, enable_memory)
        self._notification_session_id = notification_session_id or session_id
        self._parent_tool_call_id = parent_tool_call_id

    def _include_expression_in_prompt(self) -> bool:
        """SubAgent: no expression instructions needed."""
        return False

    def _get_notification_session_id(self) -> str:
        """Return parent's session ID for WebSocket notifications."""
        return self._notification_session_id

    async def _pre_execute(self, instruction: UserMessage) -> None:
        """Register in primary LLM client for tool workspace resolution."""
        from backend.infrastructure.llm.session_client import get_session_llm_client

        try:
            primary_client = get_session_llm_client(self.session_id)
            primary_ctx = primary_client.get_or_create_context_manager(self.session_id)
            primary_ctx.agent_profile = self.config.name
        except Exception:
            pass  # Fallback gracefully if primary client unavailable

    async def _execute_loop(self) -> Any:
        """Execute non-streaming loop via SubAgentExecutor."""
        return await SubAgentExecutor(self).execute_loop()

    async def _build_result(self, response: Any, start_time: float) -> AgentResult:
        """Build result, handling special markers and text extraction."""
        if response is None:
            return AgentResult(
                status="max_iterations",
                iterations_used=self.config.max_iterations,
                execution_time_seconds=time.time() - start_time,
            )

        # Check for special markers
        if isinstance(response, dict):
            if "_subagent_rejected" in response:
                return AgentResult(
                    status="user_rejected",
                    message=AssistantMessage(
                        role="assistant",
                        content=[{"type": "text", "text": "SubAgent operation was rejected by user."}],
                    ),
                    execution_time_seconds=time.time() - start_time,
                )

            if "_iteration_limit_text" in response:
                response_text = response["_iteration_limit_text"]
                return AgentResult(
                    status="max_iterations",
                    message=AssistantMessage(
                        role="assistant", content=[{"type": "text", "text": response_text}]
                    ),
                    iterations_used=self.config.max_iterations,
                    execution_time_seconds=time.time() - start_time,
                )

        # Extract text content from LLM response
        processor = self.llm_client._get_response_processor()
        response_text = processor.extract_text_content(response)
        final_message = AssistantMessage(role="assistant", content=[{"type": "text", "text": response_text}])

        # Check for empty response
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
            execution_time_seconds=time.time() - start_time,
        )

    async def _handle_error(self, error: Exception, start_time: float) -> AgentResult:
        """Return error result without raising."""
        error_message = AssistantMessage(
            role="assistant", content=[{"type": "text", "text": f"Error: {str(error)}"}]
        )
        return AgentResult(
            status="error",
            message=error_message,
            execution_time_seconds=time.time() - start_time,
        )

    async def _handle_iteration_limit(self, tool_calls: list) -> Any:
        """Return iteration limit marker for result building."""
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


# Backward compatibility alias
Agent = MainAgent
