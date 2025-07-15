"""
Response processing utilities for Gemini API.

Enhanced dual-mode response processor that handles:
1. Raw context preservation for tool calling sequences
2. Storage-optimized response formatting for message history
3. Advanced response analysis and state management
4. Comprehensive error handling and validation

This processor is the core component for maintaining context integrity
during multi-turn tool calling while ensuring proper storage format compatibility.
"""

from typing import List, Dict, Any, Optional, Tuple, Union
from backend.chat.models import LLMResponse, ResponseType, BaseMessage, message_factory
from .constants import PYDANTIC_METADATA_ATTRS
from backend.chat.utils import parse_llm_output


class ResponseProcessor:
    """
    Advanced dual-mode response processor for Gemini API interactions.
    
    This processor provides comprehensive response handling with two distinct modes:
    
    1. **Context Mode**: Preserves raw API responses for tool calling sequences
       - Maintains original thinking content and validation fields
       - Supports multi-turn tool calling context preservation
       - Optimized for API call chains
    
    2. **Storage Mode**: Formats responses for persistent storage
       - Standardized message format for history
       - Optimized for database storage and retrieval
       - Compatible with existing message models
    
    Key Features:
    - State-aware response analysis
    - Comprehensive error handling
    - Performance-optimized processing
    - Extensible design for future enhancements
    """

    @staticmethod
    def format_llm_response(response) -> LLMResponse:
        """
        [LEGACY] Format Gemini API response into LLMResponse object.
        
        This method maintains backward compatibility while serving as the
        foundation for storage mode processing.
        
        Args:
            response: Raw response from Gemini API
            
        Returns:
            LLMResponse object containing the formatted response
            
        Note:
            This method is kept for backward compatibility. New implementations
            should consider using the more specific dual-mode methods.
        """
        return ResponseProcessor._process_response_for_storage(response)

    @staticmethod
    def analyze_response_state(response) -> Dict[str, Any]:
        """
        Analyze raw Gemini API response and extract comprehensive state information.
        
        This method provides deep analysis of the response without modifying it,
        enabling intelligent decision-making for context management.
        
        Args:
            response: Raw Gemini API response object
            
        Returns:
            Dict containing response analysis:
            {
                'has_candidates': bool,
                'has_content': bool,
                'has_tool_calls': bool,
                'has_thinking': bool,
                'has_text': bool,
                'tool_call_count': int,
                'thinking_parts_count': int,
                'text_parts_count': int,
                'response_type': ResponseType,
                'validation_fields': List[str],
                'error_info': Optional[Dict]
            }
        """
        analysis = {
            'has_candidates': False,
            'has_content': False,
            'has_tool_calls': False,
            'has_thinking': False,
            'has_text': False,
            'tool_call_count': 0,
            'thinking_parts_count': 0,
            'text_parts_count': 0,
            'response_type': ResponseType.ERROR,
            'validation_fields': [],
            'error_info': None
        }
        
        try:
            # Basic structure validation
            if not hasattr(response, 'candidates'):
                analysis['error_info'] = {'type': 'missing_candidates', 'message': 'Response missing candidates'}
                return analysis
            
            if not response.candidates:
                analysis['error_info'] = {'type': 'empty_candidates', 'message': 'Response candidates list is empty'}
                return analysis
                
            analysis['has_candidates'] = True
            candidate = response.candidates[0]
            
            # Content structure analysis
            if not (hasattr(candidate, 'content') and hasattr(candidate.content, 'parts')):
                analysis['error_info'] = {'type': 'missing_content', 'message': 'Candidate missing content/parts'}
                return analysis
                
            analysis['has_content'] = True
            
            # Validation fields detection
            validation_fields = []
            
            for attr in dir(candidate):
                if (not attr.startswith('_') and 
                    attr not in PYDANTIC_METADATA_ATTRS and 
                    hasattr(candidate, attr)):
                    try:
                        value = getattr(candidate, attr)
                        if not callable(value) and attr not in ['content', 'parts']:
                            validation_fields.append(attr)
                    except:
                        pass
            analysis['validation_fields'] = validation_fields
            
            # Top-level thinking analysis
            if hasattr(candidate, 'thought') and candidate.thought:
                analysis['has_thinking'] = True
                analysis['thinking_parts_count'] += 1
            
            # Parts analysis
            for part in candidate.content.parts:
                if hasattr(part, 'function_call') and part.function_call:
                    analysis['has_tool_calls'] = True
                    analysis['tool_call_count'] += 1
                elif hasattr(part, 'text') and part.text:
                    if getattr(part, 'thought', False):
                        analysis['has_thinking'] = True
                        analysis['thinking_parts_count'] += 1
                    else:
                        analysis['has_text'] = True
                        analysis['text_parts_count'] += 1
            
            # Determine response type
            if analysis['has_tool_calls']:
                analysis['response_type'] = ResponseType.FUNCTION_CALL
            elif analysis['has_text'] or analysis['has_thinking']:
                analysis['response_type'] = ResponseType.TEXT
            else:
                analysis['response_type'] = ResponseType.ERROR
                analysis['error_info'] = {'type': 'no_content', 'message': 'No text or tool calls found'}
                
        except Exception as e:
            analysis['error_info'] = {
                'type': 'analysis_exception',
                'message': f'Error during response analysis: {str(e)}'
            }
            
        return analysis

    @staticmethod
    def should_continue_tool_calling(response) -> bool:
        """
        Determine if response contains tool calls requiring continuation.
        
        This method provides fast, optimized detection of tool calling requirements
        without full response processing overhead.
        
        Args:
            response: Raw Gemini API response object
            
        Returns:
            True if tool calling should continue, False otherwise
        """
        analysis = ResponseProcessor.analyze_response_state(response)
        return analysis['has_tool_calls'] and analysis['tool_call_count'] > 0

    @staticmethod
    def extract_tool_calls(response) -> List[Dict[str, Any]]:
        """
        Extract tool call information from raw response.
        
        Optimized for context preservation mode - extracts tool calls
        while maintaining all original metadata and validation fields.
        
        Args:
            response: Raw Gemini API response object
            
        Returns:
            List of tool call dictionaries with format:
            [{'name': str, 'arguments': dict, 'id': str, 'metadata': dict}]
        """
        tool_calls = []
        
        try:
            analysis = ResponseProcessor.analyze_response_state(response)
            if not analysis['has_tool_calls']:
                return tool_calls
                
            candidate = response.candidates[0]
            
            for part in candidate.content.parts:
                if hasattr(part, 'function_call') and part.function_call:
                    func_call = part.function_call
                    
                    # Extract arguments with fallback handling
                    arguments = {}
                    if hasattr(func_call, 'args') and func_call.args:
                        arguments = func_call.args
                    elif hasattr(func_call, 'arguments') and func_call.arguments:
                        arguments = func_call.arguments
                    
                    # Extract metadata for context preservation
                    metadata = {}
                    
                    for attr in dir(func_call):
                        if (not attr.startswith('_') and 
                            attr not in ['name', 'args', 'arguments', 'id'] and
                            attr not in PYDANTIC_METADATA_ATTRS):
                            try:
                                value = getattr(func_call, attr)
                                if not callable(value):
                                    metadata[attr] = value
                            except:
                                pass
                    
                    tool_call = {
                        'name': func_call.name,
                        'arguments': arguments,
                        'id': func_call.id or func_call.name,
                        'metadata': metadata
                    }
                    tool_calls.append(tool_call)
                    
        except Exception as e:
            # Log error but don't raise - return empty list for graceful degradation
            print(f"[WARNING] Error extracting tool calls: {e}")
            
        return tool_calls

    @staticmethod
    def format_response_for_storage(response, keyword: Optional[str] = None) -> BaseMessage:
        """
        Format response specifically for persistent storage.
        
        This method creates standardized message objects optimized for:
        - Database storage efficiency
        - Historical retrieval performance
        - Cross-LLM compatibility
        - Future migration support
        
        Args:
            response: Raw Gemini API response object
            keyword: Optional extracted keyword for categorization
            
        Returns:
            BaseMessage object ready for storage
            
        Raises:
            ValueError: If response cannot be formatted for storage
        """
        try:
            # Use the internal storage processor
            llm_response = ResponseProcessor._process_response_for_storage(response, keyword)
            
            # Convert to message format
            if llm_response.response_type == ResponseType.ERROR:
                raise ValueError(f"Cannot format error response for storage: {llm_response.content}")
            
            # 构建消息数据，根据响应类型决定是否包含tool_calls
            message_data = {
                "role": "assistant",
                "content": llm_response.content,
                "keyword": keyword or llm_response.keyword,
            }
            
            # 只有当响应类型是FUNCTION_CALL且有工具调用时才添加tool_calls
            if (llm_response.response_type == ResponseType.FUNCTION_CALL and 
                llm_response.tool_calls and len(llm_response.tool_calls) > 0):
                message_data["tool_calls"] = llm_response.tool_calls
            
            storage_message = message_factory(message_data)
            
            return storage_message
            
        except Exception as e:
            raise ValueError(f"Failed to format response for storage: {str(e)}")

    @staticmethod
    def extract_thinking_content(response) -> Optional[str]:
        """
        Extract all thinking content from response for context preservation.
        
        This method specifically extracts thinking content while preserving
        all validation metadata for context integrity.
        
        Args:
            response: Raw Gemini API response object
            
        Returns:
            Combined thinking content string, or None if no thinking found
        """
        thinking_parts = []
        
        try:
            analysis = ResponseProcessor.analyze_response_state(response)
            if not analysis['has_thinking']:
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
    def get_response_validation_info(response) -> Dict[str, Any]:
        """
        Extract validation information crucial for context preservation.
        
        This method captures validation fields that are essential for
        maintaining response integrity during tool calling sequences.
        
        Args:
            response: Raw Gemini API response object
            
        Returns:
            Dictionary containing validation information
        """
        validation_info = {
            'candidate_count': 0,
            'validation_fields': {},
            'content_metadata': {},
            'part_metadata': []
        }
        
        try:
            if hasattr(response, 'candidates') and response.candidates:
                validation_info['candidate_count'] = len(response.candidates)
                candidate = response.candidates[0]
                
                # Extract candidate-level validation fields
                for attr in dir(candidate):
                    if (not attr.startswith('_') and 
                        attr not in ['content'] and 
                        attr not in PYDANTIC_METADATA_ATTRS):
                        try:
                            value = getattr(candidate, attr)
                            if not callable(value):
                                validation_info['validation_fields'][attr] = str(value)
                        except:
                            pass
                
                # Extract content metadata
                if hasattr(candidate, 'content'):
                    content = candidate.content
                    
                    for attr in dir(content):
                        if (not attr.startswith('_') and 
                            attr not in ['parts'] and
                            attr not in PYDANTIC_METADATA_ATTRS):
                            try:
                                value = getattr(content, attr)
                                if not callable(value):
                                    validation_info['content_metadata'][attr] = str(value)
                            except:
                                pass
                    
                    # Extract part-level metadata
                    if hasattr(content, 'parts'):
                        for i, part in enumerate(content.parts):
                            part_meta = {'index': i, 'type': type(part).__name__}
                            
                            for attr in dir(part):
                                if (not attr.startswith('_') and 
                                    attr not in ['text', 'function_call'] and
                                    attr not in PYDANTIC_METADATA_ATTRS):
                                    try:
                                        value = getattr(part, attr)
                                        if not callable(value):
                                            part_meta[attr] = str(value)
                                    except:
                                        pass
                            validation_info['part_metadata'].append(part_meta)
                            
        except Exception as e:
            validation_info['error'] = str(e)
            
        return validation_info

    @staticmethod
    def _process_response_for_storage(response, keyword: Optional[str] = None) -> LLMResponse:
        """
        Internal method for processing responses in storage mode.
        
        This is the core storage processing logic, optimized for
        message history and database storage requirements.
        
        Args:
            response: Raw Gemini API response object
            keyword: Optional keyword for response categorization
            
        Returns:
            LLMResponse object formatted for storage
        """
        # Validate response structure
        if not (hasattr(response, 'candidates') and response.candidates):
            return LLMResponse(
                content=[{"type": "text", "text": ""}], 
                response_type=ResponseType.ERROR
            )

        candidate = response.candidates[0]
        
        content_list = []
        tool_calls = []
        thinking_parts = []
        text_parts = []
        
        # Extract top-level thought
        if hasattr(candidate, 'thought') and candidate.thought:
            thinking_parts.append(candidate.thought)
            
        # Process parts
        if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
            for part in candidate.content.parts:
                if hasattr(part, 'function_call') and part.function_call:
                    # Extract tool call information
                    tool_calls.append({
                        'name': part.function_call.name,
                        'arguments': part.function_call.args if hasattr(part.function_call, 'args') else part.function_call.arguments,
                        'id': part.function_call.id or part.function_call.name
                    })
                elif hasattr(part, 'text') and part.text:
                    # Categorize text content
                    if getattr(part, 'thought', False):
                        thinking_parts.append(part.text)
                    else:
                        text_parts.append(part.text)

        # Build content list for storage
        if thinking_parts:
            full_thinking_content = "\n".join(thinking_parts).strip()
            if full_thinking_content:
                content_list.append({
                    "type": "thinking",
                    "thinking": full_thinking_content,
                })
        
        # Process text content
        full_text_content = "".join(text_parts).strip()
        if full_text_content:
            response_text, extracted_keyword = parse_llm_output(full_text_content)
            content_list.append({
                "type": "text",
                "text": response_text
            })
            # Use provided keyword or extracted keyword
            if not keyword:
                keyword = extracted_keyword

        # Determine response type and create LLMResponse
        if tool_calls:
            return LLMResponse(
                content=content_list,
                response_type=ResponseType.FUNCTION_CALL,
                tool_calls=tool_calls,
                keyword=keyword
            )
        
        if content_list:
            return LLMResponse(
                content=content_list,
                response_type=ResponseType.TEXT,
                keyword=keyword
            )
            
        return LLMResponse(
            content=[{"type": "text", "text": "Empty response from model."}],
            response_type=ResponseType.ERROR
        ) 