"""
Enhanced LLM Client Base with SOTA streaming architecture.

This module provides the foundational LLMClientBase class that all provider-specific
clients inherit from, implementing common patterns extracted from the Gemini implementation.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, Tuple, AsyncGenerator, Union
from backend.domain.models.messages import BaseMessage


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
    
    def __init__(self, tools_enabled: bool = True, extra_config: Dict[str, Any] = None):
        """
        Initialize LLM client base class.
        
        Args:
            tools_enabled: Whether to enable tool calling functionality
            extra_config: Additional configuration parameters
        """
        self.tools_enabled = tools_enabled
        self.extra_config = extra_config or {}
        
        # Common client attributes that all implementations should have
        self.client = None  # Will be set by concrete implementations
        self.tool_manager = None  # Will be initialized by concrete implementations

    # ========== CORE STREAMING INTERFACE ==========

    @abstractmethod     
    async def get_response(
        self,
        messages: List[BaseMessage],
        session_id: Optional[str] = None,
        **kwargs
    ) -> AsyncGenerator[Union[Dict[str, Any], Tuple[BaseMessage, Dict[str, Any]]], None]:
        """
        [Core Interface] Get LLM response with real-time tool calling notifications.
        
        Architecture designed for real-time tool calling notifications using streaming state machine pattern:
        1. Real-time yield tool call start/progress/completion notifications
        2. Real-time yield tool execution progress and status updates
        3. Final yield complete response and execution metadata
        4. Complete error handling and recovery mechanisms
        
        This method is the core of the new architecture, solving traditional batch notification latency issues,
        allowing frontend to perceive tool calling status in real-time, significantly improving user experience.
        
        Args:
            messages: Input message list
            session_id: Session ID for tool and context management
            **kwargs: Additional parameters (like max_iterations, temperature, etc.)
            
        Yields:
            Union[Dict[str, Any], Tuple[BaseMessage, Dict[str, Any]]]:
            - Dict[str, Any]: Intermediate notifications (tool calling status updates)
            - Tuple[BaseMessage, Dict[str, Any]]: Final result (final_message, execution_metadata)
            
        Note:
            Notification format examples:
            - Tool start: {'type': 'NAGISA_IS_USING_TOOL', 'tool_name': 'search', 'action_text': 'Searching...'}
            - Tool progress: {'type': 'NAGISA_IS_USING_TOOL', 'tool_name': 'search', 'action_text': 'Using search tool...'}
            - Tool completion: {'type': 'NAGISA_IS_USING_TOOL', 'tool_name': 'search', 'action_text': 'Completed search'}
            - Sequence end: {'type': 'NAGISA_TOOL_USE_CONCLUDED'}
            - Final result: (final_message, {'execution_id': '...', 'tool_calls_executed': 3, ...})
        """
        pass

    # ========== ABSTRACT METHODS FOR PROVIDER-SPECIFIC IMPLEMENTATION ==========

    @abstractmethod
    async def get_function_call_schemas(self, session_id: str) -> List[Any]:
        """
        Get function call schemas for tool registration.
        
        Args:
            session_id: Session ID for context-specific tools (required for dependency injection)
            
        Returns:
            List[Any]: List of tool schemas in provider-specific format
        """
        pass

    @abstractmethod 
    async def call_api_with_context(
        self, 
        context_contents: List[Dict[str, Any]], 
        session_id: str,
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

    @abstractmethod
    async def _streaming_tool_calling_loop(
        self,
        context_manager: Any,
        session_id: Optional[str],
        max_iterations: int,
        metadata: Dict[str, Any],
        debug: bool,
        **kwargs
    ) -> AsyncGenerator[Union[Dict[str, Any], Any], None]:
        """
        Core streaming tool calling loop with real-time notifications.
        
        Implements the tool calling state machine with event-driven architecture for
        real-time status updates during tool execution sequences.
        
        Args:
            context_manager: Provider-specific context manager for conversation state:
                - Manages conversation history and working contents
                - Handles response integration and tool result addition
                - Provider-specific implementation (GeminiContextManager, etc.)
            session_id: Session ID for tool and context management
            max_iterations: Maximum number of tool calling iterations allowed
            metadata: Execution metadata dictionary with structure:
                - execution_id: str - Unique execution identifier
                - iterations: int - Current iteration count
                - api_calls: int - Total API calls made
                - tool_calls_executed: int - Number of tool calls executed
                - tool_calls_detected: bool - Whether any tool calls were found
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
        pass

    async def _execute_single_tool_call(
        self,
        tool_call: Dict[str, Any],
        session_id: Optional[str],
        execution_id: str,
        debug: bool
    ) -> Any:
        """
        Execute single tool call with comprehensive error handling.
        
        Unified implementation for all providers. Returns error strings for compatibility
        with existing error handling patterns.
        
        Args:
            tool_call: Tool call specification with structure:
                - id: str - Unique tool call identifier
                - name: str - Tool name to execute
                - args/arguments: Dict[str, Any] - Tool parameters (key varies by provider)
            session_id: Session ID for context-specific tool execution
            execution_id: Unique execution identifier for debugging and tracking
            debug: Enable detailed debug logging and error tracing
            
        Returns:
            Any: Tool execution result in standardized ToolResult format:
                - Success: Tool-specific result data from tool layer
                - Error: Error string "Tool execution failed: {error_message}"
                      
        Note:
            All providers use this unified implementation. Debug logging should be
            added here if needed for all providers, not in individual implementations.
        """
        try:
            if debug:
                print(f"[DEBUG] Executing tool: {tool_call.get('name', 'unknown')} in execution {execution_id}")
                # Could add more debug info here if needed for all providers
            
            result = await self.tool_manager.handle_function_call(
                tool_call, session_id, debug
            )
            
            if debug:
                print(f"[DEBUG] Tool execution completed: {tool_call.get('name', 'unknown')}")
            
            return result
            
        except Exception as e:
            # Return error string for unified error handling
            error_result = f"Tool execution failed: {str(e)}"
            
            if debug:
                print(f"[DEBUG] Tool execution failed: {tool_call.get('name', 'unknown')} - {str(e)}")
            
            return error_result

    # ========== SHARED UTILITY METHODS ==========

    def _generate_execution_id(self) -> str:
        """Generate unique execution ID."""
        import uuid
        return f"EXE_{str(uuid.uuid4())[:8]}"
    
    def _get_timestamp(self) -> float:
        """Get current timestamp."""
        import time
        return time.time()

    async def _clear_session_tool_cache(self, session_id: str):
        """Clear session tool cache - shared implementation."""
        if self.tool_manager and hasattr(self.tool_manager, 'clear_session_tool_cache'):
            self.tool_manager.clear_session_tool_cache(session_id)

    def update_config(self, **kwargs):
        """
        Update client configuration.
        
        Args:
            **kwargs: Configuration parameters to update
        """
        # Provide default implementation, subclasses can override
        for key, value in kwargs.items():
            setattr(self, key, value)
            # Also update extra_config
            self.extra_config[key] = value