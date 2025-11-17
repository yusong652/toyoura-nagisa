"""
OpenAI Response Processor

Handles processing of OpenAI API responses including text extraction,
tool call detection, and response formatting for storage.
"""

import json
from typing import List, Dict, Any, Optional
from openai.types.responses import (
    Response,
    ResponseFunctionToolCall,
    ResponseOutputMessage,
    ResponseReasoningItem,
    ResponseCompletedEvent,
    ResponseFunctionCallArgumentsDeltaEvent,
    ResponseFunctionCallArgumentsDoneEvent,
    ResponseOutputItemAddedEvent,
    ResponseReasoningTextDeltaEvent,
    ResponseReasoningSummaryPartAddedEvent,
    ResponseReasoningSummaryTextDeltaEvent,
    ResponseTextDeltaEvent,
)
from openai.types.responses.response_output_text import ResponseOutputText
from backend.domain.models.messages import AssistantMessage
from backend.domain.models.streaming import StreamingChunk
from backend.infrastructure.llm.base.response_processor import BaseResponseProcessor, BaseStreamingProcessor


class OpenAIStreamingProcessor(BaseStreamingProcessor):
    """
    Stateful streaming processor for OpenAI Responses API.

    Processes OpenAI Response events and converts them into standardized
    StreamingChunk objects. Maintains state to track tool calls across events.
    """

    def __init__(self):
        """Initialize streaming processor with state tracking."""
        # Track tool calls being built (indexed by item_id)
        self.tool_call_index: Dict[str, Dict[str, Any]] = {}

    def process_event(self, event: Any) -> List[StreamingChunk]:
        """
        Process OpenAI streaming event into standardized StreamingChunk objects.

        Args:
            event: OpenAI Response event

        Returns:
            List[StreamingChunk]: List of standardized chunks to yield
        """
        result = []

        # Extract usage metadata from event
        # Note: For Responses API, usage is in ResponseCompletedEvent.response.usage
        # For Chat Completions API (if used), usage might be in event.usage
        usage_info = {}
        if hasattr(event, 'usage') and event.usage:
            usage = event.usage
            # Support both Responses API (input_tokens/output_tokens) and Chat API (prompt_tokens/completion_tokens)
            usage_info = {
                'prompt_token_count': getattr(usage, 'input_tokens', None) or getattr(usage, 'prompt_tokens', None),
                'candidates_token_count': getattr(usage, 'output_tokens', None) or getattr(usage, 'completion_tokens', None),
                'total_token_count': getattr(usage, 'total_tokens', None),
            }

            # Extract detailed token counts if available (both API formats)
            if hasattr(usage, 'output_tokens_details'):
                details = usage.output_tokens_details
                if details:
                    usage_info['reasoning_tokens'] = getattr(details, 'reasoning_tokens', None)
            elif hasattr(usage, 'completion_tokens_details'):
                details = usage.completion_tokens_details
                if details:
                    usage_info['reasoning_tokens'] = getattr(details, 'reasoning_tokens', None)

            if hasattr(usage, 'input_tokens_details'):
                details = usage.input_tokens_details
                if details:
                    usage_info['cached_tokens'] = getattr(details, 'cached_tokens', None)
            elif hasattr(usage, 'prompt_tokens_details'):
                details = usage.prompt_tokens_details
                if details:
                    usage_info['cached_tokens'] = getattr(details, 'cached_tokens', None)

        # Thinking / reasoning summary events
        if isinstance(event, ResponseReasoningSummaryTextDeltaEvent):
            if hasattr(event, 'delta') and event.delta:
                result.append(StreamingChunk(
                    chunk_type="thinking",
                    content=event.delta,
                    metadata={
                        "item_id": getattr(event, 'item_id', None),
                        "summary_index": getattr(event, 'summary_index', None),
                        **usage_info
                    }
                ))

        elif isinstance(event, ResponseReasoningSummaryPartAddedEvent):
            if hasattr(event, 'part'):
                part_text = getattr(event.part, "text", "")
                if part_text:
                    result.append(StreamingChunk(
                        chunk_type="thinking",
                        content=part_text,
                        metadata={
                            "item_id": getattr(event, 'item_id', None),
                            "summary_index": getattr(event, 'summary_index', None),
                            **usage_info
                        }
                    ))

        elif isinstance(event, ResponseReasoningTextDeltaEvent):
            if hasattr(event, 'delta') and event.delta:
                result.append(StreamingChunk(
                    chunk_type="thinking",
                    content=str(event.delta),
                    metadata={"item_id": getattr(event, 'item_id', None), **usage_info}
                ))

        # Text deltas
        if isinstance(event, ResponseTextDeltaEvent):
            if hasattr(event, 'delta') and event.delta:
                result.append(StreamingChunk(
                    chunk_type="text",
                    content=event.delta,
                    metadata={
                        "item_id": getattr(event, 'item_id', None),
                        "content_index": getattr(event, 'content_index', None),
                        **usage_info
                    }
                ))

        # Function call lifecycle - item added
        if isinstance(event, ResponseOutputItemAddedEvent):
            if hasattr(event, 'item'):
                item = event.item
                if isinstance(item, ResponseFunctionToolCall):
                    call_id = item.call_id or item.id or item.name
                    info = {
                        "call_id": call_id,
                        "id": item.id or call_id,
                        "name": item.name
                    }
                    # Map both id and call_id for lookup
                    self.tool_call_index[call_id] = info
                    if item.id:
                        self.tool_call_index[item.id] = info

        # Function call arguments delta
        elif isinstance(event, ResponseFunctionCallArgumentsDeltaEvent):
            item_id = getattr(event, 'item_id', None)
            if item_id:
                info = self.tool_call_index.get(item_id, {})
                snapshot_text = getattr(event, "snapshot", "")

                if snapshot_text:
                    try:
                        args_snapshot = json.loads(snapshot_text)
                    except Exception:
                        args_snapshot = {}
                else:
                    args_snapshot = {}

                result.append(StreamingChunk(
                    chunk_type="function_call",
                    content=info.get("name", ""),
                    metadata={
                        "tool_id": info.get("call_id"),
                        "delta": getattr(event, 'delta', None),
                        **usage_info
                    },
                    function_call={
                        "id": info.get("call_id"),
                        "name": info.get("name"),
                        "args": args_snapshot
                    }
                ))

        # Function call arguments done
        elif isinstance(event, ResponseFunctionCallArgumentsDoneEvent):
            item_id = getattr(event, 'item_id', None)
            if item_id:
                info = self.tool_call_index.get(item_id, {})
                arguments_text = getattr(event, 'arguments', None) or ""

                if arguments_text:
                    try:
                        parsed_args = json.loads(arguments_text)
                    except Exception:
                        parsed_args = arguments_text
                else:
                    parsed_args = getattr(event, 'arguments', None)

                result.append(StreamingChunk(
                    chunk_type="function_call",
                    content=info.get("name", ""),
                    metadata={
                        "tool_id": info.get("call_id"),
                        "is_final": True,
                        **usage_info
                    },
                    function_call={
                        "id": info.get("call_id"),
                        "name": info.get("name"),
                        "args": parsed_args
                    }
                ))

        # ResponseCompletedEvent - capture final response metadata and usage
        if hasattr(event, 'response') and event.response:
            response = event.response
            if hasattr(response, 'usage') and response.usage:
                usage = response.usage
                usage_info = {
                    'prompt_token_count': getattr(usage, 'input_tokens', None),
                    'candidates_token_count': getattr(usage, 'output_tokens', None),
                    'total_token_count': getattr(usage, 'total_tokens', None),
                }

        # If we extracted usage but didn't produce any chunks, create a metadata-only chunk
        # This ensures usage information from the final chunk is not lost
        if usage_info and not result:
            result.append(StreamingChunk(
                chunk_type="text",
                content="",  # Empty content, only metadata
                metadata=usage_info
            ))

        return result


