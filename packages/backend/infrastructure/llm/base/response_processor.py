"""
Base response processor - Abstract base class for response processing.

This module provides the foundation for all provider-specific response processors,
ensuring consistent response handling across different LLM providers.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from backend.domain.models.messages import BaseMessage, AssistantMessage
from backend.domain.models.streaming import StreamingChunk


class BaseStreamingProcessor(ABC):
    """
    Base class for stateful streaming processors.

    Each provider implements a streaming processor that maintains state
    across multiple streaming events/chunks and converts them to StreamingChunk objects.

    This enables consistent handling of both simple chunk-based streaming (Gemini)
    and complex event-based streaming with state management (Anthropic, OpenAI, etc.).
    """

    @abstractmethod
    def process_event(self, event: Any) -> List[StreamingChunk]:
        """
        Process a single streaming event/chunk with state management.

        This method is called for each event/chunk in the stream. The processor
        maintains internal state across calls to properly handle multi-event
        constructs like tool calls, thinking blocks, etc.

        Args:
            event: Provider-specific streaming event or chunk:
                - Gemini: GenerateContentResponse chunk
                - Anthropic: MessageStreamEvent
                - OpenAI: Response event
                - Moonshot/Zhipu/OpenRouter: ChatCompletionChunk

        Returns:
            List[StreamingChunk]: List of standardized chunks to yield.
                                 May be empty if event is state-only (no output yet).
        """
        pass


class BaseResponseProcessor(ABC):
    """
    Abstract base class for response processors.
    
    Defines unified interface for processing LLM API responses, extracting content,
    handling tool calls, and formatting responses for storage and display.
    """
    
    @staticmethod
    @abstractmethod
    def extract_text_content(response) -> str:
        """
        Extract text content from LLM API response.
        
        Args:
            response: Raw LLM API response object
            
        Returns:
            str: Extracted text content
        """
        pass
    
    @staticmethod
    @abstractmethod
    def extract_tool_calls(response) -> List[Dict[str, Any]]:
        """
        Extract tool call information from LLM API response.
        
        Args:
            response: Raw LLM API response object
            
        Returns:
            List[Dict[str, Any]]: List of tool calls with name, arguments, id, etc.
        """
        pass
    
    @staticmethod
    @abstractmethod
    def format_response_for_storage(response, tool_calls: Optional[List[Dict[str, Any]]] = None) -> BaseMessage:
        """
        Format LLM API response for storage in conversation history.

        Args:
            response: Raw LLM API response object
            tool_calls: Pre-extracted tool calls (optional). If provided, reuses these instead of re-extracting.
                       This ensures consistent IDs between extract_tool_calls() and format_response_for_storage().

        Returns:
            BaseMessage: Formatted message for storage
        """
        pass
    
    @staticmethod
    def extract_thinking_content(response) -> Optional[str]:
        """
        Extract thinking/reasoning content from response (shared utility).
        
        Args:
            response: Raw LLM API response object
            
        Returns:
            Optional[str]: Extracted thinking content, None if not available
        """
        # Default implementation - providers can override
        return None
    
    @staticmethod
    def has_tool_calls(response) -> bool:
        """
        Check if response contains tool calls (shared utility).
        
        Args:
            response: Raw LLM API response object
            
        Returns:
            bool: True if response contains tool calls
        """
        # Default implementation - providers should override
        return False
    
    @staticmethod
    def extract_web_search_sources(response, debug: bool = False) -> List[Dict[str, Any]]:
        """
        Extract web search sources from response (shared utility for providers that support it).

        Args:
            response: Raw LLM API response object
            debug: Enable debug output

        Returns:
            List[Dict[str, Any]]: List of web search sources
        """
        # Default implementation - providers can override
        return []

    @staticmethod
    @abstractmethod
    def create_streaming_processor() -> BaseStreamingProcessor:
        """
        Create a stateful streaming processor instance for this provider.

        The streaming processor maintains state across multiple streaming events/chunks
        and converts them into standardized StreamingChunk objects.

        Returns:
            BaseStreamingProcessor: Provider-specific streaming processor instance

        Example:
            processor = self._get_response_processor().create_streaming_processor()
            async for event in stream:
                chunks = processor.process_event(event)
                for chunk in chunks:
                    yield chunk
        """
        pass

    @staticmethod
    @abstractmethod
    def construct_response_from_chunks(chunks: List[StreamingChunk]) -> Any:
        """
        Construct complete response object from collected streaming chunks.

        This method converts a list of StreamingChunk objects back into
        the provider's native response format for tool call detection and context management.

        Args:
            chunks: List of StreamingChunk objects collected during streaming

        Returns:
            Any: Provider-specific complete response object:
                - Gemini: types.GenerateContentResponse
                - Anthropic: anthropic.types.Message
                - OpenAI: openai.types.responses.Response
                - Moonshot: openai.types.chat.ChatCompletion
                - Zhipu: ChatCompletion-like object
                - OpenRouter: openai.types.chat.ChatCompletion
                - Must contain all necessary data for tool call detection

        Note:
            This reconstruction is necessary because we need the complete response
            for tool call detection and context management, while streaming provides
            only incremental chunks.
        """
        pass