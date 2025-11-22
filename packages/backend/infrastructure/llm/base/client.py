"""
Enhanced LLM Client Base with SOTA streaming architecture.

This module provides the foundational LLMClientBase class that all provider-specific
clients inherit from, implementing common patterns extracted from the Gemini implementation.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, Type, AsyncGenerator
from backend.domain.models.streaming import StreamingChunk
from backend.infrastructure.llm.base.context_manager import BaseContextManager
from backend.infrastructure.llm.base.response_processor import BaseResponseProcessor


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

    async def _clear_session_context(self, session_id: str):
        """Clear session context - shared implementation."""
        # Clear session-specific context manager
        self.cleanup_session_context(session_id)

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

    def clear_context_manager(self, session_id: str) -> None:
        """
        Clear cached context manager for a session, forcing reload on next request.

        This ensures the context manager is recreated with fresh data from storage,
        preventing stale state issues.

        Args:
            session_id: Session identifier to clear
        """
        if session_id in self._session_context_managers:
            del self._session_context_managers[session_id]

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