class OpenAIResponseProcessor(BaseResponseProcessor):
    """
    Process OpenAI API responses and extract relevant information.
    """

    @staticmethod
    def extract_text_content(response) -> str:
        """
        Extract text content from OpenAI Responses API result.

        Args:
            response: OpenAI Responses API response object

        Returns:
            Extracted text content as a single string.
        """
        if not isinstance(response, Response) or not response.output:
            return ""

        text_segments: List[str] = []

        for item in response.output:
            if isinstance(item, ResponseOutputMessage):
                for part in item.content:
                    if isinstance(part, ResponseOutputText):
                        text_segments.append(part.text)

        return "".join(text_segments)

    @staticmethod
    def has_tool_calls(response) -> bool:
        """
        Check if response contains tool calls.
        """
        if not isinstance(response, Response) or not response.output:
            return False

        return any(isinstance(item, ResponseFunctionToolCall) for item in response.output)

    @staticmethod
    def extract_tool_calls(response) -> List[Dict[str, Any]]:
        """
        Extract tool calls from OpenAI Responses API result.
        """
        if not isinstance(response, Response) or not response.output:
            return []

        tool_calls: List[Dict[str, Any]] = []

        for item in response.output:
            if not isinstance(item, ResponseFunctionToolCall):
                continue

            try:
                arguments = item.arguments
                if isinstance(arguments, str):
                    try:
                        parsed_args = json.loads(arguments)
                    except json.JSONDecodeError:
                        parsed_args = arguments
                else:
                    parsed_args = arguments

                import uuid

                tool_call_id = item.call_id or item.id or str(uuid.uuid4())
                tool_calls.append({
                    "name": item.name,
                    "arguments": parsed_args,
                    "id": tool_call_id
                })
            except Exception as exc:
                print(f"[WARNING] Failed to parse tool call: {exc}")
                continue

        return tool_calls

    @staticmethod
    def format_response_for_storage(
        response,
        tool_calls: Optional[List[Dict[str, Any]]] = None
    ) -> AssistantMessage:
        """
        Format OpenAI Responses API output for storage in message history.
        """
        if not isinstance(response, Response):
            return AssistantMessage(role="assistant", content=[{"type": "text", "text": ""}])

        content_blocks: List[Dict[str, Any]] = []

        # Extract reasoning and text content in a single pass (optimization)
        # This avoids redundant iteration over response.output
        if response.output:
            text_segments: List[str] = []

            for item in response.output:
                # Extract reasoning content
                if isinstance(item, ResponseReasoningItem):
                    # Extract all summary text parts
                    reasoning_texts = []
                    for summary in item.summary:
                        summary_text = getattr(summary, "text", "")
                        if summary_text:
                            reasoning_texts.append(summary_text)

                    # Combine all reasoning text into single thinking block
                    if reasoning_texts:
                        content_blocks.append({
                            "type": "thinking",
                            "thinking": "\n".join(reasoning_texts)
                        })

                # Extract text content
                elif isinstance(item, ResponseOutputMessage):
                    for part in item.content:
                        if isinstance(part, ResponseOutputText):
                            text_segments.append(part.text)

            # Add combined text content if any
            if text_segments:
                combined_text = "".join(text_segments)
                if combined_text:
                    content_blocks.append({"type": "text", "text": combined_text})

        # Reuse pre-extracted tool calls if provided, otherwise extract now
        if tool_calls is None:
            tool_calls = OpenAIResponseProcessor.extract_tool_calls(response)

        # Add tool_use blocks to content array (following Gemini/Anthropic/Kimi pattern)
        # This ensures frontend can render tool calls correctly
        if tool_calls:
            for tool_call in tool_calls:
                content_blocks.append({
                    "type": "tool_use",
                    "id": tool_call['id'],
                    "name": tool_call['name'],
                    "input": tool_call['arguments']
                })

        message = AssistantMessage(
            role="assistant",
            content=content_blocks if content_blocks else [{"type": "text", "text": ""}]
        )

        # Note: tool_calls are already represented as tool_use blocks in content array
        # No need to set message.tool_calls attribute (which doesn't exist in the model)

        return message

    @staticmethod
    def format_response_for_context(response) -> List[Dict[str, Any]]:
        """
        Format OpenAI Responses API output for working context.

        Processes response.output items and converts them to Responses API input format
        for use in subsequent API calls.

        This method centralizes the formatting logic previously in
        context_manager.add_response() for better separation of concerns.

        Args:
            response: OpenAI API Response object

        Returns:
            List of context items ready to append to working_contents.
            Returns empty list if response is invalid.

            Note: Unlike other providers, OpenAI returns a LIST because one response
            can produce multiple context items (message, reasoning, function_call).
        """
        if not isinstance(response, Response):
            return []

        if not response.output:
            return []

        context_items: List[Dict[str, Any]] = []

        # Process each output item and convert to input format
        for item in response.output:
            # Convert Pydantic model to dict
            item_dict = item.model_dump(mode='json', exclude_none=False)
            item_type = item_dict.get("type")

            # Handle message items (assistant responses)
            if item_type == "message":
                role = item_dict.get("role")
                if not role:
                    continue

                content = item_dict.get("content", [])

                # Extract text content from response.output format
                if isinstance(content, list):
                    if not content:
                        content_value = ""
                    else:
                        # Extract only text content (skip reasoning)
                        text_parts = []
                        for block in content:
                            if isinstance(block, dict) and block.get("type") == "output_text":
                                text_parts.append(block.get("text", ""))
                            elif isinstance(block, str):
                                text_parts.append(block)
                        content_value = "".join(text_parts)
                elif isinstance(content, str):
                    content_value = content
                else:
                    content_value = str(content) if content else ""

                context_items.append({
                    "role": role,
                    "content": content_value
                })

            # Handle reasoning items
            # Note: Current request's reasoning MUST be kept for pairing with function_call
            # Historical reasoning (from DB) is NOT loaded (format_single_message skips thinking)
            # This dual approach works because API only requires pairing in current request
            elif item_type == "reasoning":
                summary = item_dict.get("summary", [])
                reasoning_id = item_dict.get("id")

                # Keep reasoning item if it has an ID (required for pairing with function_call)
                # Note: Empty summary ([]) should still be kept to maintain pairing
                if reasoning_id:
                    # Keep type, id, and summary for input
                    context_items.append({
                        "type": "reasoning",
                        "id": reasoning_id,
                        "summary": summary if summary else []
                    })

            # Handle function_call items
            elif item_type == "function_call":
                # Ensure arguments field exists
                if 'arguments' not in item_dict or item_dict['arguments'] is None:
                    item_dict['arguments'] = "{}"

                # Convert arguments to string if needed
                arguments = item_dict.get("arguments")
                if isinstance(arguments, dict):
                    try:
                        arguments = json.dumps(arguments)
                    except (TypeError, ValueError):
                        arguments = "{}"
                elif arguments is None:
                    arguments = "{}"
                else:
                    arguments = str(arguments)

                # Use correct IDs for input format:
                # - id: fc_xxx (required for input[].id field)
                # - call_id: call_xxx (used to match with function_call_output)
                context_items.append({
                    "type": "function_call",
                    "id": item_dict.get("id"),           # fc_xxx - required by API
                    "call_id": item_dict.get("call_id"), # call_xxx - for matching results
                    "name": item_dict.get("name"),
                    "arguments": arguments
                })

            # Note: function_call_output branch intentionally removed
            # - OpenAI API does not return function_call_output in response.output
            # - Tool results are added via add_tool_result() → format_tool_result_for_context()
            # - This prevents duplication and aligns with other providers' architecture

        return context_items

    @staticmethod
    def extract_web_search_sources(response, debug: bool = False) -> List[Dict[str, Any]]:
        """
        Extract web search sources from OpenAI response.

        Note: OpenAI doesn't have built-in web search like Gemini. Placeholder for MCP-based sources.
        """
        return []

    @staticmethod
    def construct_response_from_chunks(chunks: List['StreamingChunk']) -> Response:
        """
        Convert collected streaming chunks back into a complete Response object.

        Args:
            chunks: List of StreamingChunk objects collected during streaming

        Returns:
            Response: Complete OpenAI Response object

        Note:
            This method prefers the response captured during streaming if available,
            otherwise reconstructs from streamed text/thinking content.
        """
        import time
        from backend.domain.models.streaming import StreamingChunk

        # Prefer the response captured during streaming if available
        for chunk in reversed(chunks):
            metadata = chunk.metadata or {}
            final_response = metadata.get("__openai_final_response")
            if isinstance(final_response, Response):
                return final_response

        # Fallback reconstruction from streamed text/thinking
        text_output = "".join(
            chunk.content for chunk in chunks if chunk.chunk_type == "text"
        )
        reasoning_output = "".join(
            chunk.content for chunk in chunks if chunk.chunk_type == "thinking"
        )

        output_items: List[Any] = []

        if reasoning_output:
            output_items.append(
                ResponseReasoningItem.model_construct(
                    id="reasoning_stream",
                    type="reasoning",
                    summary=[{"type": "summary_text", "text": reasoning_output}],
                    status="completed",
                    encrypted_content=None
                )
            )

        if text_output:
            output_items.append(
                ResponseOutputMessage.model_construct(
                    id="msg_stream",
                    role="assistant",
                    status="completed",
                    type="message",
                    content=[
                        ResponseOutputText.model_construct(
                            type="output_text",
                            text=text_output,
                            annotations=[]
                        )
                    ]
                )
            )

        # Get model name from config
        from backend.config.llm import get_llm_settings
        model_name = get_llm_settings().get_openai_config().model

        return Response.model_construct(
            id="resp_stream",
            object="response",
            created_at=int(time.time()),
            status="completed",
            model=model_name,
            output=output_items,
            reasoning=None,
            instructions=None,
            metadata={},
            parallel_tool_calls=True,
            tools=[],
            temperature=1.0,
            top_p=1.0,
            text=None,
            usage=None,
            tool_choice=None,
            max_output_tokens=None,
            previous_response_id=None,
            prompt=None,
            service_tier=None,
            truncation="disabled",
            background=None,
            user=None,
            error=None,
            incomplete_details=None
        )

    @staticmethod
    def create_streaming_processor() -> BaseStreamingProcessor:
        """
        Create OpenAI streaming processor instance.

        Returns:
            OpenAIStreamingProcessor: Stateful processor for OpenAI streaming
        """
        return OpenAIStreamingProcessor()
