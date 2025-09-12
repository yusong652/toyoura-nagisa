"""
Enhanced LLM Client Base with SOTA streaming architecture.

This module provides the foundational LLMClientBase class that all provider-specific
clients inherit from, implementing common patterns extracted from the Gemini implementation.
"""

import asyncio
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, Tuple, AsyncGenerator, Union
from backend.domain.models.messages import BaseMessage
from backend.infrastructure.llm.base.context_manager import BaseContextManager
from backend.infrastructure.llm.base.message_formatter import BaseMessageFormatter
from backend.infrastructure.llm.base.response_processor import BaseResponseProcessor    


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
    
    def __init__(self, extra_config: Dict[str, Any] = None):
        """
        Initialize LLM client base class.
        
        Args:
            extra_config: Additional configuration parameters
        """
        self.extra_config = extra_config or {}
        
        # Common client attributes that all implementations should have
        self.client = None  # Will be set by concrete implementations
        self.tool_manager = None  # Will be initialized by concrete implementations
        
        # Enhanced context manager for runtime tool history preservation
        # Will be initialized with provider name and session_id when needed
        self.context_manager = None

    # ========== CORE STREAMING INTERFACE ==========

    async def get_response(
        self,
        messages: List[BaseMessage],
        session_id: Optional[str] = None,
        agent_profile: str = "general",
        enable_memory: bool = True,
        **kwargs
    ) -> AsyncGenerator[Union[Dict[str, Any], Tuple[BaseMessage, Dict[str, Any]]], None]:
        """
        [Core Interface] Get LLM response with real-time tool calling notifications.
        
        Unified implementation for all providers using provider-specific components.
        This method centralizes the common workflow while delegating provider-specific
        operations to abstract methods implemented by each provider.
        
        Args:
            messages: Input message list
            session_id: Session ID for tool and context management
            agent_profile: Agent profile type ("general", "coding", "lifestyle", "disabled", etc.)
            enable_memory: Whether to enable memory injection in system prompt (controlled by frontend)
            **kwargs: Additional parameters (like max_iterations, temperature, etc.)
            
        Yields:
            Union[Dict[str, Any], Tuple[BaseMessage, Dict[str, Any]]]:
            - Dict[str, Any]: Intermediate notifications (tool calling status updates)
            - Tuple[BaseMessage, Dict[str, Any]]: Final result (final_message, execution_metadata)
        """
        # === INITIALIZATION PHASE ===
        provider_config = self._get_provider_config()
        debug = getattr(provider_config, 'debug', False)
        
        if debug:
            provider_name = self.__class__.__name__.replace('Client', '')

        # Initialize or reuse enhanced context manager
        if self.context_manager is None or self.context_manager.session_id != session_id:
            # Need to create new enhanced context manager for this session
            # Get provider name for context manager
            provider_name = self.__class__.__name__.replace('Client', '').lower()
            
            # Create enhanced context manager with session tracking
            context_manager_class = self._get_context_manager()
            self.context_manager = context_manager_class(
                provider_name=provider_name,
                session_id=session_id
            )

            self.context_manager.initialize_session_from_history(messages)
        else:
            # Existing session - just add the new user message
            if messages:
                # Assume the last message is the new user input
                self.context_manager.add_user_message(messages[-1])
        
        context_manager = self.context_manager
        
        # Execution metadata - unified across all providers
        metadata = {
            'session_id': session_id,
            'iterations': 0,
            'api_calls': 0,
            'tool_calls_executed': 0,
            'status': 'running'
        }
        
        try:
            # === EXECUTION PHASE - Streaming tool calling loop ===
            from backend.config import get_llm_settings
            max_iterations = get_llm_settings().max_tool_iterations
            
            print(f"[DEBUG] LLMClientBase.get_response: about to call _streaming_tool_calling_loop with agent_profile={agent_profile}")
            
            final_response = None
            async for item in self._streaming_tool_calling_loop(
                context_manager, session_id, max_iterations, metadata, debug, agent_profile, enable_memory, **kwargs
            ):
                if isinstance(item, dict):
                    # Intermediate notification - yield directly to API layer
                    yield item
                else:
                    # Final response - save for subsequent processing
                    final_response = item
            
            # === FINALIZATION PHASE ===
            metadata['status'] = 'completed'
            
            # Extract thinking content if supported
            thinking_content = self._extract_thinking_content(final_response)
            if thinking_content:
                metadata['thinking_preserved'] = True
            
            # Extract keyword using shared utility
            processor = self._get_response_processor()
            original_text = processor.extract_text_content(final_response)
            if original_text:
                from backend.shared.utils.text_parser import parse_llm_output
                _, extracted_keyword = parse_llm_output(original_text)
                metadata['keyword'] = extracted_keyword
            
            # Send tool use concluded notification if tools were used
            if metadata['tool_calls_executed'] > 0:
                # Send both SSE and WebSocket notifications
                concluded_notification = {
                    'type': 'NAGISA_TOOL_USE_CONCLUDED'
                }
                yield concluded_notification
                
                # Also send WebSocket notification
                await self._send_websocket_tool_notification(
                    session_id, concluded_notification
                )
            
            # Create final storage message using provider-specific processor
            final_message = processor.format_response_for_storage(final_response)
            
            # Add final response to context manager for next round
            context_manager.add_response(final_message)
            
            # Yield final result
            yield (final_message, metadata)
            
        except Exception as e:
            metadata['status'] = 'failed'
            metadata['error'] = str(e)
            
            if debug:
                provider_name = self.__class__.__name__.replace('Client', '')
                print(f"[DEBUG] {provider_name} execution failed: {e}")
            
            # Yield error notification
            yield {
                'type': 'error',
                'error': f"Execution failed: {e}"
            }
            
            raise Exception(f"Execution failed: {e}")

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

    # ========== ABSTRACT TOOL CALLING METHODS ==========

    async def _streaming_tool_calling_loop(
        self,
        context_manager: BaseContextManager,
        session_id: Optional[str],
        max_iterations: int,
        metadata: Dict[str, Any],
        debug: bool,
        agent_profile: str = "general",
        enable_memory: bool = True,
        **kwargs
    ) -> AsyncGenerator[Union[Dict[str, Any], Any], None]:
        """
        Core streaming tool calling loop with real-time notifications.
        
        Implements the tool calling state machine with event-driven architecture for
        real-time status updates during tool execution sequences. This unified implementation
        works across all LLM providers by leveraging provider-specific components.
        
        Args:
            context_manager: Provider-specific context manager for conversation state:
                - Manages conversation history and working contents
                - Handles response integration and tool result addition
                - Provider-specific implementation (GeminiContextManager, etc.)
            session_id: Session ID for tool and context management
            max_iterations: Maximum number of tool calling iterations allowed
            metadata: Execution metadata dictionary with structure:
                - iterations: int - Current iteration count
                - api_calls: int - Total API calls made
                - tool_calls_executed: int - Number of tool calls executed
            debug: Enable detailed debug logging and tracing
            **kwargs: Additional API configuration parameters
            
        Yields:
            Union[Dict[str, Any], Any]:
            - Dict[str, Any]: Real-time notifications with structure:
                - type: str - Notification type ('NAGISA_IS_USING_TOOL', 'error', etc.)
                - tool_name: str - Name of tool being executed
                - action_text: str - Human-readable action description
            - Any: Final provider-specific response object for processing
            
        Raises:
            Exception: If maximum iterations exceeded or system-level errors occur
            
        Note:
            This method implements the core tool calling workflow:
            1. Execute API calls and check for tool calls
            2. Yield real-time notifications for each tool execution phase
            3. Maintain execution state and handle iteration limits
            4. Return final response for downstream processing
        """
        
        # Get initial response using provider-specific context with truncation
        from backend.config import get_llm_settings
        recent_messages_length = get_llm_settings().recent_messages_length
        working_contents = context_manager.get_working_contents(recent_messages_length=recent_messages_length)
        current_response = await self.call_api_with_context(
            working_contents, session_id=session_id, agent_profile=agent_profile, enable_memory=enable_memory, **kwargs
        )
        metadata['api_calls'] += 1
        
        # Tool calling state machine
        iteration = 0
        while iteration < max_iterations:
            metadata['iterations'] = iteration + 1
            
            # State check: whether to continue tool calling (provider-specific)
            if not self._should_continue_tool_calling(current_response):
                break
            
            # Tool calls detected - no flag needed, tool_calls_executed will track this
            
            # Add current response to context
            context_manager.add_response(current_response)
            
            # Extract and execute tool calls (provider-specific)
            tool_calls = self._extract_tool_calls(current_response)
            
            # Execute tool calls - parallel execution when multiple tools requested
            if tool_calls:
                num_tools = len(tool_calls)
                metadata['tool_calls_executed'] += num_tools
                
                # Extract LLM text content from current response
                extracted_text = self._extract_text_from_response(current_response)
                
                # Extract thinking content if available
                thinking_content = self._extract_thinking_content(current_response)
                
                # Extract tool names once for reuse
                tool_names = [tc.get('name', 'unknown') for tc in tool_calls]
                
                # Determine action text: use extracted LLM text or fallback to generic message
                if extracted_text and len(extracted_text.strip()) > 0:
                    action_text = extracted_text.strip()
                    # Limit text length for display purposes
                    if len(action_text) > 150:
                        action_text = action_text[:147] + "..."
                else:
                    # Fallback to tool-specific message
                    if num_tools == 1:
                        action_text = f"Using {tool_names[0]}..."
                    else:
                        action_text = f"Executing {num_tools} tools in parallel: {', '.join(tool_names)}..."
                
                notification = {
                    'type': 'NAGISA_IS_USING_TOOL',
                    'tool_names': tool_names,  # Always provide array of tool names
                    'action_text': action_text
                }
                
                if thinking_content:
                    notification['thinking'] = thinking_content
                
                # Send both SSE and WebSocket notifications
                yield notification
                
                # Also send WebSocket notification
                await self._send_websocket_tool_notification(
                    session_id, notification
                )
                
                # Execute all tools in parallel
                tasks = []
                for tc in tool_calls:
                    tasks.append(self._execute_tool_for_parallel_batch(tc, session_id, debug))
                
                results = await asyncio.gather(*tasks, return_exceptions=False)
                
                # Process results and add to context
                for tool_call, result in zip(tool_calls, results):
                    context_manager.add_tool_result(
                        tool_call['id'],
                        tool_call['name'],
                        result
                    )
                
                # Skip completion notifications - let LLM response show naturally
            
            # Get next round response with truncation
            working_contents = context_manager.get_working_contents(recent_messages_length=recent_messages_length)
            
            if debug:
                print(f"[DEBUG] Tool calling iteration {iteration + 1}")
            
            current_response = await self.call_api_with_context(
                working_contents, session_id=session_id, agent_profile=agent_profile, enable_memory=enable_memory, **kwargs
            )
            metadata['api_calls'] += 1
            
            iteration += 1
        
        # Check if maximum iterations reached
        if iteration >= max_iterations:
            yield {
                'type': 'error',
                'error': f"Exceeded max iterations ({max_iterations})"
            }
            raise Exception(f"Exceeded max iterations ({max_iterations})")
        
        # Tool calling loop completed - let get_response handle final notifications
        
        # Return final response
        yield current_response

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
    def _get_response_processor(self):
        """
        Get provider-specific response processor instance.
        
        Returns:
            Provider-specific response processor class (e.g., GeminiResponseProcessor)
        """
        pass

    @abstractmethod
    def _get_context_manager(self):
        """
        Get provider-specific context manager instance.
        
        Returns:
            Provider-specific context manager class (e.g., GeminiContextManager)
        """
        pass

    @abstractmethod
    def _get_provider_config(self):
        """
        Get provider-specific configuration object.
        
        Returns:
            Provider-specific config object with debug flag and other settings
        """
        pass

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
            if hasattr(processor, 'extract_thinking_content'):
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
            This method is used to generate better action_text in tool calling
            notifications by extracting the actual LLM response text instead
            of using generic messages.
        """
        try:
            processor = self._get_response_processor()
            return processor.extract_text_content(response)
        except Exception:
            # Fallback to empty string on extraction failure
            return ""

    async def _execute_single_tool_call(
        self,
        tool_call: Dict[str, Any],
        session_id: Optional[str],
        debug: bool
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
            if debug:
                print(f"[DEBUG] Executing tool: {tool_call.get('name', 'unknown')}")
            
            # Tool manager always returns Dict[str, Any]
            result = await self.tool_manager.handle_function_call(
                tool_call, session_id, debug
            )
            
            if debug:
                print(f"[DEBUG] Tool execution completed: {tool_call.get('name', 'unknown')}")
            
            return result
            
        except Exception as e:
            # Tool execution failed - log and re-raise to stop execution
            if debug:
                print(f"[DEBUG] Tool execution failed: {tool_call.get('name', 'unknown')} - {str(e)}")
            
            # Re-raise the exception to stop tool calling loop
            raise e

    async def _execute_tool_for_parallel_batch(
        self,
        tool_call: Dict[str, Any],
        session_id: Optional[str],
        debug: bool
    ) -> Dict[str, Any]:
        """
        Execute a single tool as part of a parallel batch execution.
        
        Thin wrapper around _execute_single_tool_call for parallel execution.
        The tool manager handles all normal error cases and returns proper ToolResult dicts.
        
        Args:
            tool_call: Tool call specification with structure:
                - id: str - Unique tool call identifier
                - name: str - Tool name to execute
                - args/arguments: Dict[str, Any] - Tool parameters
            session_id: Session ID for context-specific tool execution
            debug: Enable detailed debug logging
            
        Returns:
            Dict[str, Any]: Tool execution result with ToolResult structure
        """
        if debug:
            tool_name = tool_call.get('name', 'unknown')
            print(f"[DEBUG] Parallel batch tool call for {tool_name}:")
            print(f"[DEBUG] - Tool call structure: {tool_call}")
            
        return await self._execute_single_tool_call(
            tool_call, session_id, debug
        )

    # ========== SHARED UTILITY METHODS ==========

    async def _clear_session_tool_cache(self, session_id: str):
        """Clear session tool cache - shared implementation."""
        if self.tool_manager and hasattr(self.tool_manager, 'clear_session_tool_cache'):
            self.tool_manager.clear_session_tool_cache(session_id)
        
        # Also clear enhanced context manager if it's for this session
        if self.context_manager and self.context_manager.session_id == session_id:
            self.context_manager.clear_runtime_context()
            self.context_manager = None  # Reset for next session
    
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
            from backend.presentation.websocket.tool_notification_service import (
                notify_tool_started, notify_tool_concluded
            )
            
            notification_type = notification.get('type')
            
            if notification_type == 'NAGISA_IS_USING_TOOL':
                await notify_tool_started(
                    session_id=session_id,
                    tool_names=notification.get('tool_names', []),
                    action_text=notification.get('action_text', ''),
                    thinking=notification.get('thinking')
                )
            elif notification_type == 'NAGISA_TOOL_USE_CONCLUDED':
                await notify_tool_concluded(
                    session_id=session_id,
                    tool_names=notification.get('tool_names'),
                    results=notification.get('results')
                )
            
        except Exception as e:
            # Don't fail the main execution if WebSocket notification fails
            provider_name = self.__class__.__name__.replace('Client', '')
            print(f"[DEBUG] {provider_name} WebSocket tool notification failed: {e}")

    def update_config(self, **kwargs):
        """
        Update client configuration.
        
        Args:
            **kwargs: Configuration parameters to update (tools_enabled, etc.)
        """
        
        # agent_profile is now stateless - passed in each request, no longer stored
        
        # Handle other configuration parameters
        for key, value in kwargs.items():
            setattr(self, key, value)
            # Also update extra_config
            self.extra_config[key] = value
    
