"""
Enhanced LLM Client Base with SOTA streaming architecture.

This module provides the foundational LLMClientBase class that all provider-specific
clients inherit from, implementing common patterns extracted from the Gemini implementation.
"""

import asyncio
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, Tuple, Type
from backend.domain.models.messages import BaseMessage
from backend.infrastructure.llm.base.context_manager import BaseContextManager
from backend.infrastructure.llm.base.message_formatter import BaseMessageFormatter
from backend.infrastructure.llm.base.response_processor import BaseResponseProcessor
from backend.shared.exceptions import UserRejectionInterruption    


class LLMClientBase(ABC):
    """
    Enhanced LLM client base class with unified streaming architecture.
    
    SOTA streaming architecture design focused on real-time tool call notifications:
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
        self.tool_manager = None  # Will be initialized by concrete implementations

        # Session-based context manager management
        self._session_context_managers: Dict[str, BaseContextManager] = {}

    # ========== CORE STREAMING INTERFACE ==========

    # ========== ABSTRACT METHODS FOR PROVIDER-SPECIFIC IMPLEMENTATION ==========

    @abstractmethod
    async def get_function_call_schemas(self, session_id: str, agent_profile: str = "general") -> List[Any]:
        """
        Get function call schemas for tool registration.
        
        Args:
            session_id: Session ID for context-specific tools (required for dependency injection)
            agent_profile: Agent profile type for tool filtering
            
        Returns:
            List[Any]: List of tool schemas in provider-specific format
        """
        pass

    @abstractmethod 
    async def call_api_with_context(
        self, 
        context_contents: List[Dict[str, Any]], 
        session_id: str,
        agent_profile: str = "general",
        enable_memory: bool = True,
        **kwargs
    ) -> Any:
        """
        Execute direct LLM API call with provider-specific context format and tool integration.
        
        Performs a complete API call using pre-formatted context contents while maintaining
        provider-specific response structure. Automatically retrieves session-specific tool
        schemas and applies configuration overrides for optimal provider performance.
        
        Args:
            context_contents: Pre-formatted context contents in provider-specific format with structure:
                - Provider-specific message format (e.g., Gemini, OpenAI, Anthropic formats)
                - Message roles and content parts as required by each provider
                - Function call definitions and tool schemas when applicable
            session_id: Session ID for tool schema retrieval and dependency injection
            agent_profile: Agent profile type for tool filtering and prompt customization
            enable_memory: Whether to enable memory injection in system prompt (controlled by frontend)
            **kwargs: Additional API configuration parameters:
                - temperature: Optional[float] - Sampling temperature override
                - max_output_tokens: Optional[int] - Maximum output tokens override
                - top_p: Optional[float] - Nucleus sampling parameter (provider-dependent)
                - top_k: Optional[int] - Top-k sampling parameter (provider-dependent)
                - Additional provider-specific parameters
                
        Returns:
            Any: Raw API response object in provider-specific format:
                - Response structure varies by provider (Gemini, OpenAI, Anthropic formats)
                - Contains response candidates, usage metadata, and tool call results
                - Maintains complete original response structure for downstream processing
                
        Raises:
            Exception: If API call fails, returns invalid response, or encounters authentication errors
            NotImplementedError: If concrete implementation is not provided by subclass
            
        Example:
            # Provider-specific implementation required
            context = provider_formatter.format_messages(messages)
            response = await client.call_api_with_context(context, session_id="123")
            
        Note:
            Each provider implementation must handle session-specific tool schemas
            and integrate with their respective tool managers and debug systems.
            Response format preservation is critical for tool calling sequences.
        """
        pass

    # ========== SESSION-BASED OPERATION INTERFACES ==========

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
    ) -> Tuple[BaseMessage, Dict[str, Any]]:
        """
        Generate response from specified session.

        Args:
            session_id: Session ID

        Returns:
            Tuple[BaseMessage, Dict[str, Any]]: Final message and execution metadata

        Raises:
            UserRejectionInterruption: When user rejects tool execution (not an error)
        """
        # Get the session's context manager
        context_manager = self.get_or_create_context_manager(session_id)

        try:
            # Call recursive tool calling loop
            final_response = await self._recursive_tool_calling(
                session_id, iterations=0
            )

            # Extract keyword from response
            keyword = None
            processor = self._get_response_processor()
            original_text = processor.extract_text_content(final_response) if processor else ""
            if original_text:
                from backend.shared.utils.text_parser import parse_llm_output
                _, keyword = parse_llm_output(original_text)

            # Create final message and add to context manager
            if processor:
                final_message = processor.format_response_for_storage(final_response)
                context_manager.add_response(final_message)
            else:
                from backend.domain.models.messages import AssistantMessage
                final_message = AssistantMessage(content="Response processing unavailable")

            # Return simplified metadata with only what's actually used
            metadata = {'keyword': keyword} if keyword else {}
            return (final_message, metadata)

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

        # Get current state
        context_manager = self.get_or_create_context_manager(session_id)
        agent_profile = getattr(context_manager, 'agent_profile', 'general')
        enable_memory = getattr(context_manager, 'enable_memory', True)

        from backend.config import get_llm_settings
        recent_messages_length = get_llm_settings().recent_messages_length
        # Get LLM response
        working_contents = context_manager.get_working_contents(recent_messages_length=recent_messages_length)
        current_response = await self.call_api_with_context(
            working_contents,
            session_id=session_id,
            agent_profile=agent_profile,
            enable_memory=enable_memory
        )

        # Check if we need to continue tool calling
        if not self._should_continue_tool_calling(current_response):
            # If previous round had tools and now we're done, send concluded notification
            if had_tools_in_previous_round:
                concluded_notification = {'type': 'NAGISA_TOOL_USE_CONCLUDED'}
                await self._send_websocket_tool_notification(session_id, concluded_notification)
            return current_response  # Normal completion

        # Process tool calls
        context_manager.add_response(current_response)
        tool_calls = self._extract_tool_calls(current_response)

        if tool_calls:
            # Send tool use notification
            notification = self._create_tool_notification(tool_calls, current_response)
            await self._send_websocket_tool_notification(session_id, notification)

            # Execute tools
            tasks = []
            for tc in tool_calls:
                tasks.append(self._execute_single_tool_call(tc, session_id))
            results = await asyncio.gather(*tasks, return_exceptions=False)

            # Check for rejections and add results to context
            rejected_tools = []
            for tool_call, result in zip(tool_calls, results):
                context_manager.add_tool_result(
                    tool_call['id'],
                    tool_call['name'],
                    result
                )

                # Check if this tool was rejected
                if self._is_tool_rejected(result):
                    rejected_tools.append(tool_call['name'])

            # If any tool was rejected, interrupt immediately
            if rejected_tools:
                raise UserRejectionInterruption(session_id, rejected_tools)

        # Continue recursively - pass True if we executed tools this round
        return await self._recursive_tool_calling(session_id, iterations + 1, bool(tool_calls))

    # ========== SPECIALIZED CONTENT GENERATION INTERFACES ==========

    async def generate_title_from_messages(
        self,
        latest_messages: List[BaseMessage]
    ) -> Optional[str]:
        """
        [Optional Interface] Generate title from conversation messages.
        
        Args:
            latest_messages: Recent conversation messages to generate title from
            
        Returns:
            Generated title string, or None if failed
            
        Raises:
            NotImplementedError: If client doesn't support this functionality
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support title generation"
        )

    async def generate_text_to_image_prompt(
        self, 
        session_id: Optional[str] = None
    ) -> Optional[Dict[str, str]]:
        """
        [Optional Interface] Generate text-to-image prompt.
        
        Args:
            session_id: Session ID for getting context
            
        Returns:
            Dictionary containing text prompt and negative prompt, or None if failed
            
        Raises:
            NotImplementedError: If client doesn't support this functionality
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support image prompt generation"
        )

    async def perform_web_search(self, query: str, **kwargs) -> Dict[str, Any]:
        """
        [Optional Interface] Perform web search.
        
        Args:
            query: Search query
            **kwargs: Additional search parameters
            
        Returns:
            Dictionary containing search results
            
        Raises:
            NotImplementedError: If client doesn't support this functionality  
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support web search"
        )


    # ========== ABSTRACT HELPER METHODS FOR PROVIDER-SPECIFIC LOGIC ==========

    @abstractmethod
    def _should_continue_tool_calling(self, response: Any) -> bool:
        """
        Check if response contains tool calls that require execution.
        
        Args:
            response: Provider-specific response object to check
            
        Returns:
            bool: True if tool calls are present and execution should continue
        """
        pass

    @abstractmethod
    def _extract_tool_calls(self, response: Any) -> List[Dict[str, Any]]:
        """
        Extract tool calls from provider-specific response.
        
        Args:
            response: Provider-specific response object
            
        Returns:
            List[Dict[str, Any]]: List of tool call dictionaries with structure:
                - id: str - Tool call identifier
                - name: str - Tool name
                - args/arguments: Dict[str, Any] - Tool parameters (key varies by provider)
        """
        pass

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

    def _is_tool_rejected(self, tool_result: Dict[str, Any]) -> bool:
        """
        Check if tool execution was rejected by user.

        Args:
            tool_result: Tool execution result dictionary

        Returns:
            bool: True if tool was rejected by user, False otherwise
        """
        return tool_result.get('user_rejected', False)

    def _extract_thinking_content(self, response) -> Optional[str]:
        """
        Extract thinking content from provider response (optional override).
        
        Args:
            response: Provider-specific response object
            
        Returns:
            Optional[str]: Thinking content if available, None otherwise
        """
        # Default implementation - providers can override if they support thinking
        try:
            processor = self._get_response_processor()
            if processor and hasattr(processor, 'extract_thinking_content'):
                return processor.extract_thinking_content(response)
        except Exception:
            pass
        return None

    def _extract_text_from_response(self, response: Any) -> str:
        """
        Extract text content from provider-specific response using response processor.
        
        This method provides a unified interface for extracting text content from
        LLM responses across all providers. It delegates to provider-specific
        response processors to handle format differences.
        
        Args:
            response: Provider-specific response object
            
        Returns:
            str: Extracted text content for display and processing
            
        Note:
            This method is used to generate better action in tool calling
            notifications by extracting the actual LLM response text instead
            of using generic messages.
        """
        try:
            processor = self._get_response_processor()
            return processor.extract_text_content(response) if processor else ""
        except Exception:
            # Fallback to empty string on extraction failure
            return ""

    async def _execute_single_tool_call(
        self,
        tool_call: Dict[str, Any],
        session_id: Optional[str]
    ) -> Dict[str, Any]:
        """
        Execute single tool call with comprehensive error handling.
        
        Unified implementation for all providers. Returns standardized tool result 
        dictionaries from the tool manager layer.
        
        Args:
            tool_call: Tool call specification with structure:
                - id: str - Unique tool call identifier
                - name: str - Tool name to execute
                - args/arguments: Dict[str, Any] - Tool parameters (key varies by provider)
            session_id: Session ID for context-specific tool execution
            debug: Enable detailed debug logging and error tracing
            
        Returns:
            Dict[str, Any]: Tool execution result from tool manager with structure:
                - inline_data: Dict - Multimodal content or empty {}
                - llm_content: Any - Tool's textual/structured response
                
                For error cases, the tool manager returns a ToolResult dict with:
                - status: "error"
                - message: User-facing error message
                - llm_content: Formatted error for LLM
                - data: Error details and metadata
                      
        Note:
            All providers use this unified implementation. The tool manager handles
            all error cases and returns proper dictionaries, not error strings.
        """
        try:
            from backend.config import get_llm_settings

            # Tool manager always returns Dict[str, Any]
            if self.tool_manager:
                result = await self.tool_manager.handle_function_call(
                    tool_call, session_id
                ) # type: ignore
            else:
                result = {
                    'status': 'error',
                    'message': 'Tool manager not initialized',
                    'error': 'Tool execution unavailable'
                }
            
            return result
            
        except Exception as e:
            # Tool execution failed - log and re-raise to stop execution
            from backend.config import get_llm_settings
            debug = get_llm_settings().debug
            if debug:
                print(f"[DEBUG] Tool execution failed: {tool_call.get('name', 'unknown')} - {str(e)}")
            
            # Re-raise the exception to stop tool calling loop
            raise e


    # ========== SHARED UTILITY METHODS ==========

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
        extracted_text = self._extract_text_from_response(current_response)
        thinking_content = self._extract_thinking_content(current_response)
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

    # ========== SESSION CONTEXT MANAGER MANAGEMENT ==========

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

    def get_context_manager(self, session_id: str) -> Optional[BaseContextManager]:
        """
        Get existing context manager for session.

        Args:
            session_id: Session identifier

        Returns:
            Optional[BaseContextManager]: Context manager if exists, None otherwise
        """
        return self._session_context_managers.get(session_id)

    def cleanup_session_context(self, session_id: str) -> None:
        """
        Clean up context manager for ended session.

        Args:
            session_id: Session identifier to clean up
        """
        if session_id in self._session_context_managers:
            self._session_context_managers[session_id].clear_runtime_context()
            del self._session_context_managers[session_id]
