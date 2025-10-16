"""
Gemini-specific response processor.

Handles processing of Gemini API responses, extracting content, tool calls, and metadata.
"""

from typing import List, Dict, Any, Optional
from backend.domain.models.messages import BaseMessage, AssistantMessage
from backend.infrastructure.llm.base.response_processor import BaseResponseProcessor


class GeminiResponseProcessor(BaseResponseProcessor):
    """
    Gemini-specific response processor.
    
    Handles processing of Gemini API responses with proper extraction of
    text content, tool calls, thinking content, and web search sources.
    """
    
    @staticmethod
    def extract_text_content(response) -> str:
        """
        Extract text content from Gemini API response.
        
        Args:
            response: Raw Gemini API response object
            
        Returns:
            str: Extracted text content
        """
        if not hasattr(response, 'candidates') or not response.candidates:
            return ""
        
        candidate = response.candidates[0]
        if not hasattr(candidate, 'content') or not candidate.content:
            return ""
        
        text_parts = []
        if hasattr(candidate.content, 'parts'):
            for part in candidate.content.parts:
                if hasattr(part, 'text') and part.text:
                    # Only extract non-thinking text parts
                    if not getattr(part, 'thought', False):
                        text_parts.append(part.text)
        
        return ''.join(text_parts).strip()
    
    @staticmethod
    def extract_tool_calls(response) -> List[Dict[str, Any]]:
        """
        Extract tool call information from Gemini API response.
        
        Args:
            response: Raw Gemini API response object
            
        Returns:
            List[Dict[str, Any]]: List of tool calls with id, name, arguments
        """
        tool_calls = []
        
        if not hasattr(response, 'candidates') or not response.candidates:
            return tool_calls
        
        candidate = response.candidates[0]
        if not hasattr(candidate, 'content') or not candidate.content:
            return tool_calls
        
        if hasattr(candidate.content, 'parts'):
            for part in candidate.content.parts:
                if hasattr(part, 'function_call') and part.function_call:
                    func_call = part.function_call
                    tool_call = {
                        'id': getattr(func_call, 'id', f"call_{len(tool_calls)}"),
                        'name': func_call.name,
                        'arguments': dict(func_call.args) if hasattr(func_call, 'args') else {}
                    }
                    tool_calls.append(tool_call)
        
        return tool_calls
    @staticmethod
    def format_response_for_storage(response) -> BaseMessage:
        """
        Format Gemini API response for storage in conversation history.
        
        Args:
            response: Raw Gemini API response object
            
        Returns:
            BaseMessage: Formatted message for storage
        """
        # Build content array for multimodal support
        content = []

        if not hasattr(response, 'candidates') or not response.candidates:
            return AssistantMessage(role="assistant", content=[{"type": "text", "text": ""}])

        candidate = response.candidates[0]
        if not hasattr(candidate, 'content') or not candidate.content:
            return AssistantMessage(role="assistant", content=[{"type": "text", "text": ""}])
        
        # Extract thinking content and text parts
        thinking_parts = []
        text_parts = []  # Collect ALL non-thinking text parts

        # Extract top-level thought
        if hasattr(candidate, 'thought') and candidate.thought:
            thinking_parts.append(str(candidate.thought))

        # Process all parts from the response
        if hasattr(candidate.content, 'parts'):
            for part in candidate.content.parts:
                if hasattr(part, 'text') and part.text:
                    # Categorize text content
                    if getattr(part, 'thought', False):
                        thinking_parts.append(part.text)
                    else:
                        # Collect ALL non-thinking text parts (preserves order)
                        text_parts.append(part.text)
                elif hasattr(part, 'function_call') and part.function_call:
                    # Include function calls in storage format
                    func_call = part.function_call
                    content.append({
                        "type": "tool_use",
                        "id": getattr(func_call, 'id', f"call_{len(content)}"),
                        "name": func_call.name,
                        "input": dict(func_call.args) if hasattr(func_call, 'args') else {}
                    })

        # Build content list for storage
        if thinking_parts:
            full_thinking_content = "\n".join(thinking_parts).strip()
            if full_thinking_content:
                content.append({
                    "type": "thinking",
                    "thinking": full_thinking_content,
                })

        # Add all text parts as separate blocks (preserves multipart responses)
        for text_part in text_parts:
            if text_part.strip():  # Only add non-empty parts
                content.append({
                    "type": "text",
                    "text": text_part  # Keep original format for proper markdown rendering
                })
        
        # If no content was extracted, add empty text
        if not content:
            content = [{"type": "text", "text": ""}]
        
        return AssistantMessage(role="assistant", content=content)
    
    @staticmethod
    def extract_thinking_content(response) -> Optional[str]:
        """
        Extract thinking/reasoning content from Gemini response.
        
        Args:
            response: Raw Gemini API response object
            
        Returns:
            Optional[str]: Extracted thinking content, None if not available
        """
        thinking_parts = []
        
        try:
            if not hasattr(response, 'candidates') or not response.candidates:
                return None
                
            candidate = response.candidates[0]
            
            # Extract top-level thought
            if hasattr(candidate, 'thought') and candidate.thought and str(candidate.thought).strip():
                thinking_parts.append(str(candidate.thought))
                
            # Extract part-level thinking
            if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                for part in candidate.content.parts:
                    if hasattr(part, 'text') and part.text and getattr(part, 'thought', False):
                        thinking_parts.append(str(part.text))
            
            return "\n".join(thinking_parts).strip() if thinking_parts else None
            
        except Exception as e:
            print(f"[WARNING] Error extracting thinking content: {e}")
            return None
    
    @staticmethod
    def extract_web_search_sources(response, debug: bool = False) -> List[Dict[str, Any]]:
        """
        Extract web search sources from Gemini response.
        
        Args:
            response: Raw Gemini API response object
            debug: Enable debug output
            
        Returns:
            List[Dict[str, Any]]: List of web search sources
        """
        sources = []
        
        if not hasattr(response, 'candidates') or not response.candidates:
            return sources
        
        candidate = response.candidates[0]
        
        # Check for grounding metadata (Gemini's search results)
        if hasattr(candidate, 'groundingMetadata'):
            grounding = candidate.groundingMetadata
            if hasattr(grounding, 'webSearchQueries'):
                for query in grounding.webSearchQueries:
                    if hasattr(query, 'searchResults'):
                        for result in query.searchResults:
                            source = {
                                'title': getattr(result, 'title', ''),
                                'url': getattr(result, 'uri', ''),
                                'snippet': getattr(result, 'snippet', ''),
                                'type': 'web_search'
                            }
                            sources.append(source)
        
        # Check for citations in content
        if hasattr(candidate, 'citationMetadata'):
            citations = candidate.citationMetadata
            if hasattr(citations, 'citationSources'):
                for citation in citations.citationSources:
                    source = {
                        'title': getattr(citation, 'title', ''),
                        'url': getattr(citation, 'uri', ''),
                        'snippet': '',
                        'type': 'citation'
                    }
                    sources.append(source)
        
        if debug and sources:
            print(f"[WebSearch] Extracted {len(sources)} sources from Gemini response")
        
        return sources
    
    @staticmethod
    def extract_combined_text_from_content(content: List[Dict[str, Any]]) -> str:
        """
        Extract and combine all text parts from content array.

        Used by frontend rendering and TTS processing to get complete text.
        Skips thinking, tool_use, and tool_result blocks.

        Args:
            content: Message content array with multiple parts (from AssistantMessage.content)

        Returns:
            str: Combined text from all text parts

        Example:
            >>> content = [
            ...     {"type": "text", "text": "Part 1"},
            ...     {"type": "tool_use", "name": "read"},
            ...     {"type": "text", "text": "Part 2"}
            ... ]
            >>> GeminiResponseProcessor.extract_combined_text_from_content(content)
            'Part 1Part 2'
        """
        text_parts = []
        for item in content:
            if isinstance(item, dict) and item.get('type') == 'text':
                text_parts.append(item.get('text', ''))
        return ''.join(text_parts)

    @staticmethod
    def has_tool_calls(response) -> bool:
        """
        Check if Gemini response contains tool calls.

        Args:
            response: Raw Gemini API response object

        Returns:
            bool: True if response contains tool calls
        """
        return len(GeminiResponseProcessor.extract_tool_calls(response)) > 0