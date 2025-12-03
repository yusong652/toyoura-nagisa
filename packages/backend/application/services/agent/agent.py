"""
Agent - First-class citizen with active behavior.

This module provides the Agent class that encapsulates both
configuration (AgentDefinition) and behavior (run/stream methods).

Execution modes:
- run(): Non-streaming mode for SubAgents (no persistence, activity callbacks)
- stream(): Streaming mode for MainAgent (WebSocket, persistence, user interruption)
"""

import asyncio
import time
import uuid
from typing import Any, Callable, Dict, List, Optional

from backend.domain.models.agent import AgentActivity, AgentDefinition, AgentResult
from backend.domain.models.messages import AssistantMessage, BaseMessage, UserMessage
from backend.infrastructure.llm.base.client import LLMClientBase
from backend.application.services.conversation.tool_executor import ToolExecutor
from backend.application.services.conversation.models import StreamingState
from backend.application.services.conversation.streaming_processor import StreamingProcessor
from backend.application.services.message_service import MessageService


class Agent:
    """
    Agent with active behavior - first-class citizen in the system.

    An Agent encapsulates:
    - Configuration (AgentDefinition)
    - Behavior (run for non-streaming, stream for streaming)
    - State management (context, execution tracking)

    Usage:
        # Create agent instance
        explorer = Agent(PFC_EXPLORER, llm_client)

        # Execute task (non-streaming)
        result = await explorer.run({"objective": "Find ball syntax"})

        # Or with activity monitoring
        def on_activity(activity):
            print(f"[{activity.event_type}] {activity.data}")

        explorer = Agent(PFC_EXPLORER, llm_client, on_activity=on_activity)
        result = await explorer.run(inputs)
    """

    def __init__(
        self,
        definition: AgentDefinition,
        llm_client: LLMClientBase,
        on_activity: Optional[Callable[[AgentActivity], None]] = None,
    ):
        """
        Initialize Agent.

        Args:
            definition: Agent configuration (name, tool_profile, limits)
            llm_client: LLM client for API calls
            on_activity: Optional callback for activity events
        """
        self.definition = definition
        self.llm_client = llm_client
        self.on_activity = on_activity

        # Execution state (reset on each run)
        self._execution_id: Optional[str] = None

    @property
    def name(self) -> str:
        """Agent name from definition."""
        return self.definition.name

    @property
    def display_name(self) -> str:
        """Agent display name from definition."""
        return self.definition.display_name

    async def run(
        self,
        inputs: Dict[str, str],
        abort_signal: Optional[asyncio.Event] = None,
    ) -> AgentResult:
        """
        Execute agent task (non-streaming mode).

        This is the primary method for SubAgents. The agent will:
        1. Build context from inputs
        2. Call LLM
        3. Execute tools if requested
        4. Repeat until done or limits reached

        Args:
            inputs: Task inputs (e.g., {"objective": "...", "context": "..."})
            abort_signal: Optional event to signal abort

        Returns:
            AgentResult with execution outcome
        """
        # Generate unique execution ID for this run
        self._execution_id = str(uuid.uuid4())[:8]

        start_time = time.time()
        iteration = 0

        self._emit_activity("started", {"inputs": inputs})

        try:
            # Setup context manager for this execution
            context_manager = self.llm_client.get_or_create_context_manager(
                self._execution_id
            )
            context_manager.agent_profile = self.definition.tool_profile
            context_manager.enable_memory = self.definition.enable_memory

            # Build initial user message from inputs (task from parent agent)
            initial_message = UserMessage(content=self._build_prompt_content(inputs))
            await context_manager.add_user_message(initial_message)

            # Build system prompt using infrastructure
            # Uses definition.name as the prompt profile to load {name}.md
            from backend.shared.utils.prompt.builder import build_system_prompt
            prompt_tool_schemas = await self.llm_client.tool_manager.get_schemas_for_system_prompt(
                self._execution_id, self.definition.tool_profile
            )
            system_prompt = await build_system_prompt(
                agent_profile=self.definition.name,  # name doubles as prompt profile
                session_id=self._execution_id,
                enable_memory=self.definition.enable_memory,
                tool_schemas=prompt_tool_schemas
            )

            # Get api_config using infrastructure layer
            messages, api_config = await self.llm_client._prepare_complete_context(
                session_id=self._execution_id,
                system_prompt=system_prompt
            )

            # Execution loop
            while iteration < self.definition.max_iterations:
                # Check abort signal
                if abort_signal and abort_signal.is_set():
                    return AgentResult(
                        status="aborted",
                        iterations_used=iteration,
                        execution_time_seconds=time.time() - start_time,
                    )

                # Get fresh messages from context_manager
                messages = context_manager.get_working_contents()

                # LLM call
                self._emit_activity("thinking", {"iteration": iteration})
                response = await self.llm_client.call_api_with_context(
                    context_contents=messages,
                    api_config=api_config,
                )
                self._emit_activity("llm_response", {"iteration": iteration})

                # Extract response content and tool calls
                response_text, tool_calls = self._parse_response(response)

                # No tool calls = done
                if not tool_calls:
                    # Wrap response text in AssistantMessage for unified handling
                    final_message = AssistantMessage(
                        role="assistant",
                        content=[{"type": "text", "text": response_text}]
                    )
                    return AgentResult(
                        status="success",
                        message=final_message,
                        iterations_used=iteration + 1,
                        execution_time_seconds=time.time() - start_time,
                    )

                # Add assistant response to context
                context_manager.add_response(response)

                # Execute tools and add results to context
                tool_results = await self._execute_tools(tool_calls, iteration)
                for tool_call, result in zip(tool_calls, tool_results):
                    if result is not None:
                        await context_manager.add_tool_result(
                            tool_call_id=tool_call.get("id", ""),
                            tool_name=tool_call.get("name", ""),
                            result=result,
                            inject_reminders=False
                        )

                iteration += 1

            # Max iterations reached
            return AgentResult(
                status="max_iterations",
                iterations_used=iteration,
                execution_time_seconds=time.time() - start_time,
            )

        except Exception as e:
            self._emit_activity("error", {"error": str(e)})
            # Wrap error in AssistantMessage for unified handling
            error_message = AssistantMessage(
                role="assistant",
                content=[{"type": "text", "text": f"Error: {str(e)}"}]
            )
            return AgentResult(
                status="error",
                message=error_message,
                iterations_used=iteration,
                execution_time_seconds=time.time() - start_time,
            )

        finally:
            self._emit_activity("completed", {
                "iterations": iteration,
                "elapsed": time.time() - start_time,
            })

    async def stream(
        self,
        session_id: str,
        instruction: Optional[str] = None,
    ) -> AgentResult:
        """
        Execute agent task (streaming mode) for MainAgent.

        This method provides full streaming support:
        - Streaming LLM calls with WebSocket notifications
        - Message persistence to database
        - User interruption support
        - Recursive tool calling

        Args:
            session_id: Session ID (uses existing context from session)
            instruction: Optional instruction to inject if context is empty

        Returns:
            AgentResult with execution outcome

        Raises:
            UserRejectionInterruption: When user rejects tool execution
        """
        from backend.shared.exceptions import UserRejectionInterruption

        start_time = time.time()

        try:
            # Inject instruction if provided and context needs it
            if instruction:
                context_manager = self.llm_client.get_or_create_context_manager(session_id)
                if self._should_inject_instruction(context_manager):
                    user_message = UserMessage(content=instruction)
                    await context_manager.add_user_message(user_message)

            final_response = await self._recursive_stream(session_id, iterations=0)

            # Format response for storage
            processor = self.llm_client._get_response_processor()
            if processor:
                final_message = processor.format_response_for_storage(final_response)
            else:
                final_message = AssistantMessage(
                    role="assistant",
                    content=[{"type": "text", "text": "Response processing unavailable"}]
                )

            context_manager = self.llm_client.get_or_create_context_manager(session_id)
            streaming_message_id = getattr(context_manager, 'streaming_message_id', None)

            return AgentResult(
                status="success",
                message=final_message,
                message_id=streaming_message_id,
                execution_time_seconds=time.time() - start_time,
            )

        except UserRejectionInterruption:
            raise

        except Exception as e:
            import traceback
            print(f"[Agent.stream] Exception: {e}")
            print(f"[Agent.stream] Traceback: {traceback.format_exc()}")

            # Clean up placeholder message on error
            context_manager = self.llm_client.get_or_create_context_manager(session_id)
            streaming_message_id = getattr(context_manager, 'streaming_message_id', None)
            if streaming_message_id:
                try:
                    message_service = MessageService()
                    await message_service.delete_message_async(session_id, streaming_message_id)
                except Exception as cleanup_error:
                    print(f"[Agent.stream] Failed to clean up placeholder: {cleanup_error}")

            raise Exception(f"Agent streaming failed: {e}")

    def _should_inject_instruction(self, context_manager) -> bool:
        """Check if instruction should be injected (context is empty or no user message)."""
        contents = context_manager.get_working_contents()
        if not contents:
            return True
        # Check if last message is already a user message
        last_msg = contents[-1]
        return last_msg.get('role') != 'user'

    async def execute(
        self,
        instruction: Optional[str] = None,
        *,
        session_id: Optional[str] = None,
        context: Optional[str] = None,
        abort_signal: Optional[asyncio.Event] = None,
    ) -> AgentResult:
        """
        Unified agent execution entry point (facade).

        Dispatches to run() or stream() based on session_id.
        Future: Will be unified into a single execution path.

        Args:
            instruction: Task instruction for the agent
            session_id: If provided, uses streaming mode
            context: Additional context (SubAgent mode only)
            abort_signal: Optional abort signal

        Returns:
            AgentResult with execution outcome
        """
        if session_id is not None:
            return await self.stream(session_id, instruction)
        else:
            if instruction is None:
                raise ValueError("instruction is required for SubAgent execution")
            inputs = {"task": instruction}
            if context:
                inputs["context"] = context
            return await self.run(inputs=inputs, abort_signal=abort_signal)

    async def _recursive_stream(
        self,
        session_id: str,
        iterations: int = 0
    ) -> Any:
        """
        Recursive streaming implementation with tool calling.
        """
        from backend.infrastructure.websocket.notification_service import WebSocketNotificationService
        from backend.infrastructure.monitoring import get_status_monitor

        # Track conversation turn for todo reminders
        status_monitor = get_status_monitor(session_id)
        if hasattr(status_monitor, 'todo_monitor'):
            status_monitor.todo_monitor.track_conversation_turn()

        # Get context manager
        context_manager = self.llm_client.get_or_create_context_manager(session_id)

        # Build system prompt
        from backend.shared.utils.prompt.builder import build_system_prompt
        prompt_tool_schemas = await self.llm_client.tool_manager.get_schemas_for_system_prompt(
            session_id, context_manager.agent_profile
        )
        system_prompt = await build_system_prompt(
            agent_profile=context_manager.agent_profile,
            session_id=session_id,
            enable_memory=context_manager.enable_memory,
            tool_schemas=prompt_tool_schemas
        )

        complete_context, api_config = await self.llm_client._prepare_complete_context(
            session_id=session_id,
            system_prompt=system_prompt
        )

        # Create placeholder message
        message_service = MessageService()
        message_id = message_service.save_assistant_message([], session_id)

        # Send MESSAGE_CREATE notification
        await WebSocketNotificationService.send_message_create(
            session_id, message_id, streaming=True
        )

        context_manager.streaming_message_id = message_id
        state = StreamingState(message_id=message_id)

        # Create streaming processor
        streaming_processor = StreamingProcessor(self.llm_client, session_id)

        # Process stream
        stream = self.llm_client.call_api_with_context_streaming(complete_context, api_config)
        was_interrupted, current_response = await streaming_processor.process_stream(stream, state)

        if was_interrupted:
            return await self._handle_stream_interruption(
                session_id, state, iterations, message_service
            )

        # Check for tool calls
        if not streaming_processor.has_tool_calls(current_response):
            return await self._finalize_stream_response(
                session_id, current_response, message_id, state, streaming_processor, message_service
            )

        # Handle tool calls
        return await self._handle_stream_tool_calls(
            session_id, current_response, message_id, iterations, state, streaming_processor, message_service
        )

    async def _handle_stream_interruption(
        self,
        session_id: str,
        state: StreamingState,
        iterations: int,
        message_service: MessageService
    ) -> Any:
        """Handle user interruption during streaming."""
        from backend.infrastructure.websocket.notification_service import WebSocketNotificationService
        from backend.infrastructure.monitoring import get_status_monitor

        print(f"[Agent.stream] Interrupted by user at iteration {iterations}")

        status_monitor = get_status_monitor(session_id)
        status_monitor.set_interrupt_flag()

        # Construct partial response
        processor = self.llm_client._get_response_processor()
        if processor:
            partial_response = processor.construct_response_from_chunks(state.collected_chunks)
        else:
            partial_response = None

        # Delete placeholder message
        await message_service.delete_message_async(session_id, state.message_id)

        # Send final update with interrupted=True
        await WebSocketNotificationService.send_streaming_update(
            session_id=session_id,
            message_id=state.message_id,
            content=state.get_content_blocks(),
            streaming=False,
            interrupted=True
        )

        # Trigger title generation
        from backend.application.services.contents import TitleService
        title_service = TitleService()
        asyncio.create_task(
            title_service.try_generate_title_if_needed_async(session_id, self.llm_client)
        )

        return partial_response

    async def _finalize_stream_response(
        self,
        session_id: str,
        response: Any,
        message_id: str,
        state: StreamingState,
        streaming_processor: StreamingProcessor,
        message_service: MessageService
    ) -> Any:
        """Finalize streaming response without tool calls."""
        from backend.infrastructure.websocket.notification_service import WebSocketNotificationService

        # Add to context
        context_manager = self.llm_client.get_or_create_context_manager(session_id)
        context_manager.add_response(response)

        # Format and save
        final_message = streaming_processor.format_for_storage(response)
        if final_message:
            content = final_message.content if isinstance(
                final_message.content, list
            ) else [{"type": "text", "text": str(final_message.content)}]
            message_service.update_assistant_message(message_id, content, session_id)

            usage = streaming_processor.extract_usage(state)

            # Send final update
            await WebSocketNotificationService.send_streaming_update(
                session_id=session_id,
                message_id=message_id,
                content=content,
                streaming=False,
                usage=usage
            )

            # Save usage
            if usage:
                from backend.infrastructure.storage.session_manager import save_token_usage
                save_token_usage(session_id, usage)

            # Trigger title generation
            from backend.application.services.contents import TitleService
            title_service = TitleService()
            asyncio.create_task(
                title_service.try_generate_title_if_needed_async(session_id, self.llm_client)
            )

        return response

    async def _handle_stream_tool_calls(
        self,
        session_id: str,
        response: Any,
        message_id: str,
        iterations: int,
        state: StreamingState,
        streaming_processor: StreamingProcessor,
        message_service: MessageService
    ) -> Any:
        """Handle tool calls in streaming response."""
        from backend.infrastructure.websocket.notification_service import WebSocketNotificationService
        from backend.infrastructure.monitoring import get_status_monitor
        from backend.shared.exceptions import UserRejectionInterruption

        # Add response to context
        context_manager = self.llm_client.get_or_create_context_manager(session_id)
        context_manager.add_response(response)

        # Extract tool calls
        tool_calls = streaming_processor.extract_tool_calls(response)

        # Update streaming message (await to ensure tool_use blocks are sent before tool_result_update)
        await self._update_stream_tool_message(
            session_id, response, message_id, state, streaming_processor, tool_calls, message_service
        )

        if not tool_calls:
            return response

        # Check iteration limit
        if iterations >= self.definition.max_iterations:
            await self._handle_stream_iteration_limit(session_id, tool_calls, context_manager, message_service)
            return response

        # Execute tools
        tool_executor = ToolExecutor(
            self.llm_client.tool_manager,
            message_service,
            session_id
        )

        execution_result = await tool_executor.execute_all(
            tool_calls, message_id, context_manager.agent_profile
        )

        # Save to context and database
        await tool_executor.save_results_to_context(
            tool_calls, execution_result.results, context_manager
        )
        await tool_executor.save_results_to_database(
            tool_calls, execution_result.results
        )

        # Handle rejection
        if execution_result.rejected_tools:
            await WebSocketNotificationService.send_streaming_update(
                session_id=session_id,
                message_id=message_id,
                content=state.get_content_blocks(),
                streaming=False,
                interrupted=False
            )
            raise UserRejectionInterruption(session_id, execution_result.rejected_tools)

        # Check for user interrupt before recursion
        status_monitor = get_status_monitor(session_id)
        if status_monitor.is_user_interrupted():
            print(f"[Agent.stream] Tool calling interrupted by user at iteration {iterations}")

            await WebSocketNotificationService.send_streaming_update(
                session_id=session_id,
                message_id=state.message_id,
                content=state.get_content_blocks(),
                streaming=False,
                interrupted=True
            )
            return response

        # Continue recursively
        return await self._recursive_stream(session_id, iterations + 1)

    async def _update_stream_tool_message(
        self,
        session_id: str,
        response: Any,
        message_id: str,
        state: StreamingState,
        streaming_processor: StreamingProcessor,
        tool_calls: list,
        message_service: MessageService
    ) -> None:
        """Update streaming message with tool call content."""
        from backend.infrastructure.websocket.notification_service import WebSocketNotificationService

        try:
            tool_call_message = streaming_processor.format_for_storage(response, tool_calls)
            content = tool_call_message.content if isinstance(
                tool_call_message.content, list
            ) else [{"type": "text", "text": str(tool_call_message.content)}]
            message_service.update_assistant_message(message_id, content, session_id)

            usage = streaming_processor.extract_usage(state)

            # Send streaming update and WAIT for completion
            await WebSocketNotificationService.send_streaming_update(
                session_id=session_id,
                message_id=message_id,
                content=content,
                streaming=True,
                usage=usage
            )

            if usage:
                from backend.infrastructure.storage.session_manager import save_token_usage
                save_token_usage(session_id, usage)

            # Trigger title generation
            from backend.application.services.contents import TitleService
            title_service = TitleService()
            asyncio.create_task(
                title_service.try_generate_title_if_needed_async(session_id, self.llm_client)
            )

        except Exception as e:
            print(f"[Agent.stream] Failed to update streaming message: {e}")

    async def _handle_stream_iteration_limit(
        self,
        session_id: str,
        tool_calls: list,
        context_manager: Any,
        message_service: MessageService
    ) -> None:
        """Handle iteration limit reached in streaming mode."""
        from backend.infrastructure.mcp.utils.tool_result import success_response
        from backend.infrastructure.websocket.notification_service import WebSocketNotificationService

        print(f"[Agent.stream] Reached iteration limit ({self.definition.max_iterations})")

        stop_message = (
            f"Tool execution stopped: Reached iteration limit "
            f"({self.definition.max_iterations} iterations).\n\n"
            f"The task may be incomplete. You can provide a summary of what was accomplished.\n\n"
            f"Note: This is a safety mechanism to prevent infinite loops."
        )

        for i, tool_call in enumerate(tool_calls):
            is_last_tool = (i == len(tool_calls) - 1)

            limit_result = success_response(
                stop_message,
                llm_content={"parts": [{"type": "text", "text": stop_message}]}
            )

            await context_manager.add_tool_result(
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
                    session_id=session_id
                )

                await WebSocketNotificationService.send_tool_result_update(
                    session_id=session_id,
                    message_id=result_message_id,
                    tool_call_id=tool_call['id'],
                    tool_name=tool_call['name'],
                    tool_result=limit_result
                )
            except Exception as e:
                print(f"[Agent.stream] Failed to save iteration limit result: {e}")

    def _build_prompt_content(self, inputs: Dict[str, str]) -> str:
        """
        Build prompt content from inputs for initial user message.

        Args:
            inputs: Task inputs

        Returns:
            Prompt string for the initial user message
        """
        if len(inputs) == 1:
            return str(list(inputs.values())[0])

        parts = []
        for key, value in inputs.items():
            parts.append(f"## {key.replace('_', ' ').title()}\n{value}")

        return "\n\n".join(parts)

    def _parse_response(self, response: Any) -> tuple[str, List[Dict]]:
        """
        Parse LLM response to extract text and tool calls.

        Uses the provider's response processor for format-agnostic parsing.
        """
        processor = self.llm_client._get_response_processor()
        if not processor:
            return "", []

        try:
            text_content = processor.extract_text_content(response)
            tool_calls = processor.extract_tool_calls(response)
            return text_content, tool_calls
        except Exception as e:
            print(f"[Agent] Error parsing response: {e}")
            return "", []

    async def _execute_tools(
        self,
        tool_calls: List[Dict],
        iteration: int
    ) -> List[Optional[Dict[str, Any]]]:
        """
        Execute tool calls.

        Args:
            tool_calls: List of tool call dicts
            iteration: Current iteration number

        Returns:
            List of tool results
        """
        # Emit activity for each tool
        for tool_call in tool_calls:
            self._emit_activity("tool_call_start", {
                "tool": tool_call.get("name", "unknown"),
                "args": tool_call.get("arguments", {}),
            })

        # Create ToolExecutor
        tool_executor = ToolExecutor(
            tool_manager=self.llm_client.tool_manager,
            message_service=MessageService(),
            session_id=self._execution_id or "",
        )

        # Generate message ID for tool execution
        message_id = f"agent_{self._execution_id}_{iteration}"

        # Execute all tools
        execution_result = await tool_executor.execute_all(
            tool_calls=tool_calls,
            message_id=message_id,
            agent_profile=self.definition.tool_profile,
        )

        # Emit completion activity for each tool
        for i, tool_call in enumerate(tool_calls):
            result = execution_result.results[i]
            status = result.get("status", "unknown") if result else "rejected"
            self._emit_activity("tool_call_end", {
                "tool": tool_call.get("name", "unknown"),
                "status": status,
            })

        return execution_result.results

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
            agent_name=self.definition.name,
            event_type=event_type,  # type: ignore
            data=data,
        )
        self.on_activity(activity)
