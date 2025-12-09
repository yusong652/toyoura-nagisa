"""
LLM Client Base Module.

Provides the foundational LLMClientBase abstract class that all provider-specific
clients inherit from. This is a pure infrastructure layer - it handles only API
communication, while business logic (agent loop, streaming orchestration, tool
execution) resides in the application layer (Agent, AgentService).
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, Type, AsyncGenerator
from backend.domain.models.streaming import StreamingChunk
from backend.infrastructure.llm.base.context_manager import BaseContextManager
from backend.infrastructure.llm.base.response_processor import BaseResponseProcessor


class LLMClientBase(ABC):
    """
    LLM client base class providing stateless API interfaces.

    This is a pure infrastructure component - business logic (agent loop, tool execution,
    streaming orchestration) has been moved to the application layer (Agent, AgentService).

    Core interfaces:
    - call_api_with_context(): Non-streaming API call for tool execution
    - call_api_with_context_streaming(): Streaming API call yielding StreamingChunk
    - _build_api_config(): Build provider-specific API configuration
    - get_or_create_context_manager(): Session-based context management

    Design principles:
    - Stateless: All session state passed as parameters, not stored in instance
    - Thread-safe: Supports concurrent sessions without state conflicts
    - Provider-agnostic: Unified interface across Gemini, Anthropic, OpenAI, etc.
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
            working_contents = context_manager.get_working_contents()
            api_config = self._build_api_config(system_prompt, tool_schemas)
            response = await self.call_api_with_context(working_contents, api_config)

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
            working_contents = context_manager.get_working_contents()
            api_config = self._build_api_config(system_prompt, tool_schemas)
            async for chunk in self.call_api_with_context_streaming(working_contents, api_config):
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
    def _get_response_processor(self) -> BaseResponseProcessor:
        """
        Get provider-specific response processor instance.

        Returns:
            BaseResponseProcessor: Provider-specific response processor instance
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
    def _build_api_config(
        self,
        system_prompt: str,
        tool_schemas: Optional[List[Any]]
    ) -> Dict[str, Any]:
        """
        Build provider-specific API configuration.

        This method constructs the API configuration dictionary specific to each
        LLM provider, including system prompt and tool schemas in the required format.

        Args:
            system_prompt: Pre-built system prompt
            tool_schemas: Tool schemas in provider-specific format (can be None)

        Returns:
            Dict[str, Any]: Provider-specific API configuration:
                - Gemini: {'config': GenerateContentConfig}
                - Anthropic: {'tools': [...], 'system_prompt': str}
                - OpenAI: {'tools': [...], 'instructions': str}
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
