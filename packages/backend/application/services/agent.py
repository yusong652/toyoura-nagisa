"""
Agent - First-class citizen with active behavior.

This module provides the Agent class that encapsulates both
configuration (ProfileConfig/SubAgentConfig) and behavior (execute method).

Execution modes (controlled by is_main_agent):
- MainAgent: streaming LLM calls, WebSocket notifications, message persistence
- SubAgent: non-streaming calls, activity callbacks, context-only storage
"""

import time
import uuid
from typing import Any, Callable, Dict, List, Optional, Union, cast

from backend.domain.models.agent import AgentActivity, AgentResult
from backend.domain.models.agent_profiles import ProfileConfig, SubAgentConfig
from backend.domain.models.messages import AssistantMessage, UserMessage
from backend.domain.models.message_factory import extract_text_from_message
from backend.infrastructure.llm.base.client import LLMClientBase
from backend.application.services.tool_executor import ToolExecutor
from backend.application.services.streaming_models import StreamingState
from backend.application.services.streaming_processor import StreamingProcessor
from backend.application.services.message_service import MessageService
from backend.application.services.contents.title_service import trigger_title_generation
from backend.infrastructure.storage.session_manager import save_token_usage

# Type alias for agent configuration
AgentConfig = Union[ProfileConfig, SubAgentConfig]


