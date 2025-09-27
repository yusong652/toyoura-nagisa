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
        **kwargs
    ) -> Any:
        """
        Execute direct LLM API call with complete pre-formatted context.

        Performs a pure API call using complete context contents that already include
        all necessary tool schemas and system prompts. This is a clean separation
        between context preparation and API execution.

        Args:
            context_contents: Complete context contents in provider-specific format with structure:
                - Provider-specific message format (e.g., Gemini, OpenAI, Anthropic formats)
                - Message roles and content parts as required by each provider
                - Tool schemas already integrated into context
                - System prompts with tool descriptions already included
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
            # Complete context already prepared by upper layer
            response = await client.call_api_with_context(complete_context)

        Note:
            This method should be a pure API call without session or tool dependencies.
            All context preparation including tool schemas should be handled by caller.
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

        # Get current state
        context_manager = self.get_or_create_context_manager(session_id)
        agent_profile = getattr(context_manager, 'agent_profile', 'general')
        enable_memory = getattr(context_manager, 'enable_memory', True)

        from backend.config import get_llm_settings
        recent_messages_length = get_llm_settings().recent_messages_length

        # Get tool schemas and system prompt at the proper layer
        tool_schemas = await self.get_function_call_schemas(session_id, agent_profile)

        # Get prompt tool schemas if tool manager is available
        prompt_tool_schemas = None
        if hasattr(self, 'tool_manager') and self.tool_manager is not None:
            try:
                # Type: ignore because tool_manager is dynamically set by concrete implementations
                prompt_tool_schemas = await self.tool_manager.get_schemas_for_system_prompt(session_id, agent_profile)  # type: ignore
            except (AttributeError, NotImplementedError):
                # Tool manager doesn't support this method
                prompt_tool_schemas = None

        # Build system prompt with tool schemas and memory
        from backend.shared.utils.prompt.builder import build_system_prompt
        system_prompt = await build_system_prompt(
            agent_profile=agent_profile,
            session_id=session_id,
            enable_memory=enable_memory,
            tool_schemas=prompt_tool_schemas
        )
        from backend.config import get_llm_settings
        debug = get_llm_settings().debug
        if debug:
            print(f"[DEBUG] System prompt for session {session_id}:\n{system_prompt}\n")

        # Get working contents and create complete context
        working_contents = context_manager.get_working_contents(recent_messages_length=recent_messages_length)

        # Prepare complete context with tools and system prompt
        complete_context = self._prepare_complete_context(
            working_contents=working_contents,
            tool_schemas=tool_schemas,
            system_prompt=system_prompt
        )

        # Pure API call with complete context
        current_response = await self.call_api_with_context(complete_context)

        # Check if we need to continue tool calling
        if not self._should_continue_tool_calling(current_response):
            # If previous round had tools and now we're done, send concluded notification
            if had_tools_in_previous_round:
                concluded_notification = {'type': 'NAGISA_TOOL_USE_CONCLUDED'}
                await self._send_websocket_tool_notification(session_id, concluded_notification)

            # Add final response to context manager before returning
            context_manager.add_response(current_response)
            return current_response  # Normal completion

        # Process tool calls
        context_manager.add_response(current_response)

        # Extract tool calls using response processor
        processor = self._get_response_processor()
        tool_calls = processor.extract_tool_calls(current_response) if processor else []

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
    def _prepare_complete_context(
        self,
        working_contents: List[Dict[str, Any]],
        tool_schemas: List[Any],
        system_prompt: Optional[str]
    ) -> List[Dict[str, Any]]:
        """
        Prepare complete context with tool schemas and system prompt.

        Args:
            working_contents: Base message contents from context manager
            tool_schemas: Tool schemas for API in provider-specific format
            system_prompt: System prompt with tool descriptions

        Returns:
            List[Dict[str, Any]]: Complete context ready for API call
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

    def cleanup_session_context(self, session_id: str) -> None:
        """
        Clean up context manager for ended session.

        Args:
            session_id: Session identifier to clean up
        """
        if session_id in self._session_context_managers:
            self._session_context_managers[session_id].clear_runtime_context()
            del self._session_context_managers[session_id]
