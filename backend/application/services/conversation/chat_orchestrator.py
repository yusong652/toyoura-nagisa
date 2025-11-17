"""
Chat Orchestrator Service - Application Layer Business Logic.

This service orchestrates conversation turns with recursive tool calling,
separating business logic from infrastructure concerns.
"""
from typing import Any, List, Dict, Optional, Tuple
from backend.domain.models.messages import BaseMessage
from backend.shared.exceptions import UserRejectionInterruption
from backend.application.services.conversation.models import (
    ConversationResult,
    StreamingState
)


class ChatOrchestrator:
    """
    Application layer service for orchestrating chat conversations.

    This service handles the business logic of:
    - Streaming response management
    - Recursive tool calling coordination
    - Message persistence and notifications
    - Business rules (iteration limits, interruptions)

    All infrastructure concerns (API calls, storage, notifications)
    are delegated to injected dependencies.
    """

    MAX_ITERATIONS = 64  # Business rule: maximum tool calling iterations

    def __init__(self, llm_client):
        """
        Initialize ChatOrchestrator with dependencies.

        Args:
            llm_client: LLMClientBase instance for LLM API interaction
        """
        self.llm_client = llm_client

        # Initialize services for message and title management
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

        This is the main entry point for conversation orchestration.
        It handles the complete flow from context preparation to final response.

        Args:
            session_id: Session identifier

        Returns:
            Tuple[BaseMessage, Optional[str]]: (final_message, streaming_message_id)

        Raises:
            UserRejectionInterruption: When user rejects tool execution
            Exception: On execution failures
        """
        try:
            # Execute recursive tool calling loop
            final_response = await self._recursive_tool_calling(
                session_id, iterations=0
            )

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

            # Get streaming message_id from context manager
            context_manager = self.llm_client.get_or_create_context_manager(session_id)
            streaming_message_id = getattr(context_manager, 'streaming_message_id', None)

            return final_message, streaming_message_id

        except UserRejectionInterruption:
            # User rejection is not an error - re-raise as-is
            raise

        except Exception as e:
            # Real error - log and clean up
            import traceback
            print(f"[ERROR] Exception in execute_conversation_turn: {e}")
            print(f"[ERROR] Traceback: {traceback.format_exc()}")

            # Clean up placeholder message on error
            context_manager = self.llm_client.get_or_create_context_manager(session_id)
            streaming_message_id = getattr(context_manager, 'streaming_message_id', None)
            if streaming_message_id:
                try:
                    await self.message_service.delete_message_async(session_id, streaming_message_id)
                    print(f"[DEBUG] Cleaned up placeholder message {streaming_message_id}")
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

        This method implements the core business logic for managing:
        - LLM API streaming
        - User interruptions
        - Tool call detection and execution
        - Iteration limits
        - Message persistence
        - WebSocket notifications

        Args:
            session_id: Session ID
            iterations: Current iteration count

        Returns:
            Any: Final LLM response in provider-native format

        Raises:
            UserRejectionInterruption: When user rejects any tool
        """
        # Get context manager
        context_manager = self.llm_client.get_or_create_context_manager(session_id)

        # Prepare complete context (delegate to LLM client)
        complete_context, api_config = await self.llm_client._prepare_complete_context(
            session_id=session_id
        )

        # Create placeholder message before streaming starts
        message_id = self.message_service.save_assistant_message([], session_id)

        # Send MESSAGE_CREATE notification
        from backend.infrastructure.websocket.notification_service import WebSocketNotificationService
        await WebSocketNotificationService.send_message_create(
            session_id, message_id, streaming=True
        )

        # Store message_id in context manager
        context_manager.streaming_message_id = message_id

        # Initialize streaming state
        state = StreamingState(message_id=message_id)

        # Stream LLM response with accumulated content updates
        async for chunk in self.llm_client.call_api_with_context_streaming(
            complete_context, api_config
        ):
            # Check for user interrupt via StatusMonitor
            from backend.infrastructure.monitoring import get_status_monitor
            status_monitor = get_status_monitor(session_id)
            if status_monitor.is_user_interrupted():
                return await self._handle_user_interruption(
                    session_id, state, iterations
                )

            # Add chunk to state
            state.add_chunk(chunk)

            # Send accumulated content update to WebSocket
            content_blocks = state.get_content_blocks()
            if content_blocks:
                await WebSocketNotificationService.send_streaming_update(
                    session_id=session_id,
                    message_id=message_id,
                    content=content_blocks,
                    streaming=True
                )

        # Ensure at least one streaming update was sent
        if not state.text_buffer and not state.thinking_buffer:
            await WebSocketNotificationService.send_streaming_update(
                session_id=session_id,
                message_id=message_id,
                content=[{"type": "text", "text": ""}],
                streaming=True
            )

        # Construct complete response from collected chunks
        processor = self.llm_client._get_response_processor()
        current_response = processor.construct_response_from_chunks(state.collected_chunks)

        # Check if response contains tool calls
        if not (processor and processor.has_tool_calls(current_response)):
            # No tool calls - finalize and return
            return await self._finalize_response(
                session_id, current_response, message_id, state
            )

        # Process tool calls
        return await self._handle_tool_calls(
            session_id, current_response, message_id, iterations, state
        )

    async def _handle_user_interruption(
        self,
        session_id: str,
        state: StreamingState,
        iterations: int
    ) -> Any:
        """
        Handle user interruption during streaming.

        Args:
            session_id: Session ID
            state: Current streaming state
            iterations: Current iteration count

        Returns:
            Any: Partial response with interrupt marker
        """
        print(f"[INFO] Streaming interrupted by user at iteration {iterations}")

        # Set interrupt flag via StatusMonitor (handles both in-memory and persistent storage)
        from backend.infrastructure.monitoring import get_status_monitor
        status_monitor = get_status_monitor(session_id)
        status_monitor.set_interrupt_flag()
        print(f"[DEBUG] Set interrupt flag via StatusMonitor - incomplete response will NOT be added to LLM context")

        # Build final content blocks for frontend display only
        content_blocks = state.get_content_blocks()
        print(f"[DEBUG] Content blocks (for frontend only): {content_blocks}")

        # Construct partial response for database storage and frontend display
        # This will NOT be added to LLM context to avoid misleading the model
        processor = self.llm_client._get_response_processor()
        partial_response = processor.construct_response_from_chunks(state.collected_chunks)

        # Debug: Check the constructed response content
        if hasattr(partial_response, 'choices') and partial_response.choices:
            message = partial_response.choices[0].message
            print(f"[DEBUG] Partial response content (not added to context): {repr(message.content)[:200]}")
            if hasattr(message, 'reasoning_content'):
                print(f"[DEBUG] Partial reasoning_content: {repr(message.reasoning_content)[:200]}")

        # DO NOT add to context manager - incomplete responses should not be in LLM context
        # The next user message will be merged if there are consecutive user messages
        print(f"[DEBUG] Skipping add_response() - keeping context clean for LLM")
        # DO NOT save to database - incomplete responses should not persist
        # User already saw the incomplete content in frontend (temporary display)
        # After restart, we don't want to load this incomplete message
        print(f"[DEBUG] Skipping database save - interrupted message won't persist in history")

        # Delete the placeholder message from database (it was created at streaming start)
        await self.message_service.delete_message_async(session_id, state.message_id)
        print(f"[DEBUG] Deleted placeholder message {state.message_id} from database")

        # Send final update with streaming=False (frontend will show interrupted state)
        from backend.infrastructure.websocket.notification_service import WebSocketNotificationService
        await WebSocketNotificationService.send_streaming_update(
            session_id=session_id,
            message_id=state.message_id,
            content=content_blocks,
            streaming=False
        )

        # Trigger title generation after user interruption
        # Note: Always attempted, TitleService checks history for suitable content
        # Application layer service orchestration - proper architecture
        import asyncio
        asyncio.create_task(
            self.title_service.try_generate_title_if_needed_async(
                session_id, self.llm_client
            )
        )

        return partial_response

    async def _finalize_response(
        self,
        session_id: str,
        response: Any,
        message_id: str,
        state: StreamingState
    ) -> Any:
        """
        Finalize response without tool calls.

        Args:
            session_id: Session ID
            response: LLM response
            message_id: Message ID
            state: Streaming state

        Returns:
            Any: Final response
        """
        # Add final response to context manager
        context_manager = self.llm_client.get_or_create_context_manager(session_id)
        context_manager.add_response(response)

        # Format response for storage and update message
        processor = self.llm_client._get_response_processor()
        final_message = processor.format_response_for_storage(response) if processor else None

        if final_message:
            content = final_message.content if isinstance(
                final_message.content, list
            ) else [{"type": "text", "text": str(final_message.content)}]
            self.message_service.update_assistant_message(message_id, content, session_id)

            # Extract token usage information from last streaming chunk's metadata
            usage = None
            if state.collected_chunks and len(state.collected_chunks) > 0:
                # Get last chunk and extract usage from its metadata
                last_chunk = state.collected_chunks[-1]

                if last_chunk.metadata and 'prompt_token_count' in last_chunk.metadata:
                    # Import max tokens constant
                    from backend.shared.constants.model_limits import DEFAULT_MAX_TOKENS

                    prompt_tokens = last_chunk.metadata.get('prompt_token_count', 0)
                    completion_tokens = last_chunk.metadata.get('candidates_token_count', 0)
                    total_tokens = last_chunk.metadata.get('total_token_count', 0)

                    usage = {
                        'prompt_tokens': prompt_tokens or 0,
                        'completion_tokens': completion_tokens or 0,
                        'total_tokens': total_tokens or 0,
                        'tokens_left': max(0, DEFAULT_MAX_TOKENS - (prompt_tokens or 0))
                    }

            # Send final streaming update with streaming=False
            from backend.infrastructure.websocket.notification_service import WebSocketNotificationService
            await WebSocketNotificationService.send_streaming_update(
                session_id=session_id,
                message_id=message_id,
                content=content,
                streaming=False,
                usage=usage
            )

            # Trigger title generation after response is saved (normal completion)
            # Note: Always attempted, TitleService searches history for text content
            # Application layer calling Application layer - clean architecture!
            import asyncio
            asyncio.create_task(
                self.title_service.try_generate_title_if_needed_async(
                    session_id, self.llm_client
                )
            )

        return response

    async def _handle_tool_calls(
        self,
        session_id: str,
        response: Any,
        message_id: str,
        iterations: int,
        state: StreamingState
    ) -> Any:
        """
        Handle tool calls in LLM response.

        Args:
            session_id: Session ID
            response: LLM response with tool calls
            message_id: Message ID
            iterations: Current iteration count
            state: Streaming state containing collected chunks

        Returns:
            Any: Response after tool execution and recursion

        Raises:
            UserRejectionInterruption: When user rejects any tool
        """
        # Add response to context manager
        context_manager = self.llm_client.get_or_create_context_manager(session_id)
        context_manager.add_response(response)

        # Extract tool calls
        processor = self.llm_client._get_response_processor()
        tool_calls = processor.extract_tool_calls(response) if processor else []

        # Update streaming message with complete content
        if processor:
            try:
                tool_call_message = processor.format_response_for_storage(
                    response, tool_calls
                )
                content = tool_call_message.content if isinstance(
                    tool_call_message.content, list
                ) else [{"type": "text", "text": str(tool_call_message.content)}]
                self.message_service.update_assistant_message(message_id, content, session_id)

                # Extract token usage information from last streaming chunk's metadata (tool calls path)
                usage = None
                if state.collected_chunks and len(state.collected_chunks) > 0:
                    # Get last chunk and extract usage from its metadata
                    last_chunk = state.collected_chunks[-1]

                    if last_chunk.metadata and 'prompt_token_count' in last_chunk.metadata:
                        # Import max tokens constant
                        from backend.shared.constants.model_limits import DEFAULT_MAX_TOKENS

                        prompt_tokens = last_chunk.metadata.get('prompt_token_count', 0)
                        completion_tokens = last_chunk.metadata.get('candidates_token_count', 0)
                        total_tokens = last_chunk.metadata.get('total_token_count', 0)

                        usage = {
                            'prompt_tokens': prompt_tokens or 0,
                            'completion_tokens': completion_tokens or 0,
                            'total_tokens': total_tokens or 0,
                            'tokens_left': max(0, DEFAULT_MAX_TOKENS - (prompt_tokens or 0))
                        }

                # Send final streaming update
                from backend.infrastructure.websocket.notification_service import WebSocketNotificationService
                await WebSocketNotificationService.send_streaming_update(
                    session_id=session_id,
                    message_id=message_id,
                    content=content,
                    streaming=False,
                    usage=usage
                )

                # Trigger title generation after message is saved
                # This runs in background without blocking tool execution
                # Note: Triggered even if message has no text content (only tool calls)
                # TitleService will search entire history for suitable text content
                # Application layer service orchestration - clean architecture!
                import asyncio
                asyncio.create_task(
                    self.title_service.try_generate_title_if_needed_async(
                        session_id, self.llm_client
                    )
                )
            except Exception as e:
                print(f"[WARNING] Failed to update streaming message: {e}")

        if not tool_calls:
            return response

        # Check iteration limit BEFORE executing tools
        if iterations >= self.MAX_ITERATIONS:
            await self._handle_iteration_limit(session_id, tool_calls)
            return response

        # Execute tools
        results = await self.llm_client.tool_manager.handle_multiple_function_calls(
            tool_calls,
            session_id or "",
            message_id
        )

        # Add results to context and check for rejections
        rejected_tools = []
        for i, (tool_call, result) in enumerate(zip(tool_calls, results)):
            is_last_tool = (i == len(tool_calls) - 1)

            await context_manager.add_tool_result(
                tool_call['id'],
                tool_call['name'],
                result,
                inject_reminders=is_last_tool
            )

            # Save tool result to database
            try:
                result_message_id = self.message_service.save_tool_result_message(
                    tool_call_id=tool_call['id'],
                    tool_name=tool_call['name'],
                    tool_result=result,
                    session_id=session_id
                )

                # Send WebSocket notification
                from backend.infrastructure.websocket.notification_service import WebSocketNotificationService
                await WebSocketNotificationService.send_message_saved(
                    session_id, result_message_id, 'user'
                )
            except Exception as e:
                print(f"[WARNING] Failed to save tool result: {e}")

            # Check for direct rejections
            if result.get('user_rejected', False):
                rejected_tools.append(tool_call['name'])

        # If any tool was directly rejected, interrupt immediately
        if rejected_tools:
            raise UserRejectionInterruption(session_id, rejected_tools)

        # Check for user interrupt before continuing recursion
        from backend.infrastructure.monitoring import get_status_monitor
        status_monitor = get_status_monitor(session_id)
        if status_monitor.is_user_interrupted():
            print(f"[INFO] Tool calling interrupted by user at iteration {iterations}")
            return response

        # Continue recursively
        return await self._recursive_tool_calling(session_id, iterations + 1)

    async def _handle_iteration_limit(
        self,
        session_id: str,
        tool_calls: List[Dict]
    ) -> None:
        """
        Handle iteration limit reached.

        Creates informative tool results and saves them to context/storage.

        Args:
            session_id: Session ID
            tool_calls: Tool calls that won't be executed
        """
        print(f"[INFO] Reached iteration limit ({self.MAX_ITERATIONS})")

        from backend.infrastructure.mcp.utils.tool_result import success_response
        stop_message = (
            f"Tool execution stopped: Reached iteration limit "
            f"({self.MAX_ITERATIONS} iterations).\n\n"
            f"The task may be incomplete. You can provide a summary of what was accomplished.\n\n"
            f"Note: This is a safety mechanism to prevent infinite loops."
        )

        context_manager = self.llm_client.get_or_create_context_manager(session_id)

        for i, tool_call in enumerate(tool_calls):
            is_last_tool = (i == len(tool_calls) - 1)

            # Create explanatory result
            limit_result = success_response(
                stop_message,
                llm_content={"parts": [{"type": "text", "text": stop_message}]}
            )

            # Add to context
            await context_manager.add_tool_result(
                tool_call['id'],
                tool_call['name'],
                limit_result,
                inject_reminders=is_last_tool
            )

            # Save to database
            try:
                message_id = self.message_service.save_tool_result_message(
                    tool_call_id=tool_call['id'],
                    tool_name=tool_call['name'],
                    tool_result=limit_result,
                    session_id=session_id
                )

                from backend.infrastructure.websocket.notification_service import WebSocketNotificationService
                await WebSocketNotificationService.send_message_saved(
                    session_id, message_id, 'user'
                )
            except Exception as e:
                print(f"[WARNING] Failed to save iteration limit result: {e}")
