"""
Response processing utilities for Gemini API.

Handles conversion from Gemini API responses to internal LLMResponse format,
including thought extraction, tool calls parsing, and content organization.
"""

from typing import List, Dict, Any
from backend.chat.models import LLMResponse, ResponseType
from backend.chat.utils import parse_llm_output


class ResponseProcessor:
    """
    Handles response processing for Gemini API interactions.
    
    This class provides methods for:
    - Converting Gemini API responses to LLMResponse format
    - Extracting thinking content and tool calls
    - Organizing response content by type
    - Error handling for malformed responses
    """

    @staticmethod
    def format_llm_response(response) -> LLMResponse:
        """
        Format Gemini API response into LLMResponse object.
        
        Args:
            response: Raw response from Gemini API
        Returns:
            LLMResponse object containing the formatted response
        """
        if not (hasattr(response, 'candidates') and response.candidates):
            return LLMResponse(content=[{"type": "text", "text": ""}], response_type=ResponseType.ERROR)

        candidate = response.candidates[0]
        
        content_list = []
        tool_calls = []
        thinking_parts = []
        text_parts = []
        
        # 1. Extract top-level thought (high-level summary)
        if hasattr(candidate, 'thought') and candidate.thought:
            thinking_parts.append(candidate.thought)
            
        # 2. Iterate through parts, distinguishing between thought and text
        if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
            for part in candidate.content.parts:
                if hasattr(part, 'function_call') and part.function_call:
                    tool_calls.append({
                        'name': part.function_call.name,
                        'arguments': part.function_call.args if hasattr(part.function_call, 'args') else part.function_call.arguments,
                        'id': part.function_call.id or part.function_call.name
                    })
                elif hasattr(part, 'text') and part.text:
                    # Check if the part is a thought via `getattr(part, 'thought', False)`
                    if getattr(part, 'thought', False):
                        thinking_parts.append(part.text)
                    else:
                        text_parts.append(part.text)

        # 3. Combine thinking content
        if thinking_parts:
            full_thinking_content = "\n".join(thinking_parts).strip()
            if full_thinking_content:
                content_list.append({
                    "type": "thinking",
                    "thinking": full_thinking_content,
                })
        
        # 4. Combine text content
        full_text_content = "".join(text_parts).strip()
        if full_text_content:
            response_text, _ = parse_llm_output(full_text_content)
            content_list.append({
                "type": "text",
                "text": response_text
            })

        # 5. Return LLMResponse based on content
        if tool_calls:
            return LLMResponse(
                content=content_list,
                response_type=ResponseType.FUNCTION_CALL,
                tool_calls=tool_calls
            )
        
        if content_list:
            _, keyword = parse_llm_output(full_text_content)
            return LLMResponse(
                content=content_list,
                response_type=ResponseType.TEXT,
                keyword=keyword
            )
            
        return LLMResponse(
            content=[{"type": "text", "text": "Empty response from model."}],
            response_type=ResponseType.ERROR
        ) 