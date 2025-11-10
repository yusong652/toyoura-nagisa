"""
Enhanced LLM Client Base with SOTA streaming architecture.

This module provides the foundational LLMClientBase class that all provider-specific
clients inherit from, implementing common patterns extracted from the Gemini implementation.
"""

import asyncio
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, Type, AsyncGenerator
from backend.domain.models.messages import BaseMessage
from backend.domain.models.streaming import StreamingChunk
from backend.infrastructure.llm.base.context_manager import BaseContextManager
from backend.infrastructure.llm.base.message_formatter import BaseMessageFormatter
from backend.infrastructure.llm.base.response_processor import BaseResponseProcessor
from backend.infrastructure.websocket.notification_service import WebSocketNotificationService
from backend.shared.exceptions import UserRejectionInterruption


class LLMClientBase(ABC):
    """
    LLM client base class with unified streaming architecture.
    
    Streaming architecture design focused on real-time tool call notifications:
    - Core interface: get_response() - streaming processing with real-time notifications
    - Specialized interfaces: generate_title_from_messages(), generate_text_to_image_prompt()
    - Configuration management: update_config() - dynamic configuration updates
    
    Architecture advantages:
    - Real-time: instant status updates during tool calling processes
    - Efficient: AsyncGenerator implementation with zero-latency event delivery
    - Consistent: unified streaming interface avoiding redundant wrappers
    """
    
    def __init__(self, extra_config: Optional[Dict[str, Any]] = None):
        """
        Initialize LLM client base class.

        Args:
            extra_config: Additional configuration parameters
        """
        self.extra_config = extra_config or {}

        # Common client attributes that all implementations should have
        self.client = None  # Will be set by concrete implementations

        # Tool manager will be set by concrete implementations
        # Each provider has its own tool manager (GeminiToolManager, OpenAIToolManager, etc.)
        # We use Any type here because concrete implementations always set it, never None in practice
        self.tool_manager: Any = None  # Will be BaseToolManager subclass

        # Session-based context manager management
        self._session_context_managers: Dict[str, BaseContextManager] = {}

    @abstractmethod
    async def call_api_with_context(
        self,
        context_contents: List[Dict[str, Any]],
        api_config: Dict[str, Any],
        **kwargs
    ) -> Any:
        """
        Execute direct LLM API call with complete pre-formatted context and configuration.

        Performs a pure, stateless API call using complete context and configuration.
        This method is thread-safe and supports concurrent sessions without state conflicts.

        Args:
            context_contents: Complete context contents in provider-specific format:
                - Provider-specific message format (e.g., Gemini, OpenAI, Anthropic formats)
                - Message roles and content parts as required by each provider
                - For OpenAI: includes system message if needed
                - For Anthropic/Gemini: messages without system prompt
            api_config: Provider-specific API configuration dictionary:
                - tools: List[Any] - Tool schemas in provider format (if applicable)
                - system_prompt: str - System prompt (for Anthropic)
                - config: Any - Provider-specific config object (for Gemini)
                - Any other provider-specific configuration
            **kwargs: Additional runtime API parameters:
                - temperature: Optional[float] - Sampling temperature override
                - max_tokens/max_output_tokens: Optional[int] - Maximum output override
                - top_p: Optional[float] - Nucleus sampling parameter
                - top_k: Optional[int] - Top-k sampling (provider-dependent)

        Returns:
            Any: Raw API response object in provider-specific format:
                - Response structure varies by provider (Gemini, OpenAI, Anthropic)
                - Contains response candidates, usage metadata, and tool call results
                - Maintains complete original response structure

        Raises:
            Exception: If API call fails or returns invalid response
            NotImplementedError: If not implemented by provider

        Example:
            # Thread-safe concurrent usage
            context, config = await self._prepare_complete_context(session_id)
            response = await self.call_api_with_context(context, config)

        Note:
            This method is stateless and thread-safe. All session-specific
            configuration is passed as parameters, not stored as instance state.
        """
        pass

    @abstractmethod
    async def call_api_with_context_streaming(
        self,
        context_contents: List[Dict[str, Any]],
        api_config: Dict[str, Any],
        **kwargs
    ) -> AsyncGenerator[StreamingChunk, None]:
        """
        Execute streaming LLM API call with real-time chunk delivery.

        This method performs a streaming API call and yields standardized StreamingChunk
        objects as they arrive from the provider. This enables real-time display of
        thinking content and text generation.

        Args:
            context_contents: Complete context contents in provider-specific format
            api_config: Provider-specific API configuration dictionary
            **kwargs: Additional runtime API parameters

        Yields:
            StreamingChunk: Standardized streaming data chunks containing:
                - chunk_type: "thinking" | "text" | "function_call"
                - content: The actual content text
                - metadata: Additional context-specific data
                - thought_signature: Optional cryptographic signature (Gemini)
                - function_call: Optional function call details

        Raises:
            Exception: If streaming API call fails
            NotImplementedError: If not implemented by provider

        Example:
            # Streaming usage
            context, config = await self._prepare_complete_context(session_id)
            async for chunk in self.call_api_with_context_streaming(context, config):
                if chunk.chunk_type == "thinking":
                    await send_thinking_to_websocket(chunk.content)
                elif chunk.chunk_type == "text":
                    await send_text_to_websocket(chunk.content)

        Note:
            This method is the core streaming interface. Providers must implement
            this to convert their native streaming format into StreamingChunk objects.
        """
        pass
        # Make this an async generator by yielding nothing
        # Subclasses will override with actual implementation
        if False:
            yield

    async def add_user_message_to_session(self, session_id: str, parsed_data: dict) -> None:
        """
        Add user message to specified session (async).

        Now supports async reminder injection for bash processes and PFC tasks.

        Args:
            session_id: Session ID
            parsed_data: Parsed message data including agent_profile, enable_memory configuration
        """
        context_manager = self.get_or_create_context_manager(session_id)

        # Reset interrupt flag for new conversation turn
        context_manager.user_interrupted = False

        # Initialize context manager if needed
        if not context_manager._initialized_from_history:
            from backend.infrastructure.storage.session_manager import load_history
            recent_history = load_history(session_id)
            # Exclude the last message from history since we'll add the current user message separately
            # This prevents duplicate user messages when the current message was already saved to storage
            if recent_history:
                recent_history = recent_history[:-1]
            # Use provider-specific message factory (can be overridden by subclasses)
            recent_msgs = self._process_history_messages(recent_history)
            context_manager.initialize_session_from_history(recent_msgs)
        # Add user message and set configuration (now async)
        await context_manager.add_user_message_from_data(parsed_data)

    async def get_response_from_session(
        self,
        session_id: str
    ) -> tuple[BaseMessage, Optional[str]]:
        """
        Generate response from specified session.

        Args:
            session_id: Session ID

        Returns:
            tuple[BaseMessage, Optional[str]]: (Final response message, optional message_id from streaming)

        Raises:
            UserRejectionInterruption: When user rejects tool execution (not an error)
        """
        try:
            # Call recursive tool calling loop
            # Note: final_response is already added to context_manager within _recursive_tool_calling
            final_response = await self._recursive_tool_calling(
                session_id, iterations=0
            )

            # Format response for storage (but don't add to context manager - already added)
            processor = self._get_response_processor()
            if processor:
                final_message = processor.format_response_for_storage(final_response)
            else:
                from backend.domain.models.messages import AssistantMessage
                final_message = AssistantMessage(content=[{"type": "text", "text": "Response processing unavailable"}])

            # Get streaming message_id from context manager (if streaming was used)
            context_manager = self.get_or_create_context_manager(session_id)
            streaming_message_id = getattr(context_manager, 'streaming_message_id', None)

            return final_message, streaming_message_id

        except UserRejectionInterruption:
            # User rejection is not an error - re-raise as-is
            raise

        except Exception as e:
            # Real error - log and raise with context
            import traceback
            print(f"[ERROR] Exception in execute_with_thinking: {e}")
            print(f"[ERROR] Traceback: {traceback.format_exc()}")

            # Clean up the empty placeholder message created before streaming
            # This prevents leaving empty assistant messages in history that cause API errors on reload
            context_manager = self.get_or_create_context_manager(session_id)
            streaming_message_id = getattr(context_manager, 'streaming_message_id', None)
            if streaming_message_id:
                try:
                    from backend.infrastructure.storage.session_manager import delete_message
                    delete_message(session_id, streaming_message_id)
                    print(f"[DEBUG] Cleaned up placeholder message {streaming_message_id} after API failure")
                except Exception as cleanup_error:
                    print(f"[WARNING] Failed to clean up placeholder message: {cleanup_error}")

            raise Exception(f"Execution failed: {e}")

    async def _recursive_tool_calling(
        self,
        session_id: str,
        iterations: int = 0
    ) -> Any:
        """
        Recursive tool calling implementation with user rejection interruption.

        Args:
            session_id: Session ID
            iterations: Current iteration count

        Returns:
            Any: Final LLM response

        Raises:
            UserRejectionInterruption: When user rejects any tool
        """
        # Prepare complete context with all necessary components
        # Returns both context and configuration for stateless API call
        complete_context, api_config = await self._prepare_complete_context(
            session_id=session_id
        )

        # Create placeholder message before streaming starts
        from backend.shared.utils.helpers import save_assistant_message
        message_id = save_assistant_message([], session_id)  # Empty content placeholder

        # Send MESSAGE_CREATE notification to frontend
        await WebSocketNotificationService.send_message_create(session_id, message_id, streaming=True)

        # Store message_id in context manager for retrieval by process_content_pipeline
        context_manager = self.get_or_create_context_manager(session_id)
        context_manager.streaming_message_id = message_id 

        # Use streaming API call with accumulated content updates
        # Collect chunks and send accumulated content blocks via WebSocket
        collected_chunks: List[StreamingChunk] = []
        thinking_buffer = ""
        text_buffer = ""

        async for chunk in self.call_api_with_context_streaming(complete_context, api_config):
            # Check for user interrupt
            if context_manager.user_interrupted:
                print(f"[INFO] Streaming interrupted by user at iteration {iterations}")

                # Create interrupt chunk and add to collected_chunks
                # This ensures the interrupt marker is included in the provider-native response
                interrupt_chunk = StreamingChunk(
                    chunk_type="text",
                    content="\n\n[interrupted by user]",
                    metadata={"interrupted": True}
                )
                collected_chunks.append(interrupt_chunk)

                # Update text_buffer for display
                text_buffer += "\n\n[interrupted by user]"

                # Build final content blocks with interrupt marker
                content_blocks = []
                if thinking_buffer:
                    content_blocks.append({"type": "thinking", "thinking": thinking_buffer})
                if text_buffer:
                    content_blocks.append({"type": "text", "text": text_buffer})

                # Construct partial response from complete chunks (now includes interrupt marker)
                partial_response = self._construct_response_from_streaming_chunks(collected_chunks)

                # Add to context manager (preserves provider-native format with interrupt)
                context_manager.add_response(partial_response)

                # Format for storage and save to database
                processor = self._get_response_processor()
                if processor:
                    final_message = processor.format_response_for_storage(partial_response)
                    if final_message:
                        from backend.shared.utils.helpers import update_assistant_message
                        storage_content = final_message.content if isinstance(final_message.content, list) else [{"type": "text", "text": str(final_message.content)}]
                        update_assistant_message(message_id, storage_content, session_id)

                # Send final update with streaming=False
                await WebSocketNotificationService.send_streaming_update(
                    session_id=session_id,
                    message_id=message_id,
                    content=content_blocks,
                    streaming=False
                )

                # Trigger title generation after user interruption (if we have text content)
                asyncio.create_task(self._try_generate_title_async(session_id))

                # Return partial response (allows user to send next message)
                return partial_response

            # Collect chunk for context assembly
            collected_chunks.append(chunk)

            # Accumulate chunk content
            if chunk.chunk_type == "thinking":
                thinking_buffer += chunk.content
            elif chunk.chunk_type == "text":
                text_buffer += chunk.content

            # Build complete content blocks
            # Note: Each content block type appears only once in the array to avoid
            # rendering issues (multiple text blocks would render as separate lines)
            content_blocks = []
            if thinking_buffer:
                content_blocks.append({"type": "thinking", "thinking": thinking_buffer})
            if text_buffer:
                content_blocks.append({"type": "text", "text": text_buffer})

            # Send accumulated content update to WebSocket
            if content_blocks:
                await WebSocketNotificationService.send_streaming_update(
                    session_id=session_id,
                    message_id=message_id,
                    content=content_blocks,
                    streaming=True
                )

        # Ensure at least one streaming update was sent
        # If no text/thinking content was streamed (e.g., direct tool call), send initial empty update
        if not text_buffer and not thinking_buffer:
            await WebSocketNotificationService.send_streaming_update(
                session_id=session_id,
                message_id=message_id,
                content=[{"type": "text", "text": ""}],
                streaming=True
            )

        # Construct complete response from collected chunks
        current_response = self._construct_response_from_streaming_chunks(collected_chunks)
        context_manager = self.get_or_create_context_manager(session_id)

        # Check if response contains tool calls
        processor = self._get_response_processor()
        if not (processor and processor.has_tool_calls(current_response)):
            # Add final response to context manager
            context_manager.add_response(current_response)

            # Format response for storage and update message in database
            final_message = processor.format_response_for_storage(current_response) if processor else None
            if final_message:
                from backend.shared.utils.helpers import update_assistant_message
                content = final_message.content if isinstance(final_message.content, list) else [{"type": "text", "text": str(final_message.content)}]
                update_assistant_message(message_id, content, session_id)

                # Send final streaming update with streaming=False to mark completion
                await WebSocketNotificationService.send_streaming_update(
                    session_id=session_id,
                    message_id=message_id,
                    content=content,
                    streaming=False
                )

                # Trigger title generation after content is saved (normal completion without tool calls)
                asyncio.create_task(self._try_generate_title_async(session_id))

            return current_response  # Normal completion

        # Process tool calls - add response to context manager
        context_manager.add_response(current_response)

        # Extract tool calls first (to ensure consistent IDs across save and execution)
        processor = self._get_response_processor()
        tool_calls = processor.extract_tool_calls(current_response) if processor else []

        # Update streaming message with complete content (before tool calls)
        # This ensures the streaming placeholder is updated with any thinking/text content
        if processor:
            try:
                from backend.shared.utils.helpers import update_assistant_message
                tool_call_message = processor.format_response_for_storage(current_response, tool_calls)
                content = tool_call_message.content if isinstance(tool_call_message.content, list) else [{"type": "text", "text": str(tool_call_message.content)}]
                update_assistant_message(message_id, content, session_id)

                # Send final streaming update to mark completion
                await WebSocketNotificationService.send_streaming_update(
                    session_id=session_id,
                    message_id=message_id,
                    content=content,
                    streaming=False
                )

                # Trigger title generation after first text content is saved
                # This runs in background without blocking tool execution
                asyncio.create_task(self._try_generate_title_async(session_id))

            except Exception as e:
                # Log error but don't fail the execution
                print(f"[WARNING] Failed to update streaming message with tool call content: {e}")

        if tool_calls:
            # Check iteration limit BEFORE executing tools (fixed limit: 64)
            MAX_ITERATIONS = 64

            # Check if we've reached the iteration limit
            if iterations >= MAX_ITERATIONS:
                # Reached limit - stop execution gracefully
                print(f"[INFO] Tool calling stopped at iteration {iterations}: reached maximum limit ({MAX_ITERATIONS})")

                # Create informative tool results for each tool call
                from backend.infrastructure.mcp.utils.tool_result import success_response
                stop_message = (
                    f"⚠️ Tool execution stopped: Reached iteration limit ({MAX_ITERATIONS} iterations).\n\n"
                    f"The task may be incomplete. You can provide a summary of what was accomplished.\n\n"
                    f"Note: This is a safety mechanism to prevent infinite loops."
                )

                for i, tool_call in enumerate(tool_calls):
                    is_last_tool = (i == len(tool_calls) - 1)

                    # Create explanatory result
                    limit_result = success_response(
                        stop_message,
                        llm_content={
                            "parts": [{"type": "text", "text": stop_message}]
                        }
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
                        from backend.shared.utils.helpers import save_tool_result_message
                        message_id = save_tool_result_message(
                            tool_call_id=tool_call['id'],
                            tool_name=tool_call['name'],
                            tool_result=limit_result,
                            session_id=session_id
                        )
                        await WebSocketNotificationService.send_message_saved(session_id, message_id, 'user')
                    except Exception as e:
                        print(f"[WARNING] Failed to save iteration limit tool result: {e}")

                # Return current response - LLM will see these tool results on next user request
                return current_response

            # Execute tools normally (within limit)
            # This aligns with Claude Code's behavior: serial execution with intelligent cascade
            results = await self.tool_manager.handle_multiple_function_calls(
                tool_calls,
                session_id or ""
            )

            # Add results to context and check for rejections
            rejected_tools = []
            for i, (tool_call, result) in enumerate(zip(tool_calls, results)):
                # Check if this is the last tool result
                is_last_tool = (i == len(tool_calls) - 1)

                await context_manager.add_tool_result(
                    tool_call['id'],
                    tool_call['name'],
                    result,
                    inject_reminders=is_last_tool
                )

                # Save tool result to database
                try:
                    from backend.shared.utils.helpers import save_tool_result_message
                    message_id = save_tool_result_message(
                        tool_call_id=tool_call['id'],
                        tool_name=tool_call['name'],
                        tool_result=result,
                        session_id=session_id
                    )

                    # Send WebSocket notification to refresh messages after each tool result
                    await WebSocketNotificationService.send_message_saved(session_id, message_id, 'user')
                except Exception as e:
                    # Log error but don't fail the execution
                    print(f"[WARNING] Failed to save tool result for {tool_call['name']}: {e}")

                # Check if this tool was directly rejected by user (not cascade blocked)
                # Only direct rejections trigger interruption, cascade blocks are informational
                if self._is_tool_rejected(result):
                    rejected_tools.append(tool_call['name'])

            # If any tool was directly rejected, interrupt immediately
            # Note: cascade_blocked tools are not considered rejections for interruption
            if rejected_tools:
                raise UserRejectionInterruption(session_id, rejected_tools)

        # Check for user interrupt before continuing recursion
        if context_manager.user_interrupted:
            print(f"[INFO] Tool calling interrupted by user at iteration {iterations}")
            # Return current response - user can send next message
            return current_response

        # Continue recursively
        return await self._recursive_tool_calling(session_id, iterations + 1)

    async def _try_generate_title_async(self, session_id: str) -> None:
        """
        Asynchronously attempt to generate title when first text content is detected.

        This method runs in the background without blocking the main streaming flow.
        It checks if title generation is needed and triggers it if appropriate.

        Args:
            session_id: Session ID to generate title for
        """
        try:
            # Import here to avoid circular dependency
            from backend.application.services.contents import TitleService
            from backend.infrastructure.storage.session_manager import load_all_message_history
            from backend.domain.models.message_factory import message_factory
            from backend.presentation.streaming.llm_response_handler import send_title_update_notification

            # Load history and check if title generation is needed
            title_service = TitleService()
            loaded_history = load_all_message_history(session_id)
            history_msgs = [message_factory(msg) if isinstance(msg, dict) else msg for msg in loaded_history]

            if title_service.should_generate_title(session_id, history_msgs):
                # Generate title
                result = await title_service.generate_title_for_session(session_id, self)

                if result and result.get("success") and result.get("title"):
                    # Send title update via WebSocket
                    await send_title_update_notification(session_id, result["title"])
                    print(f"[INFO] Title auto-generated during streaming for session {session_id}: {result['title']}")

        except Exception as e:
            # Title generation failure should not affect main flow
            print(f"[WARNING] Background title generation failed for session {session_id}: {e}")

    @abstractmethod
    def _get_response_processor(self) -> Optional[BaseResponseProcessor]:
        """
        Get provider-specific response processor instance.

        Returns:
            Optional[BaseResponseProcessor]: Provider-specific response processor instance (e.g., GeminiResponseProcessor)
                                           Returns None if not implemented by provider
        """
        pass

    @abstractmethod
    def _get_provider_config(self) -> Any:
        """
        Get provider-specific configuration object.

        Returns:
            Any: Provider-specific config object with debug flag and other settings
        """
        pass

    @abstractmethod
    async def _prepare_complete_context(
        self,
        session_id: str
    ) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Prepare complete context and API configuration for stateless API call.

        This method consolidates all context preparation logic including:
        - Getting or creating context manager for the session
        - Extracting agent_profile and enable_memory from context manager
        - Getting recent_messages_length from configuration
        - Getting tool schemas for API
        - Getting tool schemas for system prompt
        - Building system prompt with memory and tools
        - Getting working contents from context manager
        - Preparing provider-specific API configuration

        Args:
            session_id: Session identifier

        Returns:
            Tuple containing:
            - context_contents: List[Dict[str, Any]] - Messages ready for API call
                - For OpenAI: includes system message in the list
                - For others: just conversation messages
            - api_config: Dict[str, Any] - Provider-specific configuration:
                - tools: Tool schemas in provider format (optional)
                - system_prompt: System prompt string (for Anthropic)
                - config: GenerateContentConfig (for Gemini)
                - Any other provider-specific settings

        Note:
            This method must be stateless and return all necessary configuration.
            Do NOT store configuration in instance attributes to avoid concurrency issues.
        """
        pass

    @abstractmethod
    def _construct_response_from_streaming_chunks(
        self,
        chunks: List[StreamingChunk]
    ) -> Any:
        """
        Construct complete response object from collected streaming chunks.

        This method converts a list of StreamingChunk objects back into
        the provider's native response format for tool call detection and context management.

        Args:
            chunks: List of StreamingChunk objects collected during streaming

        Returns:
            Any: Provider-specific complete response object:
                - Gemini: types.GenerateContentResponse
                - Anthropic: Message
                - OpenAI: ChatCompletion
                - Must contain all necessary data for tool call detection

        Note:
            This reconstruction is necessary because we need the complete response
            for tool call detection and context management, while streaming provides
            only incremental chunks.
        """
        pass


    def _is_tool_rejected(self, tool_result: Dict[str, Any]) -> bool:
        """
        Check if tool execution was rejected by user.

        Args:
            tool_result: Tool execution result dictionary

        Returns:
            bool: True if tool was rejected by user, False otherwise
        """
        return tool_result.get('user_rejected', False)

    async def _clear_session_context(self, session_id: str):
        """Clear session context - shared implementation."""
        # Clear session-specific context manager
        self.cleanup_session_context(session_id)

    def _process_history_messages(self, history: List[Dict[str, Any]]) -> List[BaseMessage]:
        """
        Process history messages for context initialization.

        Default implementation filters out thinking content to reduce token usage.
        Providers can override this method to customize history processing behavior.

        Args:
            history: Raw history messages from storage

        Returns:
            List[BaseMessage]: Processed message objects
        """
        from backend.domain.models.message_factory import message_factory_no_thinking
        return [message_factory_no_thinking(msg) for msg in history]

    @abstractmethod
    def _get_context_manager_class(self) -> Type[BaseContextManager]:
        """
        Get provider-specific context manager class.

        Returns:
            Type[BaseContextManager]: Context manager class for this provider
        """
        pass

    def get_or_create_context_manager(self, session_id: str) -> BaseContextManager:
        """
        Get existing context manager or create new one for session.

        Args:
            session_id: Session identifier

        Returns:
            BaseContextManager: Context manager instance for the session
        """
        if session_id not in self._session_context_managers:
            # Create new context manager for this session
            context_manager_class = self._get_context_manager_class()
            provider_name = self.__class__.__name__.replace('Client', '').lower()

            self._session_context_managers[session_id] = context_manager_class(
                provider_name=provider_name,
                session_id=session_id
            )

        return self._session_context_managers[session_id]

    def cleanup_session_context(self, session_id: str) -> None:
        """
        Clean up context manager for ended session.

        Args:
            session_id: Session identifier to clean up
        """
        if session_id in self._session_context_managers:
            self._session_context_managers[session_id].clear_runtime_context()
            del self._session_context_managers[session_id]

        # Clear tool manager's read file tracking for this session
        if self.tool_manager:
            self.tool_manager.clear_session_read_tracking(session_id)
