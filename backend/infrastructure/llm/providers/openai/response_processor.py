"""
OpenAI Response Processor

Handles processing of OpenAI API responses including text extraction,
tool call detection, and response formatting for storage.
"""

import re
import json
from typing import List, Dict, Any, Optional
from backend.domain.models.messages import AssistantMessage
from backend.infrastructure.llm.base.response_processor import BaseResponseProcessor


class OpenAIResponseProcessor(BaseResponseProcessor):
    """
    Process OpenAI API responses and extract relevant information
    
    Handles tool call extraction, thinking content processing,
    and response formatting for consistent storage and display.
    """
    
    @staticmethod
    def extract_text_content(response) -> str:
        """
        Extract text content from OpenAI response
        
        Args:
            response: OpenAI API response object
            
        Returns:
            Extracted text content
        """
        if not hasattr(response, 'choices') or not response.choices:
            return ""
        
        choice = response.choices[0]
        if not hasattr(choice, 'message'):
            return ""
        
        return choice.message.content or ""
    
    @staticmethod
    def should_continue_tool_calling(response) -> bool:
        """
        Check if response contains tool calls requiring execution
        
        Args:
            response: OpenAI API response object
            
        Returns:
            True if tool calls are present and need execution
        """
        if not hasattr(response, 'choices') or not response.choices:
            return False
        
        choice = response.choices[0]
        if not hasattr(choice, 'message'):
            return False
        
        return (
            hasattr(choice.message, 'tool_calls') and 
            choice.message.tool_calls and 
            len(choice.message.tool_calls) > 0
        )
    
    @staticmethod
    def extract_tool_calls(response) -> List[Dict[str, Any]]:
        """
        Extract tool calls from OpenAI response
        
        Args:
            response: OpenAI API response object
            
        Returns:
            List of tool call dictionaries with name, arguments, and id
        """
        if not OpenAIResponseProcessor.should_continue_tool_calling(response):
            return []
        
        choice = response.choices[0]
        tool_calls = []
        
        for tool_call in choice.message.tool_calls:
            try:
                # Parse arguments if they're a JSON string
                arguments = tool_call.function.arguments
                if isinstance(arguments, str):
                    try:
                        parsed_args = json.loads(arguments)
                    except json.JSONDecodeError:
                        parsed_args = arguments
                else:
                    parsed_args = arguments
                
                tool_calls.append({
                    'name': tool_call.function.name,
                    'arguments': parsed_args,
                    'id': tool_call.id
                })
            except Exception as e:
                print(f"[WARNING] Failed to parse tool call: {e}")
                continue
        
        return tool_calls
    
    
    
    @staticmethod
    def format_response_for_storage(response) -> AssistantMessage:
        """
        Format OpenAI response for storage in message history
        
        Args:
            response: OpenAI API response object
            
        Returns:
            AssistantMessage object ready for storage
        """
        if not hasattr(response, 'choices') or not response.choices:
            return AssistantMessage(
                role="assistant",
                content=[{"type": "text", "text": ""}]
            )
        
        choice = response.choices[0].message
        content_blocks = []
        
        # Handle text content - preserve original format
        text_content = OpenAIResponseProcessor.extract_text_content(response)
        if text_content:
            content_blocks.append({
                "type": "text",
                "text": text_content
            })
        
        # Handle tool calls
        tool_calls = None
        if hasattr(choice, 'tool_calls') and choice.tool_calls:
            tool_calls = OpenAIResponseProcessor.extract_tool_calls(response)
        
        # Create AssistantMessage
        message = AssistantMessage(
            role="assistant",
            content=content_blocks if content_blocks else [{"type": "text", "text": ""}]
        )
        
        # Add tool calls if present
        if tool_calls:
            message.tool_calls = tool_calls
        
        return message
    
    @staticmethod
    def extract_web_search_sources(response, debug: bool = False) -> List[Dict[str, Any]]:
        """
        Extract web search sources from OpenAI response
        
        Note: OpenAI doesn't have built-in web search like Gemini.
        This method is a placeholder for MCP-based web search results.
        
        Args:
            response: OpenAI API response object
            debug: Enable debug output
            
        Returns:
            List of source dictionaries (empty for OpenAI)
        """
        if debug:
            print("[DEBUG] OpenAI doesn't support built-in web search - using MCP tools instead")
        
        return []  # OpenAI requires external tools for web search