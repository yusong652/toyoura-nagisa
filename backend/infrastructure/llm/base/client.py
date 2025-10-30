"""
Enhanced LLM Client Base with SOTA streaming architecture.

This module provides the foundational LLMClientBase class that all provider-specific
clients inherit from, implementing common patterns extracted from the Gemini implementation.
"""

import asyncio
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, Type, TYPE_CHECKING, AsyncGenerator
from backend.domain.models.messages import BaseMessage
from backend.domain.models.streaming import StreamingChunk
from backend.infrastructure.llm.base.context_manager import BaseContextManager
from backend.infrastructure.llm.base.message_formatter import BaseMessageFormatter
from backend.infrastructure.llm.base.response_processor import BaseResponseProcessor
from backend.shared.exceptions import UserRejectionInterruption

if TYPE_CHECKING:
    from backend.infrastructure.llm.base.content_generators.title import BaseTitleGenerator
    from backend.infrastructure.llm.base.content_generators.image_prompt import BaseImagePromptGenerator
    from backend.infrastructure.llm.base.content_generators.web_search import BaseWebSearchGenerator


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

        # Initialize context manager if needed
        if not context_manager._initialized_from_history:
            from backend.infrastructure.storage.session_manager import load_history
            from backend.domain.models.message_factory import message_factory_no_thinking
            recent_history = load_history(session_id)
            # Exclude the last message from history since we'll add the current user message separately
            # This prevents duplicate user messages when the current message was already saved to storage
            if recent_history:
                recent_history = recent_history[:-1]
            recent_msgs = [message_factory_no_thinking(msg) for msg in recent_history]
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
        # Get max iterations from config
        from backend.config import get_llm_settings
        max_iterations = get_llm_settings().max_tool_iterations

        # Check iteration limit
        if iterations >= max_iterations:
            raise Exception(f"Exceeded max iterations ({max_iterations})")

        # Prepare complete context with all necessary components
        # Returns both context and configuration for stateless API call
        complete_context, api_config = await self._prepare_complete_context(
            session_id=session_id
        )

        # Create placeholder message before streaming starts
        from backend.shared.utils.helpers import save_assistant_message
        message_id = save_assistant_message([], session_id)  # Empty content placeholder

        # Send MESSAGE_CREATE notification to frontend
        await self._send_message_create_notification(session_id, message_id, streaming=True)

        # Store message_id in context manager for retrieval by process_content_pipeline
        context_manager = self.get_or_create_context_manager(session_id)
        context_manager.streaming_message_id = message_id

        # Use streaming API call with accumulated content updates
        # Collect chunks and send accumulated content blocks via WebSocket
        collected_chunks: List[StreamingChunk] = []
        thinking_buffer = ""
        text_buffer = ""

        async for chunk in self.call_api_with_context_streaming(complete_context, api_config):
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
                await self._send_streaming_update(
                    session_id=session_id,
                    message_id=message_id,
                    content=content_blocks,
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
                await self._send_streaming_update(
                    session_id=session_id,
                    message_id=message_id,
                    content=content,
                    streaming=False
                )

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
                await self._send_streaming_update(
                    session_id=session_id,
                    message_id=message_id,
                    content=content,
                    streaming=False
                )
            except Exception as e:
                # Log error but don't fail the execution
                print(f"[WARNING] Failed to update streaming message with tool call content: {e}")

        if tool_calls:
            # Execute tools serially with rejection cascade
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
                    await self._send_message_saved_notification(session_id, message_id, 'user')
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

        # Continue recursively
        return await self._recursive_tool_calling(session_id, iterations + 1)

    async def generate_title_from_messages(
        self,
        latest_messages: List[BaseMessage]
    ) -> Optional[str]:
        """
        [Optional Interface] Generate title from conversation messages.

        This method uses provider-specific title generator for implementation.
        Override _get_title_generator() to provide custom generator.

        Args:
            latest_messages: Recent conversation messages to generate title from

        Returns:
            Generated title string, or None if failed

        Raises:
            NotImplementedError: If client doesn't support this functionality
        """
        generator = self._get_title_generator()
        if not generator:
            raise NotImplementedError(
                f"{self.__class__.__name__} does not support title generation"
            )

        # Get debug setting from provider config
        provider_config = self._get_provider_config()

        # Call provider-specific generator with unified signature
        return await generator.generate_title_from_messages(
            self.client,
            latest_messages
        )

    async def generate_text_to_image_prompt(
        self,
        session_id: Optional[str] = None
    ) -> Optional[Dict[str, str]]:
        """
        [Optional Interface] Generate text-to-image prompt.

        This method uses provider-specific image prompt generator for implementation.
        Override _get_image_prompt_generator() to provide custom generator.

        Args:
            session_id: Session ID for getting conversation context

        Returns:
            Dictionary containing text prompt and negative prompt, or None if failed

        Raises:
            NotImplementedError: If client doesn't support this functionality
        """
        generator = self._get_image_prompt_generator()
        if not generator:
            raise NotImplementedError(
                f"{self.__class__.__name__} does not support image prompt generation"
            )

        # Get debug setting from provider config
        provider_config = self._get_provider_config()

        # Call provider-specific generator with unified signature
        return await generator.generate_text_to_image_prompt(
            self.client,
            session_id=session_id
        )

    async def perform_web_search(self, query: str, **kwargs) -> Dict[str, Any]:
        """
        [Optional Interface] Perform web search.

        This method uses provider-specific web search generator for implementation.
        Override _get_web_search_generator() to provide custom generator.

        Args:
            query: Search query
            **kwargs: Additional search parameters (max_uses, etc.)

        Returns:
            Dictionary containing search results with sources and metadata

        Raises:
            NotImplementedError: If client doesn't support this functionality
        """
        generator = self._get_web_search_generator()
        if not generator:
            raise NotImplementedError(
                f"{self.__class__.__name__} does not support web search"
            )

        # Get debug setting from provider config
        provider_config = self._get_provider_config()
        debug = getattr(provider_config, 'debug', False)

        # Call provider-specific generator with unified signature
        return await generator.perform_web_search(
            self.client,
            query,
            debug=debug,
            **kwargs
        )

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
    def _get_title_generator(self) -> Optional[Type['BaseTitleGenerator']]:
        """
        Get provider-specific title generator class.

        Returns:
            Optional[Type[BaseTitleGenerator]]: Title generator class for this provider,
                                                or None if title generation is not supported
        """
        pass

    @abstractmethod
    def _get_image_prompt_generator(self) -> Optional[Type['BaseImagePromptGenerator']]:
        """
        Get provider-specific image prompt generator class.

        Returns:
            Optional[Type[BaseImagePromptGenerator]]: Image prompt generator class for this provider,
                                                      or None if image prompt generation is not supported
        """
        pass

    @abstractmethod
    def _get_web_search_generator(self) -> Optional[Type['BaseWebSearchGenerator']]:
        """
        Get provider-specific web search generator class.

        Returns:
            Optional[Type[BaseWebSearchGenerator]]: Web search generator class for this provider,
                                                     or None if web search is not supported
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

    async def _send_streaming_chunk_to_websocket(
        self,
        session_id: str,
        chunk: StreamingChunk
    ) -> None:
        """
        Send streaming chunk to WebSocket for real-time display.

        This method pushes individual streaming chunks to the frontend via WebSocket,
        enabling real-time display of thinking content and text generation.

        Args:
            session_id: Target session ID
            chunk: Standardized streaming chunk to send

        Note:
            Failures in WebSocket sending are logged but do not interrupt the
            streaming process. This ensures robustness even when WebSocket
            connections are unstable.
        """
        try:
            from backend.infrastructure.websocket.connection_manager import get_connection_manager
            connection_manager = get_connection_manager()

            if not connection_manager:
                return

            # Construct WebSocket message
            from backend.presentation.websocket.message_types import MessageType, create_message

            ws_message = create_message(
                MessageType.STREAMING_CHUNK,
                session_id=session_id,
                chunk_type=chunk.chunk_type,
                content=chunk.content,
                metadata=chunk.metadata
            )

            await connection_manager.send_json(session_id, ws_message.model_dump())

        except Exception as e:
            # Streaming display failure should not interrupt main flow
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to send streaming chunk to WebSocket: {e}")

    async def _send_streaming_update(
        self,
        session_id: str,
        message_id: str,
        content: List[Dict[str, Any]],
        streaming: bool = True
    ) -> None:
        """
        Send accumulated content update to WebSocket for real-time display.

        This method sends complete accumulated content blocks instead of individual chunks,
        making frontend logic simpler and consistent with session refresh data structure.

        The frontend receives complete thinking/text content and simply replaces message content,
        ensuring data structure consistency between real-time streaming and database storage.

        Args:
            session_id: Target session ID
            message_id: Message ID to update
            content: Complete content blocks array [{"type": "thinking", "thinking": "..."}, ...]
            streaming: Whether message is still streaming (True) or complete (False)

        Example:
            await self._send_streaming_update(
                session_id="session-123",
                message_id="msg-456",
                content=[
                    {"type": "thinking", "thinking": "Complete thinking so far..."},
                    {"type": "text", "text": "Complete text so far..."}
                ],
                streaming=True
            )

        Note:
            Failures in WebSocket sending are logged but do not interrupt the streaming process.
        """
        try:
            from backend.infrastructure.websocket.connection_manager import get_connection_manager
            connection_manager = get_connection_manager()

            if not connection_manager:
                return

            # Construct WebSocket message
            from backend.presentation.websocket.message_types import MessageType, create_message

            ws_message = create_message(
                MessageType.STREAMING_UPDATE,
                session_id=session_id,
                message_id=message_id,
                content=content,
                streaming=streaming
            )

            await connection_manager.send_json(session_id, ws_message.model_dump())

        except Exception as e:
            # Streaming display failure should not interrupt main flow
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to send streaming update to WebSocket: {e}")

    async def _send_message_create_notification(
        self,
        session_id: str,
        message_id: str,
        streaming: bool = True,
        initial_text: str = ""
    ) -> None:
        """
        Send MESSAGE_CREATE notification to frontend to create message container.

        This notification tells the frontend to create a new message placeholder
        before streaming content begins. The message container will receive
        streaming updates via STREAMING_UPDATE messages.

        Args:
            session_id: Target session ID
            message_id: ID of the created message
            streaming: Whether this message will receive streaming updates
            initial_text: Optional initial text content

        Example:
            await self._send_message_create_notification(
                session_id="session-123",
                message_id="msg-456",
                streaming=True
            )

        Note:
            Failures in WebSocket sending are logged but do not interrupt the process.
        """
        try:
            from backend.infrastructure.websocket.connection_manager import get_connection_manager
            connection_manager = get_connection_manager()

            if not connection_manager:
                return

            from backend.presentation.websocket.message_types import MessageType, create_message

            ws_message = create_message(
                MessageType.MESSAGE_CREATE,
                session_id=session_id,
                message_id=message_id,
                role="assistant",
                initial_text=initial_text,
                streaming=streaming
            )

            await connection_manager.send_json(session_id, ws_message.model_dump())

        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to send message create notification: {e}")

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

    async def _send_message_saved_notification(
        self,
        session_id: str,
        message_id: str,
        role: str
    ):
        """
        Send notification that a message was saved to database.

        This triggers frontend to refresh and display the new message immediately.

        Args:
            session_id: Target session ID
            message_id: ID of the saved message
            role: Message role ('user' for tool_result, 'assistant' for tool_use)
        """
        if not session_id:
            return

        try:
            from backend.infrastructure.websocket.connection_manager import get_connection_manager

            connection_manager = get_connection_manager()
            if not connection_manager:
                print("[DEBUG] Connection manager not available for MESSAGE_SAVED")
                return

            # Send custom event to trigger message refresh
            notification = {
                'type': 'MESSAGE_SAVED',
                'message_id': message_id,
                'role': role,
                'session_id': session_id
            }

            # Send via WebSocket to trigger frontend message refresh
            success = await connection_manager.send_json(session_id, notification)

            if success:
                print(f"[DEBUG] Sent MESSAGE_SAVED notification for {role} message {message_id}")
            else:
                print(f"[DEBUG] Failed to send MESSAGE_SAVED notification (no connection for session {session_id})")

        except Exception as e:
            print(f"[DEBUG] Failed to send message saved notification: {e}")

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
