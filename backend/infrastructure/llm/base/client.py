"""
Enhanced LLM Client Base with SOTA streaming architecture.

This module provides the foundational LLMClientBase class that all provider-specific
clients inherit from, implementing common patterns extracted from the Gemini implementation.
"""

import asyncio
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, Type, TYPE_CHECKING
from backend.domain.models.messages import BaseMessage
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

    def add_user_message_to_session(self, session_id: str, parsed_data: dict) -> None:
        """
        Add user message to specified session.

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
        # Add user message and set configuration
        context_manager.add_user_message_from_data(parsed_data)

    async def get_response_from_session(
        self,
        session_id: str
    ) -> BaseMessage:
        """
        Generate response from specified session.

        Args:
            session_id: Session ID

        Returns:
            BaseMessage: Final response message

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

            return final_message

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
        iterations: int = 0,
        had_tools_in_previous_round: bool = False
    ) -> Any:
        """
        Recursive tool calling implementation with user rejection interruption.

        Args:
            session_id: Session ID
            iterations: Current iteration count
            had_tools_in_previous_round: Whether tools were executed in the previous iteration

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

        # Stateless API call with context and configuration
        current_response = await self.call_api_with_context(complete_context, api_config)
        context_manager = self.get_or_create_context_manager(session_id)
        # Check if response contains tool calls
        processor = self._get_response_processor()
        if not (processor and processor.has_tool_calls(current_response)):
            # If previous round had tools and now we're done, send concluded notification
            if had_tools_in_previous_round:
                concluded_notification = {'type': 'NAGISA_TOOL_USE_CONCLUDED'}
                await self._send_websocket_tool_notification(session_id, concluded_notification)

            # Add final response to context manager before returning
            context_manager.add_response(current_response)
            return current_response  # Normal completion

        # Process tool calls - add response to context manager
        context_manager.add_response(current_response)

        # Save assistant message with tool_use to database
        processor = self._get_response_processor()
        if processor:
            try:
                tool_call_message = processor.format_response_for_storage(current_response)
                from backend.shared.utils.helpers import save_assistant_message
                save_assistant_message(tool_call_message.content, session_id)
            except Exception as e:
                # Log error but don't fail the execution
                print(f"[WARNING] Failed to save assistant message with tool_use: {e}")

        # Extract tool calls using response processor
        processor = self._get_response_processor()
        tool_calls = processor.extract_tool_calls(current_response) if processor else []

        if tool_calls:
            # Send tool use notification
            notification = self._create_tool_notification(tool_calls, current_response)
            await self._send_websocket_tool_notification(session_id, notification)

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

                context_manager.add_tool_result(
                    tool_call['id'],
                    tool_call['name'],
                    result,
                    inject_reminders=is_last_tool
                )

                # Save tool result to database
                try:
                    from backend.shared.utils.helpers import save_tool_result_message
                    save_tool_result_message(
                        tool_call_id=tool_call['id'],
                        tool_name=tool_call['name'],
                        tool_result=result,
                        session_id=session_id
                    )
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

        # Continue recursively - pass True if we executed tools this round
        return await self._recursive_tool_calling(session_id, iterations + 1, bool(tool_calls))

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

    def _is_tool_rejected(self, tool_result: Dict[str, Any]) -> bool:
        """
        Check if tool execution was rejected by user.

        Args:
            tool_result: Tool execution result dictionary

        Returns:
            bool: True if tool was rejected by user, False otherwise
        """
        return tool_result.get('user_rejected', False)

    def _create_tool_notification(
        self,
        tool_calls: List[Dict[str, Any]],
        current_response: Any
    ) -> Dict[str, Any]:
        """
        Create tool use notification data structure.

        Args:
            tool_calls: List of tool call dictionaries
            current_response: Current LLM response containing text and thinking content

        Returns:
            Dict[str, Any]: Notification dictionary ready for WebSocket transmission
        """
        num_tools = len(tool_calls)
        # Extract text and thinking content from response processor
        processor = self._get_response_processor()

        # Extract text content
        try:
            extracted_text = processor.extract_text_content(current_response) if processor else ""
        except Exception:
            extracted_text = ""

        # Extract thinking content
        thinking_content = None
        try:
            if processor and hasattr(processor, 'extract_thinking_content'):
                thinking_content = processor.extract_thinking_content(current_response)
        except Exception:
            pass
        tool_names = [tc.get('name', 'unknown') for tc in tool_calls]

        # Generate action description based on extracted text or tool names
        if extracted_text and len(extracted_text.strip()) > 0:
            action = extracted_text.strip()
            if len(action) > 150:
                action = action[:147] + "..."
        else:
            if num_tools == 1:
                action = f"Using {tool_names[0]}..."
            else:
                action = f"Executing {num_tools} tools in parallel: {', '.join(tool_names)}..."

        # Build notification structure
        notification = {
            'type': 'NAGISA_IS_USING_TOOL',
            'tool_names': tool_names,
            'action': action
        }

        # Add thinking content if available
        if thinking_content:
            notification['thinking'] = thinking_content

        return notification

    async def _clear_session_context(self, session_id: str):
        """Clear session context - shared implementation."""
        # Clear session-specific context manager
        self.cleanup_session_context(session_id)
    
    async def _send_websocket_tool_notification(
        self, 
        session_id: Optional[str], 
        notification: Dict[str, Any]
    ):
        """
        Send tool calling notification via WebSocket.
        
        This method provides dual-channel notification - both SSE (for backwards compatibility)
        and WebSocket (for unified real-time architecture) are supported.
        
        Args:
            session_id: Target session ID
            notification: Notification dictionary with tool calling information
        """
        if not session_id:
            return
        
        try:
            # Import here to avoid circular dependencies
            from backend.application.services.notifications import get_tool_notification_service

            service = get_tool_notification_service()
            if not service:
                print("[DEBUG] Tool notification service not available")
                return

            notification_type = notification.get('type')

            if notification_type == 'NAGISA_IS_USING_TOOL':
                await service.notify_tool_use_started(
                    session_id=session_id,
                    tool_names=notification.get('tool_names', []),
                    action=notification.get('action', ''),
                    thinking=notification.get('thinking')
                )
            elif notification_type == 'NAGISA_TOOL_USE_CONCLUDED':
                await service.notify_tool_use_concluded(
                    session_id=session_id,
                    tool_names=notification.get('tool_names'),
                    results=notification.get('results')
                )
            
        except Exception as e:
            # Don't fail the main execution if WebSocket notification fails
            provider_name = self.__class__.__name__.replace('Client', '')
            print(f"[DEBUG] {provider_name} WebSocket tool notification failed: {e}")

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
