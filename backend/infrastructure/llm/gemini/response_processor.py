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
from backend.domain.models.messages import BaseMessage
from backend.domain.models.message_factory import message_factory
from backend.infrastructure.llm.response_models import LLMResponse
from .shared.constants import PYDANTIC_METADATA_ATTRS
from backend.shared.utils.text_parser import parse_llm_output


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
                'is_error': bool,
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
            'is_error': True,  # Default to error until proven otherwise
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
            analysis['is_error'] = False  # Valid response structure
            
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
            
            # Parts analysis
            parts = candidate.content.parts if hasattr(candidate.content, 'parts') else []
            
            for part in parts:
                # Tool call detection
                if hasattr(part, 'function_call') and part.function_call:
                    analysis['has_tool_calls'] = True
                    analysis['tool_call_count'] += 1
                
                # Text content analysis
                if hasattr(part, 'text') and part.text:
                    if getattr(part, 'thought', False):
                        analysis['has_thinking'] = True
                        analysis['thinking_parts_count'] += 1
                    else:
                        analysis['has_text'] = True
                        analysis['text_parts_count'] += 1
            
            # Top-level thinking detection
            if hasattr(candidate, 'thought') and candidate.thought:
                analysis['has_thinking'] = True
                analysis['thinking_parts_count'] += 1
                
        except Exception as e:
            analysis['error_info'] = {'type': 'analysis_error', 'message': str(e)}
            analysis['is_error'] = True
            
        return analysis

    @staticmethod
    def should_continue_tool_calling(response) -> bool:
        """
        Determine if tool calling should continue based on response analysis.
        
        Args:
            response: Raw Gemini API response object
            
        Returns:
            True if tool calling should continue, False otherwise
        """
        analysis = ResponseProcessor.analyze_response_state(response)
        return analysis['has_tool_calls'] and not analysis['is_error']

    @staticmethod
    def extract_tool_calls(response) -> List[Dict[str, Any]]:
        """
        Extract tool calls from raw Gemini API response with enhanced context preservation.
        
        This method extracts all tool call information while preserving metadata
        for context management during multi-turn tool calling sequences.
        
        Args:
            response: Raw Gemini API response object
            
        Returns:
            List of tool call dictionaries with comprehensive metadata
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
    def format_response_for_storage(response) -> BaseMessage:
        """
        Format response specifically for persistent storage.
        
        This method creates standardized message objects optimized for:
        - Database storage efficiency
        - Historical retrieval performance
        - Cross-LLM compatibility
        - Future migration support
        
        The keyword is automatically extracted from the response text content.
        
        Args:
            response: Raw Gemini API response object
            
        Returns:
            BaseMessage object ready for storage
            
        Raises:
            ValueError: If response cannot be formatted for storage
        """
        try:
            # Use the internal storage processor (keyword is extracted automatically)
            llm_response = ResponseProcessor._process_response_for_storage(response)
            
            # Convert to message format
            if llm_response.is_error:
                raise ValueError(f"Cannot format error response for storage: {llm_response.content}")
            
            # 构建消息数据
            message_data = {
                "role": "assistant",
                "content": llm_response.content,
                "keyword": llm_response.keyword,
            }
            
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
    def extract_web_search_sources(response, debug: bool = False) -> List[Dict[str, Any]]:
        """
        Extract web search sources from grounding metadata in Gemini API response.
        
        This method processes grounding metadata to extract search sources
        with comprehensive debugging support.
        
        Args:
            response: Raw Gemini API response object
            debug: Enable debug output for source extraction
            
        Returns:
            List of source dictionaries with url, title, snippet, and index
        """
        sources = []
        
        try:
            analysis = ResponseProcessor.analyze_response_state(response)
            if analysis['is_error'] or not analysis['has_candidates']:
                if debug:
                    print("[WebSearch] No valid candidates found for source extraction")
                return sources
                
            candidate = response.candidates[0]
            
            # Extract grounding metadata for sources
            grounding_metadata = getattr(candidate, 'grounding_metadata', None)
            if not grounding_metadata:
                if debug:
                    print("[WebSearch] No grounding metadata found")
                return sources
                
            grounding_chunks = getattr(grounding_metadata, 'grounding_chunks', [])
            if debug:
                print(f"[WebSearch] Found {len(grounding_chunks)} grounding chunks")
            
            # Process grounding chunks according to official API structure
            for i, chunk in enumerate(grounding_chunks):
                if hasattr(chunk, 'web'):
                    web_info = chunk.web
                    # Extract comprehensive information
                    source_data = {
                        'url': getattr(web_info, 'uri', ''),
                        'title': getattr(web_info, 'title', ''),
                        'snippet': getattr(web_info, 'text', ''),
                        'index': i
                    }
                    
                    # Try to get additional metadata if available
                    if hasattr(web_info, 'snippet'):
                        source_data['snippet'] = web_info.snippet
                    
                    sources.append(source_data)
                    
                    if debug:
                        print(f"[WebSearch] Source {i+1}: {source_data['title']}")
                        print(f"[WebSearch]   URL: {source_data['url']}")
                        print(f"[WebSearch]   Snippet: {source_data['snippet'][:100]}...")
                        
                elif hasattr(chunk, 'uri'):  # Fallback for older format
                    source_data = {
                        'url': chunk.uri,
                        'title': getattr(chunk, 'title', ''),
                        'snippet': getattr(chunk, 'text', ''),
                        'index': i
                    }
                    sources.append(source_data)
                    
                    if debug:
                        print(f"[WebSearch] Source {i+1} (fallback): {source_data['title']}")
            
            # Also extract citation/grounding support information for debugging
            if debug and grounding_metadata and hasattr(grounding_metadata, 'grounding_supports'):
                grounding_supports = grounding_metadata.grounding_supports
                print(f"[WebSearch] Found {len(grounding_supports)} grounding supports")
                for j, support in enumerate(grounding_supports):
                    if hasattr(support, 'grounding_chunk_indices'):
                        chunk_indices = support.grounding_chunk_indices
                        print(f"[WebSearch] Support {j+1} references chunks: {chunk_indices}")
                        
        except Exception as e:
            if debug:
                print(f"[WebSearch] Error extracting sources: {e}")
            
        return sources

    @staticmethod
    def extract_text_content(response) -> str:
        """
        Extract text content from raw Gemini API response.
        
        This method extracts only the text parts (not thinking parts) from
        the response, which can be used for tool usage notifications.
        
        Args:
            response: Raw Gemini API response object
            
        Returns:
            Extracted text content as string, empty if no text found
        """
        try:
            if not (hasattr(response, 'candidates') and response.candidates and 
                    hasattr(response.candidates[0], 'content')):
                return ""
            
            candidate = response.candidates[0]
            text_parts = []
            
            if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                for part in candidate.content.parts:
                    if hasattr(part, 'text') and part.text:
                        # Only extract non-thinking text parts
                        if not getattr(part, 'thought', False):
                            text_parts.append(part.text)
            
            return "".join(text_parts).strip()
            
        except Exception as e:
            print(f"[WARNING] Error extracting text content: {e}")
            return ""

    @staticmethod
    def _process_response_for_storage(response) -> LLMResponse:
        """
        Internal method for processing responses in storage mode.
        
        This is the core storage processing logic, optimized for
        message history and database storage requirements.
        
        The keyword is automatically extracted from the response text content.
        
        Args:
            response: Raw Gemini API response object
            
        Returns:
            LLMResponse object formatted for storage
        """
        # Validate response structure
        analysis = ResponseProcessor.analyze_response_state(response)
        
        if analysis['is_error']:
            error_message = analysis.get('error_info', {}).get('message', 'Unknown error')
            return LLMResponse(
                content=error_message,
                error=error_message,
                keyword="neutral"  # Default keyword for error responses
            )

        candidate = response.candidates[0]
        
        content_list = []
        thinking_parts = []
        text_parts = []
        extracted_keyword = "neutral"  # Default keyword
        
        # Extract top-level thought
        if hasattr(candidate, 'thought') and candidate.thought:
            thinking_parts.append(candidate.thought)
            
        # Process parts
        if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
            for part in candidate.content.parts:
                if hasattr(part, 'text') and part.text:
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
        
        # Process text content and extract keyword
        full_text_content = "".join(text_parts).strip()
        if full_text_content:
            response_text, extracted_keyword = parse_llm_output(full_text_content)
            content_list.append({
                "type": "text",
                "text": response_text
            })

        # Create simplified LLMResponse
        if content_list:
            return LLMResponse(
                content=content_list,
                keyword=extracted_keyword
            )
            
        return LLMResponse(
            content=[{"type": "text", "text": "Empty response from model."}],
            keyword=extracted_keyword
        ) 