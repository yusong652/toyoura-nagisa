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
        # Track each LLM interaction for periodic todo reminders (Claude Code style)
        # This includes both initial user messages and tool calling rounds
        from backend.infrastructure.monitoring import get_status_monitor
        status_monitor = get_status_monitor(session_id)
        if hasattr(status_monitor, 'todo_monitor'):
            status_monitor.todo_monitor.track_conversation_turn()

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

        # Send final update with streaming=False and interrupted=True
        # Frontend uses interrupted flag to determine state handling (not local ref)
        from backend.infrastructure.websocket.notification_service import WebSocketNotificationService
        await WebSocketNotificationService.send_streaming_update(
            session_id=session_id,
            message_id=state.message_id,
            content=content_blocks,
            streaming=False,
            interrupted=True
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

            # Save token usage to persistent storage
            if usage:
                from backend.infrastructure.storage.session_manager import save_token_usage
                save_token_usage(session_id, usage)

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

                # Send streaming update with tool_use blocks (before tool execution)
                # This ensures frontend renders ToolUseBlock components BEFORE confirmation requests arrive
                # Note: streaming=True because tool execution is about to start
                from backend.infrastructure.websocket.notification_service import WebSocketNotificationService
                await WebSocketNotificationService.send_streaming_update(
                    session_id=session_id,
                    message_id=message_id,
                    content=content,
                    streaming=True,  # Tools are about to execute
                    usage=usage
                )

                # Save token usage to persistent storage
                if usage:
                    from backend.infrastructure.storage.session_manager import save_token_usage
                    save_token_usage(session_id, usage)

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

        # Execute tools with classification and cascade blocking
        # Non-confirmation tools execute first, confirmation tools have cascade blocking
        from backend.infrastructure.mcp.utils.tool_result import error_response
        from backend.infrastructure.websocket.notification_service import WebSocketNotificationService

        # Step 1: Classify tools into confirm and non-confirm categories
        non_confirm_tools = []  # (original_index, tool_call)
        confirm_tools = []      # (original_index, tool_call)
        for i, tool_call in enumerate(tool_calls):
            tool_name = tool_call.get('name', 'unknown')
            if self.llm_client.tool_manager._requires_user_confirmation(tool_name, {}):
                confirm_tools.append((i, tool_call))
            else:
                non_confirm_tools.append((i, tool_call))

        # Step 2: Prepare results storage (indexed by original order)
        results: List[Optional[Dict]] = [None] * len(tool_calls)
        rejected_tools: List[str] = []

        # Step 3: Execute non-confirmation tools first (not affected by cascade blocking)
        for original_index, tool_call in non_confirm_tools:
            tool_name = tool_call.get('name', 'unknown')

            # Execute single tool via infrastructure layer
            result = await self.llm_client.tool_manager.handle_function_call(
                tool_call, session_id or "", message_id
            )
            results[original_index] = result

            # Send WebSocket update immediately (real-time notification)
            await self._notify_tool_result(session_id, tool_call, result, context_manager)

        # Step 4: Request confirmations for all confirm tools (with cascade blocking)
        # Phase 4a: Collect confirmations first
        confirmations: Dict[str, tuple[bool, Optional[str]]] = {}  # tool_call_id -> (approved, user_message)
        user_rejected_tool = None

        for original_index, tool_call in confirm_tools:
            tool_name = tool_call.get('name', 'unknown')
            tool_id = tool_call.get('id', '')

            if user_rejected_tool is not None:
                # Previous tool was rejected, cascade block this one
                confirmations[tool_id] = (False, f"Cascade blocked due to {user_rejected_tool} rejection")
            else:
                # Request user confirmation
                approved, user_message = await self._request_tool_confirmation(
                    tool_call, session_id or "", message_id
                )
                confirmations[tool_id] = (approved, user_message)

                if not approved:
                    user_rejected_tool = tool_name
                    rejected_tools.append(tool_name)

        # Phase 4b: Execute confirmed tools or generate rejection responses
        from backend.infrastructure.mcp.utils.tool_result import user_rejected_response

        for original_index, tool_call in confirm_tools:
            tool_name = tool_call.get('name', 'unknown')
            tool_id = tool_call.get('id', '')
            approved, user_message = confirmations[tool_id]

            if approved:
                # User approved - execute the tool
                result = await self.llm_client.tool_manager.handle_function_call(
                    tool_call, session_id or "", message_id
                )
            elif tool_name in rejected_tools:
                # User directly rejected this tool
                result = user_rejected_response(
                    user_message=user_message or f"User rejected {tool_name}"
                )
                result["user_rejected"] = True
            else:
                # Cascade blocked (not the first rejection)
                cascade_message = (
                    f"The user doesn't want to take this action right now. "
                    f"Skipping {tool_name} due to previous rejection. "
                    f"STOP what you are doing and wait for the user to tell you how to proceed."
                )
                result = error_response(cascade_message)
                result["cascade_blocked"] = True

            results[original_index] = result

            # Send WebSocket update (real-time notification)
            await self._notify_tool_result(session_id, tool_call, result, context_manager)

        # Step 5: Save and add results to context in ORIGINAL order
        # This ensures database persistence matches LLM tool call order
        for i, tool_call in enumerate(tool_calls):
            is_last_tool = (i == len(tool_calls) - 1)

            # Save to database in original order
            result = results[i]
            if result is not None:
                await self._save_tool_result(session_id, tool_call, result)

            # Add to context in original order
            await context_manager.add_tool_result(
                tool_call['id'],
                tool_call['name'],
                results[i],
                inject_reminders=is_last_tool
            )

        # If any tool was directly rejected, send streaming end notification and interrupt
        if rejected_tools:
            # Send streaming=False to notify frontend that pending state should end
            # This stops the blinking animation on tool call blocks
            from backend.infrastructure.websocket.notification_service import WebSocketNotificationService
            await WebSocketNotificationService.send_streaming_update(
                session_id=session_id,
                message_id=message_id,
                content=state.get_content_blocks(),
                streaming=False,
                interrupted=False  # Not a user interrupt, just rejection completion
            )
            raise UserRejectionInterruption(session_id, rejected_tools)

        # Check for user interrupt before continuing recursion
        from backend.infrastructure.monitoring import get_status_monitor
        status_monitor = get_status_monitor(session_id)
        if status_monitor.is_user_interrupted():
            print(f"[INFO] Tool calling interrupted by user at iteration {iterations}")

            # Send streaming=false, interrupted=true to frontend
            # This notifies frontend to clean up state without committing to history
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

    async def _notify_tool_result(
        self,
        session_id: str,
        tool_call: Dict,
        result: Dict,
        context_manager: Any
    ) -> None:
        """
        Send WebSocket notification for tool result (real-time update).

        Args:
            session_id: Session ID
            tool_call: Tool call dict with 'id' and 'name'
            result: Tool execution result
            context_manager: Context manager for agent profile
        """
        from backend.infrastructure.websocket.notification_service import WebSocketNotificationService

        tool_name = tool_call.get('name', 'unknown')

        try:
            # Send real-time update to frontend
            await WebSocketNotificationService.send_tool_result_update(
                session_id=session_id,
                message_id=tool_call['id'],
                tool_call_id=tool_call['id'],
                tool_name=tool_name,
                tool_result=result
            )
        except Exception as e:
            print(f"[WARNING] Failed to send tool result notification: {e}")

        # Send todo update if todo_write was called
        if tool_name == 'todo_write':
            try:
                from backend.application.services.todo_service import get_todo_service
                agent_profile = getattr(context_manager, 'agent_profile', 'general')
                todo_service = get_todo_service()
                current_todo = await todo_service.get_current_todo(agent_profile, session_id)
                await WebSocketNotificationService.send_todo_update(session_id, current_todo)
            except Exception as e:
                print(f"[WARNING] Failed to send todo update notification: {e}")

    async def _save_tool_result(
        self,
        session_id: str,
        tool_call: Dict,
        result: Dict
    ) -> Optional[str]:
        """
        Save tool result to database (persistence in original order).

        Args:
            session_id: Session ID
            tool_call: Tool call dict with 'id' and 'name'
            result: Tool execution result

        Returns:
            Message ID if saved successfully, None otherwise
        """
        tool_name = tool_call.get('name', 'unknown')

        try:
            result_message_id = self.message_service.save_tool_result_message(
                tool_call_id=tool_call['id'],
                tool_name=tool_name,
                tool_result=result,
                session_id=session_id
            )
            return result_message_id
        except Exception as e:
            print(f"[WARNING] Failed to save tool result: {e}")
            return None

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

                # Send TOOL_RESULT_UPDATE for real-time display
                from backend.infrastructure.websocket.notification_service import WebSocketNotificationService
                await WebSocketNotificationService.send_tool_result_update(
                    session_id=session_id,
                    message_id=message_id,
                    tool_call_id=tool_call['id'],
                    tool_name=tool_call['name'],
                    tool_result=limit_result
                )
            except Exception as e:
                print(f"[WARNING] Failed to save iteration limit result: {e}")

    async def _request_tool_confirmation(
        self,
        tool_call: Dict,
        session_id: str,
        message_id: str
    ) -> tuple[bool, Optional[str]]:
        """
        Request user confirmation for a tool execution.

        This method handles the confirmation request flow for tools that require
        user approval (bash, edit, write, pfc_execute_task).

        Args:
            tool_call: Tool call dictionary with 'id', 'name', 'arguments'
            session_id: Session ID for the confirmation request
            message_id: ID of the message containing this tool call

        Returns:
            tuple[bool, Optional[str]]: (approved, user_message)
        """
        from pathlib import Path
        from backend.application.services.notifications.tool_confirmation_service import get_tool_confirmation_service

        tool_name = tool_call.get('name', '')
        tool_args = tool_call.get('arguments', {})
        tool_id = tool_call.get('id', '')

        confirmation_service = get_tool_confirmation_service()
        if not confirmation_service:
            print(f"[ChatOrchestrator] Confirmation service not available, auto-rejecting {tool_name}")
            return (False, "Confirmation service not available")

        # Initialize confirmation parameters
        confirmation_type: Optional[str] = None
        file_name_param: Optional[str] = None
        file_path_param: Optional[str] = None
        file_diff: Optional[str] = None
        original_content: Optional[str] = None
        new_content: Optional[str] = None

        # Extract command and prepare confirmation info based on tool type
        if tool_name == "bash":
            command = tool_args.get("command", "")
            description = tool_args.get("description", None)
            confirmation_type = "exec"
            if not description:
                description = f"Execute bash command: {command}"

        elif tool_name == "edit":
            file_path = tool_args.get("file_path", "unknown")
            command = f"Edit file: {file_path}"
            description = tool_args.get("description", None)
            confirmation_type = "edit"
            file_path_param = file_path
            file_name_param = Path(file_path).name if file_path else "unknown"

            # Generate diff for edit confirmation (reuse tool_manager method)
            diff_info = await self.llm_client.tool_manager._generate_edit_diff(file_path, tool_args)
            if diff_info:
                file_diff = diff_info.get("diff")
                original_content = diff_info.get("original", "")
                new_content = diff_info.get("new", "")

        elif tool_name == "write":
            file_path = tool_args.get("file_path", "unknown")
            command = f"Write file: {file_path}"
            description = tool_args.get("description", None)
            confirmation_type = "edit"
            file_path_param = file_path
            file_name_param = Path(file_path).name if file_path else "unknown"

            # Generate diff for write confirmation (reuse tool_manager method)
            diff_info = await self.llm_client.tool_manager._generate_write_diff(file_path, tool_args)
            if diff_info:
                file_diff = diff_info.get("diff")
                original_content = diff_info.get("original", "")
                new_content = diff_info.get("new", "")

        elif tool_name == "pfc_execute_task":
            entry_script = tool_args.get("entry_script", "unknown")
            run_in_background = tool_args.get("run_in_background", True)
            bg_info = " (background)" if run_in_background else " (foreground)"
            command = f"Execute PFC task{bg_info}: {entry_script}"
            description = tool_args.get("description", None)
            confirmation_type = "exec"

        else:
            command = f"{tool_name} operation"
            description = tool_args.get("description", None)
            confirmation_type = "info"

        # Request confirmation via confirmation service
        try:
            approved, user_message = await confirmation_service.request_confirmation(
                session_id=session_id,
                message_id=message_id,
                tool_call_id=tool_id,
                tool_name=tool_name,
                command=command,
                description=description,
                confirmation_type=confirmation_type,
                file_name=file_name_param,
                file_path=file_path_param,
                file_diff=file_diff,
                original_content=original_content,
                new_content=new_content
            )
            return (approved, user_message)

        except Exception as e:
            print(f"[ChatOrchestrator] Error requesting confirmation for {tool_name}: {e}")
            return (False, f"Error during confirmation: {str(e)}")
