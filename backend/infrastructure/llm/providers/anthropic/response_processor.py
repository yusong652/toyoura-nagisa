"""
Response processing utilities for Anthropic Claude API.

Handles parsing and formatting of Claude API responses, including tool calls,
multimodal content, and error handling.
"""

import json
from typing import Any, Dict, List, Optional, Tuple
from backend.domain.models.response_models import LLMResponse
from backend.infrastructure.llm.base.response_processor import BaseResponseProcessor


class AnthropicResponseProcessor(BaseResponseProcessor):
    """
    Processes Anthropic Claude API responses into standardized formats.
    
    This class handles:
    - Converting Claude API responses to LLMResponse objects
    - Extracting tool calls from responses
    - Processing multimodal content
    - Error handling and formatting
    """

    @staticmethod
    def extract_text_content(response: Any) -> str:
        """
        Extract text content from Claude API response.
        
        Args:
            response: Raw response from Anthropic Claude API
            
        Returns:
            str: Extracted text content
        """
        return AnthropicResponseProcessor.extract_text_from_response(response)

    @staticmethod
    def extract_text_from_response(response: Any) -> str:
        """
        Extract plain text content from Claude API response.
        
        Args:
            response: Raw response from Anthropic Claude API
            
        Returns:
            Extracted text content as string
        """
        if not hasattr(response, "content") or not response.content:
            return ""
            
        text_content = []
        for item in response.content:
            if item.type == "text":
                text_content.append(item.text)
                
        return "".join(text_content)

    @staticmethod
    def extract_tool_calls(response: Any) -> List[Dict[str, Any]]:
        """
        Extract tool calls from Claude API response.
        
        Args:
            response: Raw response from Anthropic Claude API
            
        Returns:
            List of tool call dictionaries
        """
        tool_calls = []
        
        if not hasattr(response, "content") or not response.content:
            return tool_calls
            
        for item in response.content:
            if item.type == "tool_use":
                tool_calls.append({
                    "id": item.id,
                    "name": item.name,
                    "arguments": item.input  # 统一使用 arguments 字段
                })
                
        return tool_calls

    @staticmethod
    def has_tool_calls(response: Any) -> bool:
        """
        Check if Claude API response contains tool calls.

        Args:
            response: Raw response from Anthropic Claude API

        Returns:
            bool: True if response contains tool calls, False otherwise
        """
        if not hasattr(response, "content") or not response.content:
            return False

        for item in response.content:
            if item.type == "tool_use":
                return True

        return False

    @staticmethod
    def format_error_response(error: Exception) -> LLMResponse:
        """
        Format an error into a standardized LLMResponse.
        
        Args:
            error: The exception that occurred
            
        Returns:
            LLMResponse containing error information
        """
        error_message = f"Anthropic API error: {str(error)}"
        
        return LLMResponse(
            content=[{"type": "text", "text": error_message}],
            error=str(error)
        )

    @staticmethod
    def validate_response(response: Any) -> Tuple[bool, Optional[str]]:
        """
        Validate that a Claude API response is properly formatted.
        
        Args:
            response: Raw response from Anthropic Claude API
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            if not hasattr(response, "content"):
                return False, "Response missing content attribute"
                
            if not response.content:
                return False, "Response content is empty"
                
            # Check that all content items have valid types
            valid_types = {"text", "tool_use"}
            for item in response.content:
                if not hasattr(item, "type"):
                    return False, "Content item missing type attribute"
                if item.type not in valid_types:
                    return False, f"Invalid content type: {item.type}"
                    
            return True, None
            
        except Exception as e:
            return False, f"Validation error: {str(e)}"

    @staticmethod
    def count_tokens_estimate(text: str) -> int:
        """
        Provide a rough estimate of token count for Claude models.
        
        Args:
            text: Text to estimate tokens for
            
        Returns:
            Estimated token count
        """
        # Rough approximation: 1 token ≈ 4 characters for English text
        # This is a very rough estimate and should not be used for precise calculations
        return len(text) // 4

    @staticmethod
    def extract_thinking_content(response: Any) -> Optional[str]:
        """
        Extract thinking content from Claude response if present.
        
        Args:
            response: Raw response from Anthropic Claude API
            
        Returns:
            Thinking content if found, None otherwise
        """
        if not hasattr(response, "content") or not response.content:
            return None
            
        thinking_parts = []
        for item in response.content:
            if item.type == "thinking":
                thinking_parts.append(item.thinking)
                
        return "\n".join(thinking_parts).strip() if thinking_parts else None

    @staticmethod
    def format_response_for_storage(response: Any):
        """
        Format Anthropic API response for storage as BaseMessage.

        This method creates standardized message objects optimized for:
        - Database storage efficiency
        - Historical retrieval performance
        - Cross-LLM compatibility

        Args:
            response: Raw Anthropic API response object

        Returns:
            BaseMessage object ready for storage
        """
        from backend.domain.models.messages import AssistantMessage

        if not hasattr(response, "content") or not response.content:
            return AssistantMessage(
                role="assistant",
                content=[{"type": "text", "text": ""}]
            )

        content_list = []
        text_content = ""

        for item in response.content:
            if item.type == "text":
                content_list.append({"type": "text", "text": item.text})
                text_content += item.text
            elif item.type == "thinking":
                content_list.append({"type": "thinking", "thinking": item.thinking})

        # Note: keyword parsing is handled at display layer, preserve original text

        return AssistantMessage(
            role="assistant",
            content=content_list
        )