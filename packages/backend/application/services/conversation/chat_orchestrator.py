"""
Chat Orchestrator Service - Application Layer Business Logic.

This service orchestrates conversation turns with recursive tool calling,
separating business logic from infrastructure concerns.

Refactored to delegate streaming, tool execution, and confirmation to specialized modules.
"""
from typing import Any, Optional, Tuple
from backend.domain.models.messages import BaseMessage
from backend.shared.exceptions import UserRejectionInterruption
from backend.application.services.conversation.models import StreamingState
from backend.application.services.conversation.streaming_processor import StreamingProcessor
from backend.application.services.conversation.tool_executor import ToolExecutor


class ChatOrchestrator:
    """
    Application layer service for orchestrating chat conversations.

    This service handles the business logic of:
    - Streaming response management (via StreamingProcessor)
    - Recursive tool calling coordination (via ToolExecutor)
    - Message persistence and notifications
    - Business rules (iteration limits, interruptions)

    All infrastructure concerns are delegated to injected dependencies.
    """

    MAX_ITERATIONS = 64  # Business rule: maximum tool calling iterations

    def __init__(self, llm_client):
        """
        Initialize ChatOrchestrator with dependencies.

        Args:
            llm_client: LLMClientBase instance for LLM API interaction
        """
        self.llm_client = llm_client

        # Initialize services
        from backend.application.services.contents import TitleService
        from backend.application.services.message_service import MessageService
        self.title_service = TitleService()
        self.message_service = MessageService()

    async def execute_conversation_turn(
        self,
        session_id: str
    ) -> Tuple[BaseMessage, Optional[str]]:
        """
        Execute one conversation turn with recursive tool calling.

        Args:
            session_id: Session identifier

        Returns:
            Tuple[BaseMessage, Optional[str]]: (final_message, streaming_message_id)

        Raises:
            UserRejectionInterruption: When user rejects tool execution
        """
        try:
            final_response = await self._recursive_tool_calling(session_id, iterations=0)

            # Format response for storage
            processor = self.llm_client._get_response_processor()
            if processor:
                final_message = processor.format_response_for_storage(final_response)
            else:
                from backend.domain.models.messages import AssistantMessage
                final_message = AssistantMessage(
                    role="assistant",
                    content=[{"type": "text", "text": "Response processing unavailable"}]
                )

            context_manager = self.llm_client.get_or_create_context_manager(session_id)
            streaming_message_id = getattr(context_manager, 'streaming_message_id', None)

            return final_message, streaming_message_id

        except UserRejectionInterruption:
            raise

        except Exception as e:
            import traceback
            print(f"[ERROR] Exception in execute_conversation_turn: {e}")
            print(f"[ERROR] Traceback: {traceback.format_exc()}")

            # Clean up placeholder message on error
            context_manager = self.llm_client.get_or_create_context_manager(session_id)
            streaming_message_id = getattr(context_manager, 'streaming_message_id', None)
            if streaming_message_id:
                try:
                    await self.message_service.delete_message_async(session_id, streaming_message_id)
                except Exception as cleanup_error:
                    print(f"[WARNING] Failed to clean up placeholder: {cleanup_error}")

            raise Exception(f"Conversation turn failed: {e}")

    async def _recursive_tool_calling(
        self,
        session_id: str,
        iterations: int = 0
    ) -> Any:
        """
        Recursive tool calling implementation with business orchestration.

        Args:
            session_id: Session ID
            iterations: Current iteration count

        Returns:
            Final LLM response in provider-native format

        Raises:
            UserRejectionInterruption: When user rejects any tool
        """
        # Track conversation turn for todo reminders
        from backend.infrastructure.monitoring import get_status_monitor
        status_monitor = get_status_monitor(session_id)
        if hasattr(status_monitor, 'todo_monitor'):
            status_monitor.todo_monitor.track_conversation_turn()

        # Get context manager and prepare context
        context_manager = self.llm_client.get_or_create_context_manager(session_id)
        agent_profile = getattr(context_manager, 'agent_profile', 'general')
        enable_memory = getattr(context_manager, 'enable_memory', True)

        # Build system prompt
        from backend.shared.utils.prompt.builder import build_system_prompt
        prompt_tool_schemas = await self.llm_client.tool_manager.get_schemas_for_system_prompt(
            session_id, agent_profile
        )
        system_prompt = await build_system_prompt(
            agent_profile=agent_profile,
            session_id=session_id,
            enable_memory=enable_memory,
            tool_schemas=prompt_tool_schemas
        )

        complete_context, api_config = await self.llm_client._prepare_complete_context(
            session_id=session_id,
            system_prompt=system_prompt
        )

        # Create placeholder message
        message_id = self.message_service.save_assistant_message([], session_id)

        # Send MESSAGE_CREATE notification
        from backend.infrastructure.websocket.notification_service import WebSocketNotificationService
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
            return await self._handle_user_interruption(session_id, state, iterations)

        # Check for tool calls
        if not streaming_processor.has_tool_calls(current_response):
            return await self._finalize_response(
                session_id, current_response, message_id, state, streaming_processor
            )

        # Handle tool calls
        return await self._handle_tool_calls(
            session_id, current_response, message_id, iterations, state, streaming_processor
        )

    async def _handle_user_interruption(
        self,
        session_id: str,
        state: StreamingState,
        iterations: int
    ) -> Any:
        """Handle user interruption during streaming."""
        print(f"[INFO] Streaming interrupted by user at iteration {iterations}")

        from backend.infrastructure.monitoring import get_status_monitor
        status_monitor = get_status_monitor(session_id)
        status_monitor.set_interrupt_flag()

        # Construct partial response (for return value only, not saved)
        processor = self.llm_client._get_response_processor()
        partial_response = processor.construct_response_from_chunks(state.collected_chunks)

        # Delete placeholder message
        await self.message_service.delete_message_async(session_id, state.message_id)

        # Send final update with interrupted=True
        from backend.infrastructure.websocket.notification_service import WebSocketNotificationService
        await WebSocketNotificationService.send_streaming_update(
            session_id=session_id,
            message_id=state.message_id,
            content=state.get_content_blocks(),
            streaming=False,
            interrupted=True
        )

        # Trigger title generation
        import asyncio
        asyncio.create_task(
            self.title_service.try_generate_title_if_needed_async(session_id, self.llm_client)
        )

        return partial_response

    async def _finalize_response(
        self,
        session_id: str,
        response: Any,
        message_id: str,
        state: StreamingState,
        streaming_processor: StreamingProcessor
    ) -> Any:
        """Finalize response without tool calls."""
        # Add to context
        context_manager = self.llm_client.get_or_create_context_manager(session_id)
        context_manager.add_response(response)

        # Format and save
        final_message = streaming_processor.format_for_storage(response)
        if final_message:
            content = final_message.content if isinstance(
                final_message.content, list
            ) else [{"type": "text", "text": str(final_message.content)}]
            self.message_service.update_assistant_message(message_id, content, session_id)

            usage = streaming_processor.extract_usage(state)

            # Send final update
            from backend.infrastructure.websocket.notification_service import WebSocketNotificationService
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
            import asyncio
            asyncio.create_task(
                self.title_service.try_generate_title_if_needed_async(session_id, self.llm_client)
            )

        return response

    async def _handle_tool_calls(
        self,
        session_id: str,
        response: Any,
        message_id: str,
        iterations: int,
        state: StreamingState,
        streaming_processor: StreamingProcessor
    ) -> Any:
        """Handle tool calls in LLM response."""
        # Add response to context
        context_manager = self.llm_client.get_or_create_context_manager(session_id)
        context_manager.add_response(response)

        # Extract tool calls
        tool_calls = streaming_processor.extract_tool_calls(response)

        # Update streaming message (await to ensure tool_use blocks are sent before tool_result_update)
        await self._update_tool_call_message(
            session_id, response, message_id, state, streaming_processor, tool_calls
        )

        if not tool_calls:
            return response

        # Check iteration limit
        if iterations >= self.MAX_ITERATIONS:
            await self._handle_iteration_limit(session_id, tool_calls, context_manager)
            return response

        # Execute tools
        tool_executor = ToolExecutor(
            self.llm_client.tool_manager,
            self.message_service,
            session_id
        )

        execution_result = await tool_executor.execute_all(
            tool_calls, message_id, context_manager
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
            from backend.infrastructure.websocket.notification_service import WebSocketNotificationService
            await WebSocketNotificationService.send_streaming_update(
                session_id=session_id,
                message_id=message_id,
                content=state.get_content_blocks(),
                streaming=False,
                interrupted=False
            )
            raise UserRejectionInterruption(session_id, execution_result.rejected_tools)

        # Check for user interrupt before recursion
        from backend.infrastructure.monitoring import get_status_monitor
        status_monitor = get_status_monitor(session_id)
        if status_monitor.is_user_interrupted():
            print(f"[INFO] Tool calling interrupted by user at iteration {iterations}")

            from backend.infrastructure.websocket.notification_service import WebSocketNotificationService
            await WebSocketNotificationService.send_streaming_update(
                session_id=session_id,
                message_id=state.message_id,
                content=state.get_content_blocks(),
                streaming=False,
                interrupted=True
            )
            return response

        # Continue recursively
        return await self._recursive_tool_calling(session_id, iterations + 1)

    async def _update_tool_call_message(
        self,
        session_id: str,
        response: Any,
        message_id: str,
        state: StreamingState,
        streaming_processor: StreamingProcessor,
        tool_calls: list
    ) -> None:
        """Update streaming message with tool call content."""
        from backend.infrastructure.websocket.notification_service import WebSocketNotificationService
        import asyncio

        try:
            tool_call_message = streaming_processor.format_for_storage(response, tool_calls)
            content = tool_call_message.content if isinstance(
                tool_call_message.content, list
            ) else [{"type": "text", "text": str(tool_call_message.content)}]
            self.message_service.update_assistant_message(message_id, content, session_id)

            usage = streaming_processor.extract_usage(state)

            # Send streaming update and WAIT for completion
            # This ensures tool_use blocks are sent to frontend BEFORE tool_result_update
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

            # Trigger title generation (can be async, doesn't need to wait)
            asyncio.create_task(
                self.title_service.try_generate_title_if_needed_async(session_id, self.llm_client)
            )

        except Exception as e:
            print(f"[WARNING] Failed to update streaming message: {e}")

    async def _handle_iteration_limit(
        self,
        session_id: str,
        tool_calls: list,
        context_manager: Any
    ) -> None:
        """Handle iteration limit reached."""
        print(f"[INFO] Reached iteration limit ({self.MAX_ITERATIONS})")

        from backend.infrastructure.mcp.utils.tool_result import success_response
        from backend.infrastructure.websocket.notification_service import WebSocketNotificationService

        stop_message = (
            f"Tool execution stopped: Reached iteration limit "
            f"({self.MAX_ITERATIONS} iterations).\n\n"
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
                result_message_id = self.message_service.save_tool_result_message(
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
                print(f"[WARNING] Failed to save iteration limit result: {e}")