class Agent:
    """
    Agent with active behavior - first-class citizen in the system.

    An Agent encapsulates:
    - Configuration (ProfileConfig or SubAgentConfig)
    - Unified execution (execute() handles both streaming and non-streaming)
    - State management (context, execution tracking)

    Usage:
        # MainAgent (streaming, WebSocket, persistence)
        from backend.domain.models.agent_profiles import get_profile_config
        config = get_profile_config("coding")
        agent = Agent(config, llm_client, session_id="abc123")
        result = await agent.execute(instruction=user_message)

        # SubAgent (non-streaming, activity callbacks)
        from backend.domain.models.agent_profiles import PFC_EXPLORER
        explorer = Agent(PFC_EXPLORER, llm_client, on_activity=callback)
        result = await explorer.execute(UserMessage(content="Find ball syntax"))
    """

    def __init__(
        self,
        config: AgentConfig,
        llm_client: LLMClientBase,
        session_id: Optional[str] = None,
        enable_memory: Optional[bool] = None,
        on_activity: Optional[Callable[[AgentActivity], None]] = None,
        notification_session_id: Optional[str] = None,
        parent_tool_call_id: Optional[str] = None,
    ):
        """
        Initialize Agent.

        Args:
            config: Agent configuration (ProfileConfig or SubAgentConfig)
            llm_client: LLM client for API calls
            session_id: Session ID for MainAgent (persistent session).
                       If provided, agent operates as MainAgent with streaming and persistence.
                       If None, agent operates as SubAgent with auto-generated temporary ID.
            enable_memory: Whether to enable memory persistence.
                          If None, uses config.enable_memory as default.
            on_activity: Optional callback for activity events (SubAgent mode)
            notification_session_id: Session ID for WebSocket notifications and confirmations.
                                    If None, uses session_id. This allows SubAgents to route
                                    confirmation requests to MainAgent's WebSocket connection.
            parent_tool_call_id: ID of the parent tool call (invoke_agent) for SubAgent.
                                Used to associate SubAgent tool uses with parent in frontend.
        """
        self.config = config
        self.llm_client = llm_client
        self.on_activity = on_activity

        # session_id is always str - auto-generate for SubAgent
        self._is_main_agent = session_id is not None
        self.session_id: str = session_id if session_id is not None else str(uuid.uuid4())[:8]

        # notification_session_id: for SubAgent, route to parent's WebSocket
        self._notification_session_id = notification_session_id or self.session_id

        # parent_tool_call_id: for SubAgent, associate tool uses with parent invoke_agent
        self._parent_tool_call_id = parent_tool_call_id

        # enable_memory: use provided value or fall back to config default
        self._enable_memory = enable_memory if enable_memory is not None else config.enable_memory

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

    async def execute(self, instruction: UserMessage) -> AgentResult:
        """
        Unified agent execution entry point.

        Handles both MainAgent (streaming) and SubAgent (non-streaming) modes:
        - MainAgent: streaming LLM calls, WebSocket notifications, persistence
        - SubAgent: non-streaming calls, activity callbacks, context-only storage

        All configuration comes from self.config (tool_profile, enable_memory, etc.)

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

        # SubAgent: emit started activity
        if not self.is_main_agent:
            self._emit_activity("started", {"instruction": extract_text_from_message(instruction)})

        try:
            # Setup context manager (cached as instance attribute)
            self._context_manager = self.llm_client.get_or_create_context_manager(self.session_id)

            # Configure context manager from definition and instance settings
            self._context_manager.agent_profile = self.config.tool_profile
            self._context_manager.enable_memory = self._enable_memory

            # Build system prompt once (immutable during Agent lifecycle)
            prompt_tool_schemas = await self.llm_client.tool_manager.get_schemas_for_system_prompt(
                self.session_id, self._context_manager.agent_profile
            )
            self._system_prompt = await build_system_prompt(
                agent_profile=self.config.name,  # Use config.name for SubAgent prompt lookup
                session_id=self.session_id,
                enable_memory=self._context_manager.enable_memory,
                tool_schemas=prompt_tool_schemas,
                include_expression=self.is_main_agent,  # SubAgent: no expression instructions
            )

            # Add instruction to context
            await self._context_manager.add_user_message(instruction)

            # MainAgent: persist to database
            if self.is_main_agent:
                timestamp_ms = int(instruction.timestamp.timestamp() * 1000) if instruction.timestamp else None
                message_service.save_user_message(
                    content=cast(List[Dict[str, Any]], instruction.content),
                    session_id=self.session_id,
                    timestamp=timestamp_ms,
                    message_id=instruction.id
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
                streaming_message_id = getattr(self._context_manager, 'streaming_message_id', None)
            else:
                # SubAgent: extract text content
                response_text = processor.extract_text_content(final_response)
                final_message = AssistantMessage(
                    role="assistant",
                    content=[{"type": "text", "text": response_text}]
                )
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

                streaming_message_id = getattr(self._context_manager, 'streaming_message_id', None)
                if streaming_message_id:
                    try:
                        message_service = MessageService()
                        await message_service.delete_message_async(self.session_id, streaming_message_id)
                    except Exception as cleanup_error:
                        print(f"[Agent] Failed to clean up placeholder: {cleanup_error}")

                raise Exception(f"Agent execution failed: {e}")
            else:
                # SubAgent: emit error activity and return error result
                self._emit_activity("error", {"error": str(e)})
                error_message = AssistantMessage(
                    role="assistant",
                    content=[{"type": "text", "text": f"Error: {str(e)}"}]
                )
                return AgentResult(
                    status="error",
                    message=error_message,
                    execution_time_seconds=time.time() - start_time,
                )

        finally:
            # SubAgent: emit completed activity
            if not self.is_main_agent:
                self._emit_activity("completed", {"elapsed": time.time() - start_time})

    async def _execute_loop(self) -> Any:
        """
        Unified execution loop for both streaming and non-streaming modes.

        Uses self.is_main_agent to control:
        - LLM call method (streaming vs non-streaming)
        - Message persistence (MainAgent only)
        - Progress notifications (WebSocket vs activity callbacks)
        - User interruption handling (MainAgent only)

        Returns:
            Final LLM response object
        """
        from backend.infrastructure.websocket.notification_service import WebSocketNotificationService
        from backend.infrastructure.monitoring import get_status_monitor
        from backend.shared.exceptions import UserRejectionInterruption

        # Initialize MainAgent execution context (stored as instance attributes)
        if self.is_main_agent:
            self._streaming_processor = StreamingProcessor(self.llm_client, self.session_id)
            self._status_monitor = get_status_monitor(self.session_id)
            self._status_monitor.todo_monitor.track_conversation_turn()

        iteration = 0
        while True:
            # Get tool schemas and build API config
            tool_schemas = await self.llm_client.tool_manager.get_function_call_schemas(
                self.session_id, self._context_manager.agent_profile
            )
            api_config = self.llm_client._build_api_config(self._system_prompt, tool_schemas)

            # === MainAgent: Create placeholder message ===
            if self.is_main_agent:
                message_service = MessageService()
                self._message_id = message_service.save_assistant_message([], self.session_id)
                await WebSocketNotificationService.send_message_create(
                    self.session_id, self._message_id, streaming=True
                )
                self._context_manager.streaming_message_id = self._message_id
                self._state = StreamingState(message_id=self._message_id)

            # Get working contents from context manager
            working_contents = self._context_manager.get_working_contents()

            # === LLM Call (streaming vs non-streaming) ===
            if self.is_main_agent:
                # Streaming call
                stream = self.llm_client.call_api_with_context_streaming(working_contents, api_config)
                was_interrupted, response = await self._streaming_processor.process_stream(stream, self._state)

                # Handle interruption
                if was_interrupted:
                    return await self._handle_stream_interruption(iteration)
            else:
                # Non-streaming call
                self._emit_activity("thinking", {"iteration": iteration})
                response = await self.llm_client.call_api_with_context(
                    context_contents=working_contents,
                    api_config=api_config,
                )
                self._emit_activity("llm_response", {"iteration": iteration})

            # === Check for tool calls ===
            if self.is_main_agent:
                has_tools = self._streaming_processor.has_tool_calls(response)
                tool_calls = self._streaming_processor.extract_tool_calls(response) if has_tools else []
            else:
                processor = self.llm_client._get_response_processor()
                tool_calls = processor.extract_tool_calls(response)
                has_tools = bool(tool_calls)

            # === No tool calls = done ===
            if not has_tools:
                if self.is_main_agent:
                    return await self._finalize_stream_response(response)
                else:
                    # Non-streaming: just return response
                    self._context_manager.add_response(response)
                    return response

            # === Has tool calls - process them ===
            self._context_manager.add_response(response)

            # MainAgent: Update streaming message with tool content
            if self.is_main_agent:
                await self._update_stream_tool_message(response, tool_calls)

            # === Check iteration limit BEFORE executing tools ===
            if iteration >= self.config.max_iterations:
                if self.is_main_agent:
                    await self._handle_stream_iteration_limit(tool_calls)
                    return response
                else:
                    # SubAgent: Execute pending tools, then request summary
                    return await self._handle_subagent_iteration_limit(tool_calls, iteration)

            # === Execute tools ===
            if self.is_main_agent:
                # MainAgent: Full tool execution with persistence
                tool_executor = ToolExecutor(
                    self.llm_client.tool_manager,
                    self.session_id,
                    notification_session_id=self._notification_session_id
                )
                execution_result = await tool_executor.execute_all(
                    tool_calls, self._message_id, self._context_manager.agent_profile
                )

                # Save to context and database
                await tool_executor.save_results_to_context(
                    tool_calls, execution_result.results, self._context_manager
                )
                await tool_executor.save_results_to_database(
                    tool_calls, execution_result.results
                )

                # Handle rejection
                if execution_result.rejected_tools:
                    await WebSocketNotificationService.send_streaming_update(
                        session_id=self.session_id,
                        message_id=self._message_id,
                        content=self._state.get_content_blocks(),
                        streaming=False,
                        interrupted=False
                    )
                    raise UserRejectionInterruption(self.session_id, execution_result.rejected_tools)

                # Check for user interrupt
                if self._status_monitor.is_user_interrupted():
                    print(f"[Agent] Tool calling interrupted by user at iteration {iteration}")
                    await WebSocketNotificationService.send_streaming_update(
                        session_id=self.session_id,
                        message_id=self._state.message_id,
                        content=self._state.get_content_blocks(),
                        streaming=False,
                        interrupted=True
                    )
                    return response
            else:
                # SubAgent: Simple tool execution with activity callbacks
                for tool_call in tool_calls:
                    self._emit_activity("tool_call_start", {
                        "tool": tool_call.get("name", "unknown"),
                        "args": tool_call.get("arguments", {}),
                    })

                    # Send SUBAGENT_TOOL_USE notification to frontend (SubAgent only)
                    if not self.is_main_agent and self._parent_tool_call_id:
                        await WebSocketNotificationService.send_subagent_tool_use(
                            session_id=self._notification_session_id,
                            parent_tool_call_id=self._parent_tool_call_id,
                            tool_call_id=tool_call.get("id", ""),
                            tool_name=tool_call.get("name", "unknown"),
                            tool_input=tool_call.get("arguments", {}),
                        )

                tool_executor = ToolExecutor(
                    tool_manager=self.llm_client.tool_manager,
                    session_id=self.session_id,
                    notification_session_id=self._notification_session_id,
                    send_tool_result_notifications=False,  # SubAgent: don't pollute MainAgent's stream
                )
                execution_result = await tool_executor.execute_all(
                    tool_calls=tool_calls,
                    message_id=f"agent_{self.session_id}_{iteration}",
                    agent_profile=self.config.tool_profile,
                )

                # Save results to context only (no database persistence for SubAgent)
                await tool_executor.save_results_to_context(
                    tool_calls, execution_result.results, self._context_manager,
                    inject_reminders=False
                )

                # Emit tool_call_end activities
                for tool_call, result in zip(tool_calls, execution_result.results):
                    self._emit_activity("tool_call_end", {
                        "tool": tool_call.get("name", "unknown"),
                        "status": result.get("status", "unknown") if result else "rejected",
                    })

            # Continue to next iteration
            iteration += 1

    async def _handle_stream_interruption(self, iteration: int) -> Any:
        """Handle user interruption during streaming."""
        from backend.infrastructure.websocket.notification_service import WebSocketNotificationService

        print(f"[Agent.stream] Interrupted by user at iteration {iteration}")

        self._status_monitor.set_interrupt_flag()

        # Construct partial response
        processor = self.llm_client._get_response_processor()
        partial_response = processor.construct_response_from_chunks(self._state.collected_chunks)

        # Delete placeholder message
        await MessageService().delete_message_async(self.session_id, self._state.message_id)

        # Send final update with interrupted=True
        await WebSocketNotificationService.send_streaming_update(
            session_id=self.session_id,
            message_id=self._state.message_id,
            content=self._state.get_content_blocks(),
            streaming=False,
            interrupted=True
        )

        # Trigger title generation
        trigger_title_generation(self.session_id, self.llm_client)

        return partial_response

    async def _finalize_stream_response(self, response: Any) -> Any:
        """Finalize streaming response without tool calls."""
        from backend.infrastructure.websocket.notification_service import WebSocketNotificationService

        # Add to context
        self._context_manager.add_response(response)

        # Format and save (format_for_storage always returns AssistantMessage with List content)
        final_message = self._streaming_processor.format_for_storage(response)
        content = final_message.content
        MessageService().update_assistant_message(self._message_id, content, self.session_id)

        usage = self._streaming_processor.extract_usage(self._state)

        # Send final update
        await WebSocketNotificationService.send_streaming_update(
            session_id=self.session_id,
            message_id=self._message_id,
            content=content,
            streaming=False,
            usage=usage
        )

        # Save usage
        if usage:
            save_token_usage(self.session_id, usage)

        # Trigger title generation
        trigger_title_generation(self.session_id, self.llm_client)

        return response

    async def _update_stream_tool_message(self, response: Any, tool_calls: list) -> None:
        """Update streaming message with tool call content."""
        from backend.infrastructure.websocket.notification_service import WebSocketNotificationService

        try:
            tool_call_message = self._streaming_processor.format_for_storage(response, tool_calls)
            content = tool_call_message.content
            MessageService().update_assistant_message(self._message_id, content, self.session_id)

            usage = self._streaming_processor.extract_usage(self._state)

            # Send streaming update and WAIT for completion
            await WebSocketNotificationService.send_streaming_update(
                session_id=self.session_id,
                message_id=self._message_id,
                content=content,
                streaming=True,
                usage=usage
            )

            if usage:
                save_token_usage(self.session_id, usage)

            # Trigger title generation
            trigger_title_generation(self.session_id, self.llm_client)

        except Exception as e:
            print(f"[Agent.stream] Failed to update streaming message: {e}")

    async def _handle_stream_iteration_limit(self, tool_calls: list) -> None:
        """Handle iteration limit reached in streaming mode."""
        from backend.infrastructure.mcp.utils.tool_result import success_response
        from backend.infrastructure.websocket.notification_service import WebSocketNotificationService

        print(f"[Agent.stream] Reached iteration limit ({self.config.max_iterations})")

        stop_message = (
            f"Tool execution stopped: Reached iteration limit "
            f"({self.config.max_iterations} iterations).\n\n"
            f"The task may be incomplete. You can provide a summary of what was accomplished.\n\n"
            f"Note: This is a safety mechanism to prevent infinite loops."
        )

        message_service = MessageService()
        for i, tool_call in enumerate(tool_calls):
            is_last_tool = (i == len(tool_calls) - 1)

            limit_result = success_response(
                stop_message,
                llm_content={"parts": [{"type": "text", "text": stop_message}]}
            )

            await self._context_manager.add_tool_result(
                tool_call['id'],
                tool_call['name'],
                limit_result,
                inject_reminders=is_last_tool
            )

            try:
                result_message_id = message_service.save_tool_result_message(
                    tool_call_id=tool_call['id'],
                    tool_name=tool_call['name'],
                    tool_result=limit_result,
                    session_id=self.session_id
                )

                await WebSocketNotificationService.send_tool_result_update(
                    session_id=self.session_id,
                    message_id=result_message_id,
                    tool_call_id=tool_call['id'],
                    tool_name=tool_call['name'],
                    tool_result=limit_result
                )
            except Exception as e:
                print(f"[Agent.stream] Failed to save iteration limit result: {e}")

    async def _handle_subagent_iteration_limit(self, tool_calls: list, iteration: int) -> Any:
        """Handle iteration limit for SubAgent: execute tools then request summary.

        Unlike MainAgent which just injects a stop message, SubAgent needs to:
        1. Execute the pending tool calls (they contain valuable information)
        2. Inject a "summarize your findings" instruction
        3. Make one final LLM call to get a text summary
        """
        from backend.infrastructure.websocket.notification_service import WebSocketNotificationService

        print(f"[SubAgent] Reached iteration limit ({self.config.max_iterations}), executing final tools and requesting summary")

        # Step 1: Execute pending tool calls
        for tool_call in tool_calls:
            self._emit_activity("tool_call_start", {
                "tool": tool_call.get("name", "unknown"),
                "args": tool_call.get("arguments", {}),
            })

            if self._parent_tool_call_id:
                await WebSocketNotificationService.send_subagent_tool_use(
                    session_id=self._notification_session_id,
                    parent_tool_call_id=self._parent_tool_call_id,
                    tool_call_id=tool_call.get("id", ""),
                    tool_name=tool_call.get("name", "unknown"),
                    tool_input=tool_call.get("arguments", {}),
                )

        tool_executor = ToolExecutor(
            tool_manager=self.llm_client.tool_manager,
            session_id=self.session_id,
            notification_session_id=self._notification_session_id,
            send_tool_result_notifications=False,
        )
        execution_result = await tool_executor.execute_all(
            tool_calls=tool_calls,
            message_id=f"agent_{self.session_id}_{iteration}_final",
            agent_profile=self.config.tool_profile,
        )

        # Save results to context
        await tool_executor.save_results_to_context(
            tool_calls, execution_result.results, self._context_manager,
            inject_reminders=False
        )

        for tool_call, result in zip(tool_calls, execution_result.results):
            self._emit_activity("tool_call_end", {
                "tool": tool_call.get("name", "unknown"),
                "status": result.get("status", "unknown") if result else "rejected",
            })

        # Step 2: Inject summary request as a user message
        summary_instruction = (
            "You have reached the iteration limit. Based on all the tool results above, "
            "please provide a comprehensive summary of your findings. "
            "Do NOT call any more tools - just summarize what you found."
        )
        self._context_manager.add_user_text(summary_instruction)

        # Step 3: Make final LLM call for summary (no tools)
        print(f"[SubAgent] Requesting final summary from LLM")
        final_response = await self.llm_client.call_api_with_context(
            context=self._context_manager.build_context(),
            tools=None,  # No tools - force text response
            debug=self.llm_client.debug,
        )

        return final_response

    def _emit_activity(self, event_type: str, data: Dict[str, Any]) -> None:
        """Emit activity event if callback is registered."""
        if not self.on_activity:
            return

        valid_types = [
            "started", "thinking", "tool_call_start", "tool_call_end",
            "llm_response", "completed", "error"
        ]
        if event_type not in valid_types:
            return

        activity = AgentActivity(
            agent_name=self.config.name,
            event_type=event_type,  # type: ignore
            data=data,
        )
        self.on_activity(activity)
