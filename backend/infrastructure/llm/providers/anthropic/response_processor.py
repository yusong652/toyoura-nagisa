"""
Response processing utilities for Anthropic Claude API.

Handles parsing and formatting of Claude API responses, including tool calls,
multimodal content, and error handling.
"""

import json
from typing import Any, Dict, List, Optional, Tuple
import anthropic
from backend.domain.models.response_models import LLMResponse
from backend.domain.models.streaming import StreamingChunk
from backend.infrastructure.llm.base.response_processor import BaseResponseProcessor, BaseStreamingProcessor


class AnthropicStreamingProcessor(BaseStreamingProcessor):
    """
    Stateful streaming processor for Anthropic API.

    Processes Anthropic MessageStreamEvent events and converts them
    into standardized StreamingChunk objects. Maintains state across
    events to properly handle multi-event constructs like tool calls.
    """

    def __init__(self):
        """Initialize streaming processor with state tracking."""
        # Track thinking signature for current thinking block
        self.current_thinking_signature: Optional[str] = None
        # Track current content block type
        self.current_block_type: Optional[str] = None
        # Track current tool call being streamed
        self.current_tool_id: Optional[str] = None
        self.current_tool_name: Optional[str] = None
        self.accumulated_tool_json: str = ""

    def process_event(self, event: Any) -> List[StreamingChunk]:
        """
        Process Anthropic streaming event into standardized StreamingChunk objects.

        Args:
            event: Anthropic MessageStreamEvent

        Returns:
            List[StreamingChunk]: List of standardized chunks to yield
        """
        result = []

        # Track content block start to know what type we're in
        if hasattr(event, 'type') and event.type == "content_block_start":
            if hasattr(event, 'content_block') and hasattr(event.content_block, 'type'):
                self.current_block_type = event.content_block.type
                # Only ToolUseBlock has id and name attributes
                if self.current_block_type == "tool_use" and hasattr(event.content_block, 'id') and hasattr(event.content_block, 'name'):
                    self.current_tool_id = event.content_block.id
                    self.current_tool_name = event.content_block.name
                    self.accumulated_tool_json = ""

        # Thinking content
        elif hasattr(event, 'type') and event.type == "thinking":
            if hasattr(event, 'thinking'):
                result.append(StreamingChunk(
                    chunk_type="thinking",
                    content=event.thinking,
                    metadata={"snapshot": getattr(event, 'snapshot', None)}
                ))

        # Text content
        elif hasattr(event, 'type') and event.type == "text":
            if hasattr(event, 'text'):
                result.append(StreamingChunk(
                    chunk_type="text",
                    content=event.text,
                    metadata={"snapshot": getattr(event, 'snapshot', None)}
                ))

        # Signature event (for thinking blocks)
        elif hasattr(event, 'type') and event.type == "signature":
            if hasattr(event, 'signature'):
                self.current_thinking_signature = event.signature

        # Tool parameters (partial JSON)
        elif hasattr(event, 'type') and event.type == "input_json":
            if self.current_tool_id and hasattr(event, 'partial_json'):
                self.accumulated_tool_json += event.partial_json

        # Content block complete
        elif hasattr(event, 'type') and event.type == "content_block_stop":
            # If this was a tool use block, emit the complete tool call
            if self.current_tool_id and self.current_tool_name:
                # Parse accumulated JSON
                try:
                    tool_input = json.loads(self.accumulated_tool_json) if self.accumulated_tool_json else {}
                except json.JSONDecodeError:
                    tool_input = {}

                result.append(StreamingChunk(
                    chunk_type="function_call",
                    content=self.current_tool_name,
                    metadata={
                        "tool_id": self.current_tool_id,
                        "tool_name": self.current_tool_name,
                        "tool_input": tool_input
                    },
                    thought_signature=self.current_thinking_signature.encode() if self.current_thinking_signature else None,
                    function_call={
                        "name": self.current_tool_name,
                        "args": tool_input,
                        "id": self.current_tool_id
                    }
                ))

                # Reset tool tracking
                self.current_tool_id = None
                self.current_tool_name = None
                self.accumulated_tool_json = ""
                self.current_thinking_signature = None
                self.current_block_type = None

            # If this was a thinking block and we have a signature, emit a marker chunk
            elif self.current_block_type == "thinking" and self.current_thinking_signature:
                # Emit a special chunk to mark the end of thinking with signature
                result.append(StreamingChunk(
                    chunk_type="thinking",
                    content="",  # Empty content, just carrying the signature
                    metadata={"is_signature_marker": True},
                    thought_signature=self.current_thinking_signature.encode()
                ))
                self.current_thinking_signature = None
                self.current_block_type = None
            else:
                # Reset for other block types
                self.current_block_type = None

        return result


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
                # Anthropic always provides item.id, but fallback to UUID just in case
                import uuid
                tool_call_id = item.id if hasattr(item, 'id') and item.id else str(uuid.uuid4())

                tool_calls.append({
                    "id": tool_call_id,
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
    def format_response_for_storage(response: Any, tool_calls: Optional[List[Dict[str, Any]]] = None):
        """
        Format Anthropic API response for storage as BaseMessage.

        This method creates standardized message objects optimized for:
        - Database storage efficiency
        - Historical retrieval performance
        - Cross-LLM compatibility

        Args:
            response: Raw Anthropic API response object
            tool_calls: Pre-extracted tool calls (optional). If provided, reuses these instead of re-extracting.
                       This ensures consistent IDs between extract_tool_calls() and format_response_for_storage().

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

        # Create mapping from name to tool_call for reuse
        tool_calls_map = {}
        if tool_calls:
            for tc in tool_calls:
                tool_calls_map[tc['name']] = tc

        for item in response.content:
            if item.type == "text":
                content_list.append({"type": "text", "text": item.text})
                text_content += item.text
            elif item.type == "thinking":
                # Preserve signature field (required by Anthropic API)
                content_list.append({
                    "type": "thinking",
                    "thinking": item.thinking,
                    "signature": item.signature
                })
            elif item.type == "tool_use":
                # Reuse pre-extracted tool call if available (to preserve IDs)
                if item.name in tool_calls_map:
                    tool_call = tool_calls_map[item.name]
                    content_list.append({
                        "type": "tool_use",
                        "id": tool_call['id'],
                        "name": tool_call['name'],
                        "input": item.input
                    })
                else:
                    # Fallback: generate new ID if not in pre-extracted tool_calls
                    import uuid
                    tool_call_id = item.id if hasattr(item, 'id') and item.id else str(uuid.uuid4())
                    content_list.append({
                        "type": "tool_use",
                        "id": tool_call_id,
                        "name": item.name,
                        "input": item.input
                    })

        # Note: keyword parsing is handled at display layer, preserve original text

        return AssistantMessage(
            role="assistant",
            content=content_list
        )

    @staticmethod
    def format_response_for_context(response: Any) -> Optional[Dict[str, Any]]:
        """
        Format Anthropic API response for working context.

        Extracts data from API response and builds message dict in Anthropic API
        format for use in subsequent API calls.

        This method centralizes the formatting logic previously in
        context_manager.add_response() for better separation of concerns.

        Args:
            response: Raw Anthropic API response object

        Returns:
            Message dict ready to append to working_contents, or None if invalid.

            Message dict structure:
                {
                    "role": "assistant",
                    "content": [...]  # Original Anthropic content blocks
                }
        """
        if not hasattr(response, 'content') or not response.content:
            return None

        # Build message dict in Anthropic API format
        filtered_message = {
            "role": response.role,
            "content": response.content
        }

        return filtered_message

    @staticmethod
    def construct_response_from_chunks(chunks: List['StreamingChunk']) -> 'anthropic.types.Message':
        """
        Construct Anthropic Message object from collected streaming chunks.

        Converts list of StreamingChunk objects back into Anthropic's native
        Message format for tool call detection and context management.

        Args:
            chunks: List of StreamingChunk objects collected during streaming

        Returns:
            anthropic.types.Message: Complete Anthropic Message object with
                                     all content blocks preserved for tool calling

        Note:
            This reconstruction preserves all essential fields including:
            - Thinking content with signatures
            - Text content
            - Tool use blocks with IDs and inputs
            - All metadata needed for tool calling logic
        """
        import anthropic
        from backend.domain.models.streaming import StreamingChunk

        content_blocks = []

        # Track accumulated content for each type
        accumulated_thinking = ""
        accumulated_text = ""
        current_thinking_signature: Optional[str] = None

        for chunk in chunks:
            if chunk.chunk_type == "thinking":
                # Only accumulate non-empty content (skip signature markers)
                if chunk.content or not chunk.metadata.get("is_signature_marker"):
                    accumulated_thinking += chunk.content
                # Store signature if present
                if chunk.thought_signature:
                    current_thinking_signature = chunk.thought_signature.decode()

            elif chunk.chunk_type == "text":
                # If we have accumulated thinking, add it as a block first
                if accumulated_thinking:
                    content_blocks.append({
                        "type": "thinking",
                        "thinking": accumulated_thinking,
                        "signature": current_thinking_signature or ""
                    })
                    accumulated_thinking = ""
                    current_thinking_signature = None

                accumulated_text += chunk.content

            elif chunk.chunk_type == "function_call":
                # Add any accumulated thinking first
                if accumulated_thinking:
                    content_blocks.append({
                        "type": "thinking",
                        "thinking": accumulated_thinking,
                        "signature": current_thinking_signature or ""
                    })
                    accumulated_thinking = ""
                    current_thinking_signature = None

                # Add any accumulated text
                if accumulated_text:
                    content_blocks.append({
                        "type": "text",
                        "text": accumulated_text
                    })
                    accumulated_text = ""

                # Add tool use block
                content_blocks.append({
                    "type": "tool_use",
                    "id": chunk.metadata.get("tool_id", ""),
                    "name": chunk.metadata.get("tool_name", ""),
                    "input": chunk.metadata.get("tool_input", {})
                })

        # Add any remaining accumulated content
        if accumulated_thinking:
            content_blocks.append({
                "type": "thinking",
                "thinking": accumulated_thinking,
                "signature": current_thinking_signature or ""
            })
        if accumulated_text:
            content_blocks.append({
                "type": "text",
                "text": accumulated_text
            })

        # Construct Message object
        # Note: We use minimal required fields for reconstruction
        # Get the model name from config if available
        from backend.config.llm import get_llm_settings
        model_name = get_llm_settings().get_anthropic_config().model

        return anthropic.types.Message(
            id="reconstructed",
            content=content_blocks,
            model=model_name,
            role="assistant",
            stop_reason="end_turn",
            type="message",
            usage=anthropic.types.Usage(
                input_tokens=0,
                output_tokens=0
            )
        )

    @staticmethod
    def create_streaming_processor() -> BaseStreamingProcessor:
        """
        Create Anthropic streaming processor instance.

        Returns:
            AnthropicStreamingProcessor: Stateful processor for Anthropic streaming
        """
        return AnthropicStreamingProcessor()