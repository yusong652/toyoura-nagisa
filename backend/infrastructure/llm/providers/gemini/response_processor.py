"""
Gemini-specific response processor.

Handles processing of Gemini API responses, extracting content, tool calls, and metadata.
"""

from typing import List, Dict, Any, Optional
from backend.domain.models.messages import BaseMessage, AssistantMessage
from backend.domain.models.streaming import StreamingChunk
from backend.infrastructure.llm.base.response_processor import BaseResponseProcessor, BaseStreamingProcessor
from google.genai import types


class GeminiStreamingProcessor(BaseStreamingProcessor):
    """
    Stateful streaming processor for Gemini API.

    Processes Gemini GenerateContentResponse chunks and converts them
    into standardized StreamingChunk objects. Gemini is stateless (each
    chunk is independent), so this processor has no persistent state.
    """

    def process_event(self, event: Any) -> List[StreamingChunk]:
        """
        Process Gemini streaming chunk into standardized StreamingChunk objects.

        Args:
            event: Gemini GenerateContentResponse chunk

        Returns:
            List[StreamingChunk]: List of standardized chunks (one per part)
        """
        result = []

        # Validate chunk structure
        if not hasattr(event, 'candidates') or not event.candidates:
            return result
        if not event.candidates[0].content:
            return result
        # Check both existence AND non-None value
        if not hasattr(event.candidates[0].content, 'parts') or not event.candidates[0].content.parts:
            return result

        # Extract usage metadata from this chunk (will be in last chunk for streaming)
        usage_info = {}
        if hasattr(event, 'usage_metadata') and event.usage_metadata:
            usage = event.usage_metadata
            usage_info = {
                'prompt_token_count': getattr(usage, 'prompt_token_count', None),
                'candidates_token_count': getattr(usage, 'candidates_token_count', None),
                'total_token_count': getattr(usage, 'total_token_count', None),
                'thoughts_token_count': getattr(usage, 'thoughts_token_count', None),
            }

        # Process each part in the chunk
        for part in event.candidates[0].content.parts:
            # Thinking part (with thought flag)
            if hasattr(part, 'thought') and part.thought and hasattr(part, 'text') and part.text:
                result.append(StreamingChunk(
                    chunk_type="thinking",
                    content=part.text,
                    metadata={
                        "thought": True,
                        "has_signature": bool(getattr(part, 'thought_signature', None)),
                        **usage_info  # Include usage metadata
                    },
                    thought_signature=part.thought_signature if hasattr(part, 'thought_signature') and part.thought_signature else None
                ))

            # Regular text part
            elif hasattr(part, 'text') and part.text and not getattr(part, 'thought', False):
                result.append(StreamingChunk(
                    chunk_type="text",
                    content=part.text,
                    metadata=usage_info  # Include usage metadata
                ))

            # Function call part
            elif hasattr(part, 'function_call') and part.function_call and hasattr(part.function_call, 'name') and part.function_call.name:
                # Extract args safely (convert to dict if needed, handle None)
                args = dict(part.function_call.args) if hasattr(part.function_call, 'args') and part.function_call.args else {}

                result.append(StreamingChunk(
                    chunk_type="function_call",
                    content=part.function_call.name,
                    metadata={
                        "args": args,
                        "has_signature": bool(getattr(part, 'thought_signature', None)),
                        **usage_info  # Include usage metadata
                    },
                    thought_signature=part.thought_signature if hasattr(part, 'thought_signature') and part.thought_signature else None,
                    function_call={
                        "name": part.function_call.name,
                        "args": args
                    }
                ))

        return result


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
            List[Dict[str, Any]]: List of tool calls with id, name, arguments, thought_signature
        """
        tool_calls = []

        if not hasattr(response, 'candidates') or not response.candidates:
            return tool_calls

        candidate = response.candidates[0]
        if not hasattr(candidate, 'content') or not candidate.content:
            return tool_calls

        if hasattr(candidate.content, 'parts'):
            import uuid
            for part in candidate.content.parts:
                if hasattr(part, 'function_call') and part.function_call:
                    func_call = part.function_call
                    # Generate unique ID for tool call if not provided by LLM
                    # This ID is used for user confirmation matching in frontend
                    tool_call_id = getattr(func_call, 'id', None)
                    if not tool_call_id:
                        tool_call_id = str(uuid.uuid4())

                    tool_call = {
                        'id': tool_call_id,
                        'name': func_call.name,
                        'arguments': dict(func_call.args) if hasattr(func_call, 'args') else {}
                    }

                    # Extract thought_signature if present (for tool calling chain validation)
                    if hasattr(part, 'thought_signature') and part.thought_signature:
                        import base64
                        tool_call['thought_signature'] = base64.b64encode(part.thought_signature).decode('utf-8')

                    tool_calls.append(tool_call)

        return tool_calls

    @staticmethod
    def extract_usage_metadata(response, max_tokens: int = 1048576) -> Optional[Dict[str, int]]:
        """
        Extract token usage information from Gemini API response.

        Args:
            response: Raw Gemini API response object
            max_tokens: Maximum context window size for the model (default: 1M for Gemini 2.0 Flash)

        Returns:
            Optional[Dict[str, int]]: Token usage statistics or None if not available
                - prompt_tokens: Input tokens (context window usage)
                - completion_tokens: Output tokens (AI response)
                - total_tokens: Total tokens used
                - tokens_left: Remaining tokens in context window
        """
        if not hasattr(response, 'usage_metadata') or not response.usage_metadata:
            print("[GeminiResponseProcessor] No usage_metadata found in response")
            return None

        usage = response.usage_metadata
        print(f"[GeminiResponseProcessor] Found usage_metadata: {usage}")

        # Extract token counts from Gemini usage_metadata
        prompt_tokens = getattr(usage, 'prompt_token_count', 0)
        completion_tokens = getattr(usage, 'candidates_token_count', 0)
        total_tokens = getattr(usage, 'total_token_count', 0)

        print(f"[GeminiResponseProcessor] Extracted: prompt={prompt_tokens}, completion={completion_tokens}, total={total_tokens}")

        # Calculate remaining tokens in context window
        tokens_left = max_tokens - prompt_tokens

        result = {
            'prompt_tokens': prompt_tokens,
            'completion_tokens': completion_tokens,
            'total_tokens': total_tokens,
            'tokens_left': max(0, tokens_left)  # Ensure non-negative
        }

        print(f"[GeminiResponseProcessor] Returning usage dict: {result}")
        return result

    @staticmethod
    def format_response_for_storage(response, tool_calls: Optional[List[Dict[str, Any]]] = None) -> BaseMessage:
        """
        Format Gemini API response for storage in conversation history.

        Args:
            response: Raw Gemini API response object
            tool_calls: Pre-extracted tool calls (optional). If provided, reuses these instead of re-extracting.
                       This ensures consistent IDs between extract_tool_calls() and format_response_for_storage().

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

        # Reuse pre-extracted tool calls if provided, otherwise extract now
        if tool_calls is None:
            tool_calls = GeminiResponseProcessor.extract_tool_calls(response)

        # Extract thinking content and text parts
        thinking_parts = []
        text_parts = []  # Collect ALL non-thinking text parts

        # Track tool call index to match with pre-extracted tool_calls
        tool_call_index = 0

        # Track thought_signature for thinking content
        thought_signature = None

        # Process all parts from the response
        if hasattr(candidate.content, 'parts'):
            for part in candidate.content.parts:
                if hasattr(part, 'text') and part.text:
                    # Categorize text content
                    if getattr(part, 'thought', False):
                        thinking_parts.append(part.text)
                        # Capture thought_signature if present (for tool calling chains)
                        if hasattr(part, 'thought_signature') and part.thought_signature:
                            thought_signature = part.thought_signature
                    else:
                        # Collect ALL non-thinking text parts (preserves order)
                        text_parts.append(part.text)
                elif hasattr(part, 'function_call') and part.function_call:
                    # Use pre-extracted tool call with consistent ID
                    if tool_call_index < len(tool_calls):
                        tool_call = tool_calls[tool_call_index]
                        tool_use_block = {
                            "type": "tool_use",
                            "id": tool_call['id'],  # Reuse ID from extract_tool_calls()
                            "name": tool_call['name'],
                            "input": tool_call['arguments']
                        }
                        # Add thought_signature if present (for tool calling chain validation)
                        if 'thought_signature' in tool_call:
                            tool_use_block['thought_signature'] = tool_call['thought_signature']
                        content.append(tool_use_block)
                        tool_call_index += 1

        # Build content list for storage
        if thinking_parts:
            full_thinking_content = "\n".join(thinking_parts).strip()
            if full_thinking_content:
                thinking_block = {
                    "type": "thinking",
                    "thinking": full_thinking_content,
                }
                # Add thought_signature if present (for tool calling chain validation)
                if thought_signature:
                    # Convert bytes to base64 string for JSON serialization
                    import base64
                    thinking_block["thought_signature"] = base64.b64encode(thought_signature).decode('utf-8')
                content.append(thinking_block)

        # Merge all text parts into single block for consistent rendering
        # Note: Multiple text blocks would render as separate lines in frontend
        if text_parts:
            combined_text = "".join(text_parts).strip()
            if combined_text:
                content.append({
                    "type": "text",
                    "text": combined_text
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

            # Extract part-level thinking (only location where thinking content exists)
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

    @staticmethod
    def format_response_for_context(response) -> Optional[Any]:
        """
        Format Gemini API response for working context.

        Extracts the raw Content object from Gemini API response for use in
        subsequent API calls. This maintains the original Gemini format including
        thinking chain, validation fields, and all metadata.

        This method centralizes the formatting logic previously in
        context_manager.add_response() for better separation of concerns.

        Args:
            response: Raw Gemini API response object

        Returns:
            Gemini Content object ready to append to working_contents, or None if invalid.
        """
        try:
            candidate = response.candidates[0]
        except (AttributeError, IndexError):
            return None

        # Return the raw Content object directly
        # This preserves all Gemini-specific fields (parts, thinking, validation, etc.)
        return candidate.content

    @staticmethod
    def construct_response_from_chunks(
        chunks: List[StreamingChunk]
    ) -> types.GenerateContentResponse:
        """
        Construct Gemini response object from collected streaming chunks.

        Converts list of StreamingChunk objects back into Gemini's native
        GenerateContentResponse format for tool call detection and context management.

        Args:
            chunks: List of StreamingChunk objects collected during streaming

        Returns:
            types.GenerateContentResponse: Complete Gemini response object with
                                          all parts preserved for tool calling

        Note:
            This reconstruction preserves all essential fields including:
            - Thinking content with thought flags
            - Text content
            - Function calls with thought_signature
            - All metadata needed for tool calling logic
        """
        # Convert StreamingChunk objects to Gemini Part format
        parts_data = []

        for chunk in chunks:
            part_dict = {}

            if chunk.chunk_type == "thinking":
                part_dict["text"] = chunk.content
                part_dict["thought"] = True
                if chunk.thought_signature:
                    part_dict["thought_signature"] = chunk.thought_signature

            elif chunk.chunk_type == "text":
                part_dict["text"] = chunk.content

            elif chunk.chunk_type == "function_call" and chunk.function_call:
                # Function call requires special handling
                # Skip if function_call is None (should not happen for function_call chunks)
                # Extract name and args with explicit types
                func_name = chunk.function_call.get("name")
                func_args = chunk.function_call.get("args", {})

                if func_name:  # Only create FunctionCall if name is present
                    part_dict["function_call"] = types.FunctionCall(
                        name=func_name,
                        args=func_args
                    )
                    if chunk.thought_signature:
                        part_dict["thought_signature"] = chunk.thought_signature

            if part_dict:
                parts_data.append(part_dict)

        # Build Gemini response structure
        # Create Part objects
        parts = []
        for part_data in parts_data:
            # Handle different part types appropriately
            if "function_call" in part_data:
                # Function call part
                part = types.Part(
                    function_call=part_data["function_call"]
                )
                # Add thought_signature if present
                if "thought_signature" in part_data:
                    part.thought_signature = part_data["thought_signature"]
            elif "thought" in part_data:
                # Thinking part
                part = types.Part(
                    text=part_data["text"],
                    thought=True
                )
                if "thought_signature" in part_data:
                    part.thought_signature = part_data["thought_signature"]
            else:
                # Regular text part
                part = types.Part(text=part_data["text"])

            parts.append(part)

        # Create Content with parts
        content = types.Content(parts=parts, role="model")

        # Create Candidate with content
        candidate = types.Candidate(
            content=content,
            finish_reason=types.FinishReason.STOP
        )

        # Create complete GenerateContentResponse
        response = types.GenerateContentResponse(candidates=[candidate])

        return response

    @staticmethod
    def create_streaming_processor() -> BaseStreamingProcessor:
        """
        Create Gemini streaming processor instance.

        Returns:
            GeminiStreamingProcessor: Stateful processor for Gemini streaming
        """
        return GeminiStreamingProcessor()