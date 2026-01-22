"""
OpenRouter Response Processor

Handles processing of OpenRouter API responses using OpenAI Chat Completions API format.

OpenRouter uses the traditional Chat Completions API which returns ChatCompletion objects.
"""

import json
from typing import List, Dict, Any, Optional
from openai.types.chat import ChatCompletion, ChatCompletionMessage, ChatCompletionChunk
from backend.domain.models.messages import AssistantMessage
from backend.domain.models.streaming import StreamingChunk
from backend.infrastructure.llm.base.response_processor import BaseResponseProcessor, BaseStreamingProcessor
from .debug import OpenRouterDebugger
from backend.config.dev import get_dev_config


class OpenRouterStreamingProcessor(BaseStreamingProcessor):
    """
    Stateful streaming processor for OpenRouter API.

    Processes OpenRouter ChatCompletionChunk events and converts them into
    standardized StreamingChunk objects. Maintains state to track tool calls
    and reasoning content across chunks.

    OpenRouter supports reasoning tokens via delta.reasoning_details array.
    """

    def __init__(self):
        """Initialize streaming processor with state tracking."""
        # Track tool calls being built (indexed by index)
        self.current_tool_calls: Dict[int, Dict[str, Any]] = {}
        # Track reasoning content being built (thinking models)
        self.reasoning_buffer: str = ""

    def process_event(self, event: Any) -> List[StreamingChunk]:
        """
        Process OpenRouter streaming chunk into standardized StreamingChunk objects.

        Args:
            event: OpenRouter ChatCompletionChunk

        Returns:
            List[StreamingChunk]: List of standardized chunks to yield
        """
        result = []

        # Validate chunk structure
        if not isinstance(event, ChatCompletionChunk):
            return result

        # Handle final usage-only chunk (has no choices but has chunk.usage)
        if not hasattr(event, 'choices') or not event.choices:
            if hasattr(event, 'usage') and event.usage:
                usage = event.usage
                usage_metadata = {
                    'prompt_token_count': getattr(usage, 'prompt_tokens', None),
                    'candidates_token_count': getattr(usage, 'completion_tokens', None),
                    'total_token_count': getattr(usage, 'total_tokens', None),
                }
                # Extract cached tokens if available
                if hasattr(usage, 'prompt_tokens_details') and usage.prompt_tokens_details:
                    cached = getattr(usage.prompt_tokens_details, 'cached_tokens', None)
                    if cached:
                        usage_metadata['cached_tokens'] = cached

                # Extract completion_tokens_details if available (for reasoning models)
                if hasattr(usage, 'completion_tokens_details') and usage.completion_tokens_details:
                    reasoning = getattr(usage.completion_tokens_details, 'reasoning_tokens', None)
                    if reasoning:
                        usage_metadata['reasoning_tokens'] = reasoning

                # OpenRouter-specific: Extract cost information
                if hasattr(usage, 'cost'):
                    usage_metadata['cost'] = getattr(usage, 'cost', None)
                if hasattr(usage, 'cost_details'):
                    usage_metadata['cost_details'] = getattr(usage, 'cost_details', None)

                # Create metadata-only chunk with usage
                result.append(StreamingChunk(
                    chunk_type="text",
                    content="",
                    metadata=usage_metadata
                ))
            return result

        choice = event.choices[0]
        if not hasattr(choice, 'delta'):
            return result

        delta = choice.delta

        # Handle reasoning content (OpenRouter thinking models)
        # OpenRouter sends reasoning via delta.reasoning_details array
        reasoning_details = getattr(delta, 'reasoning_details', None)
        if reasoning_details and isinstance(reasoning_details, list):
            for detail in reasoning_details:
                # detail is dict-like with type, text/summary fields
                if isinstance(detail, dict):
                    detail_type = detail.get('type', '')

                    # Handle reasoning.text deltas
                    if detail_type == 'reasoning.text':
                        text = detail.get('text', '')
                        if text:
                            self.reasoning_buffer += text
                            result.append(StreamingChunk(
                                chunk_type="thinking",
                                content=text,
                                metadata={
                                    "index": getattr(choice, 'index', 0),
                                    "is_reasoning": True,
                                    "detail_id": detail.get('id'),
                                    "format": detail.get('format')
                                }
                            ))

                    # Handle reasoning.summary deltas
                    elif detail_type == 'reasoning.summary':
                        summary = detail.get('summary', '')
                        if summary:
                            self.reasoning_buffer += summary
                            result.append(StreamingChunk(
                                chunk_type="thinking",
                                content=summary,
                                metadata={
                                    "index": getattr(choice, 'index', 0),
                                    "is_reasoning": True,
                                    "detail_id": detail.get('id'),
                                    "format": detail.get('format')
                                }
                            ))
                # Handle object format (getattr-based access)
                else:
                    detail_type = getattr(detail, 'type', '')

                    if detail_type == 'reasoning.text':
                        text = getattr(detail, 'text', '')
                        if text:
                            self.reasoning_buffer += text
                            result.append(StreamingChunk(
                                chunk_type="thinking",
                                content=text,
                                metadata={
                                    "index": getattr(choice, 'index', 0),
                                    "is_reasoning": True
                                }
                            ))
                    elif detail_type == 'reasoning.summary':
                        summary = getattr(detail, 'summary', '')
                        if summary:
                            self.reasoning_buffer += summary
                            result.append(StreamingChunk(
                                chunk_type="thinking",
                                content=summary,
                                metadata={
                                    "index": getattr(choice, 'index', 0),
                                    "is_reasoning": True
                                }
                            ))

        # Handle text content
        if hasattr(delta, 'content') and delta.content:
            result.append(StreamingChunk(
                chunk_type="text",
                content=delta.content,
                metadata={"index": getattr(choice, 'index', 0)}
            ))

        # Handle tool calls
        if hasattr(delta, 'tool_calls') and delta.tool_calls:
            for tool_call_delta in delta.tool_calls:
                idx = tool_call_delta.index

                # Initialize tool call if not exists
                if idx not in self.current_tool_calls:
                    self.current_tool_calls[idx] = {
                        "id": tool_call_delta.id or "",
                        "type": getattr(tool_call_delta, 'type', "function"),
                        "function": {
                            "name": "",
                            "arguments": ""
                        }
                    }

                # Update tool call data
                if hasattr(tool_call_delta, 'id') and tool_call_delta.id:
                    self.current_tool_calls[idx]["id"] = tool_call_delta.id

                if hasattr(tool_call_delta, 'function') and tool_call_delta.function:
                    if hasattr(tool_call_delta.function, 'name') and tool_call_delta.function.name:
                        self.current_tool_calls[idx]["function"]["name"] = tool_call_delta.function.name
                    if hasattr(tool_call_delta.function, 'arguments') and tool_call_delta.function.arguments:
                        self.current_tool_calls[idx]["function"]["arguments"] += tool_call_delta.function.arguments

        # Check if tool call is complete
        finish_reason = getattr(choice, 'finish_reason', None)
        if finish_reason == "tool_calls" and self.current_tool_calls:
            for tool_call in self.current_tool_calls.values():
                # Parse arguments string to dict
                arguments_str = tool_call["function"]["arguments"]
                try:
                    arguments_dict = json.loads(arguments_str) if arguments_str else {}
                except json.JSONDecodeError:
                    arguments_dict = {}

                result.append(StreamingChunk(
                    chunk_type="function_call",
                    content=tool_call["function"]["name"],
                    metadata={
                        "tool_call_id": tool_call["id"],
                        "args": arguments_dict
                    },
                    function_call={
                        "name": tool_call["function"]["name"],
                        "args": arguments_dict
                    }
                ))
            # Clear tool calls after emitting
            self.current_tool_calls.clear()

        # Extract usage metadata from chunk-level usage (OpenRouter includes this)
        # This appears in the final chunk even when choices are present
        usage_metadata = {}
        if hasattr(event, 'usage') and event.usage:
            usage = event.usage
            usage_metadata = {
                'prompt_token_count': getattr(usage, 'prompt_tokens', None),
                'candidates_token_count': getattr(usage, 'completion_tokens', None),
                'total_token_count': getattr(usage, 'total_tokens', None),
            }
            # Extract cached tokens if available
            if hasattr(usage, 'prompt_tokens_details') and usage.prompt_tokens_details:
                cached = getattr(usage.prompt_tokens_details, 'cached_tokens', None)
                if cached:
                    usage_metadata['cached_tokens'] = cached

            # Extract completion_tokens_details if available (for reasoning models)
            if hasattr(usage, 'completion_tokens_details') and usage.completion_tokens_details:
                reasoning = getattr(usage.completion_tokens_details, 'reasoning_tokens', None)
                if reasoning:
                    usage_metadata['reasoning_tokens'] = reasoning

            # OpenRouter-specific: Extract cost information
            if hasattr(usage, 'cost'):
                usage_metadata['cost'] = getattr(usage, 'cost', None)
            if hasattr(usage, 'cost_details'):
                usage_metadata['cost_details'] = getattr(usage, 'cost_details', None)

        # If we have usage metadata but didn't produce any chunks, create a metadata-only chunk
        if usage_metadata and not result:
            result.append(StreamingChunk(
                chunk_type="text",
                content="",
                metadata=usage_metadata
            ))
        # If we have chunks and usage metadata, merge usage into the last chunk
        elif usage_metadata and result:
            result[-1].metadata.update(usage_metadata)

        return result


class OpenRouterResponseProcessor(BaseResponseProcessor):
    """
    Process OpenRouter API responses using Chat Completions format.

    OpenRouter uses OpenAI-compatible Chat Completions API,
    so the response structure is ChatCompletion.
    """

    @staticmethod
    def extract_text_content(response) -> str:
        """
        Extract text content from OpenRouter ChatCompletion response.

        Args:
            response: ChatCompletion object from OpenRouter API

        Returns:
            Extracted text content as a single string.
        """
        if not isinstance(response, ChatCompletion):
            return ""

        if not response.choices:
            return ""

        message = response.choices[0].message
        return message.content or ""

    @staticmethod
    def extract_reasoning_content(response) -> Optional[str]:
        """
        Extract reasoning content from OpenRouter ChatCompletion response.

        OpenRouter supports reasoning tokens for thinking models (DeepSeek R1, o1, etc.).
        Reasoning appears in two forms:
        - message.reasoning: Simple string field with reasoning text
        - message.reasoning_details: Array of structured reasoning objects

        Args:
            response: ChatCompletion object from OpenRouter API

        Returns:
            Extracted reasoning content as a string, or None if not available.
        """
        if not isinstance(response, ChatCompletion):
            return None

        if not response.choices:
            return None

        message = response.choices[0].message

        # Try simple reasoning field first
        reasoning = getattr(message, 'reasoning', None)
        if reasoning:
            return reasoning

        # Try reasoning_details array (structured format)
        reasoning_details = getattr(message, 'reasoning_details', None)
        if reasoning_details and isinstance(reasoning_details, list):
            # Extract text from reasoning_details array
            reasoning_texts = []
            for detail in reasoning_details:
                if isinstance(detail, dict):
                    # Handle different reasoning detail types
                    detail_type = detail.get('type', '')
                    if detail_type == 'reasoning.text':
                        text = detail.get('text', '')
                        if text:
                            reasoning_texts.append(text)
                    elif detail_type == 'reasoning.summary':
                        summary = detail.get('summary', '')
                        if summary:
                            reasoning_texts.append(summary)
                    # Note: reasoning.encrypted is intentionally skipped

            if reasoning_texts:
                return '\n'.join(reasoning_texts)

        return None

    @staticmethod
    def has_tool_calls(response) -> bool:
        """
        Check if response contains tool calls.
        """
        if not isinstance(response, ChatCompletion):
            return False

        if not response.choices:
            return False

        message = response.choices[0].message
        return bool(message.tool_calls)

    @staticmethod
    def extract_tool_calls(response) -> List[Dict[str, Any]]:
        """
        Extract tool calls from OpenRouter ChatCompletion response.

        Args:
            response: ChatCompletion object from OpenRouter API

        Returns:
            List of tool call dictionaries with name, arguments, and id.
        """
        if not isinstance(response, ChatCompletion):
            return []

        if not response.choices:
            return []

        message = response.choices[0].message
        if not message.tool_calls:
            return []

        # Debug: Print raw tool calls from API
        if get_dev_config().debug_mode:
            raw_tool_calls = []
            for tc in message.tool_calls:
                function = getattr(tc, 'function', None)
                if function:
                    raw_tool_calls.append({
                        'id': tc.id,
                        'function': {
                            'name': getattr(function, 'name', ''),
                            'arguments': getattr(function, 'arguments', '')
                        }
                    })
            OpenRouterDebugger.print_tool_call_received(raw_tool_calls)

        tool_calls: List[Dict[str, Any]] = []

        for tool_call in message.tool_calls:
            try:
                # ChatCompletion tool_calls have: id, type, function
                # function has: name, arguments (as string)
                function = getattr(tool_call, 'function', None)
                if not function:
                    continue

                arguments = getattr(function, 'arguments', '')
                function_name = getattr(function, 'name', '')

                # Parse arguments string to dict if needed
                if isinstance(arguments, str):
                    try:
                        # Handle empty string or whitespace-only string
                        if not arguments or not arguments.strip():
                            parsed_args = {}
                        else:
                            parsed_args = json.loads(arguments)
                    except json.JSONDecodeError:
                        # If parsing fails, return empty dict (not the string!)
                        print(f"[WARNING] Failed to parse arguments as JSON: {arguments}")
                        parsed_args = {}
                else:
                    parsed_args = arguments if arguments else {}

                tool_calls.append({
                    "name": function_name,
                    "arguments": parsed_args,
                    "id": tool_call.id
                })
            except Exception as exc:
                print(f"[WARNING] Failed to parse tool call: {exc}")
                continue

        # Debug: Print extracted tool calls
        if get_dev_config().debug_mode:
            OpenRouterDebugger.print_extracted_tool_calls(tool_calls)

        return tool_calls

    @staticmethod
    def format_response_for_storage(
        response,
        tool_calls: Optional[List[Dict[str, Any]]] = None
    ) -> AssistantMessage:
        """
        Format OpenRouter ChatCompletion response for storage in message history.

        This method creates standardized message objects optimized for:
        - Database storage efficiency
        - Frontend rendering consistency
        - Cross-LLM compatibility (following Gemini/Anthropic pattern)
        - Reasoning token support for thinking models

        Args:
            response: ChatCompletion object from OpenRouter API
            tool_calls: Pre-extracted tool calls (optional). If provided, reuses these
                       instead of re-extracting to ensure consistent IDs.

        Returns:
            AssistantMessage formatted for storage with tool_use blocks in content array.
        """
        if not isinstance(response, ChatCompletion):
            return AssistantMessage(role="assistant", content=[{"type": "text", "text": ""}])

        content_blocks: List[Dict[str, Any]] = []

        # Extract reasoning content first (thinking models)
        reasoning_content = OpenRouterResponseProcessor.extract_reasoning_content(response)
        if reasoning_content:
            content_blocks.append({"type": "thinking", "thinking": reasoning_content})

        # Extract text content
        text_content = OpenRouterResponseProcessor.extract_text_content(response)
        if text_content:
            content_blocks.append({"type": "text", "text": text_content})

        # Reuse pre-extracted tool calls if provided, otherwise extract now
        if tool_calls is None:
            tool_calls = OpenRouterResponseProcessor.extract_tool_calls(response)

        # Add tool_use blocks to content array (following Gemini/Anthropic pattern)
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

        return message

    @staticmethod
    def format_response_for_context(response) -> Optional[Dict[str, Any]]:
        """
        Format OpenRouter ChatCompletion response for working context.

        Extracts data from API response and builds message dict in Chat Completions
        format for use in subsequent API calls.

        This method centralizes the formatting logic previously in
        context_manager.add_response() for better separation of concerns.

        Args:
            response: ChatCompletion object from OpenRouter API

        Returns:
            Message dict ready to append to working_contents, or None if invalid.

            Message dict structure:
                {
                    "role": "assistant",
                    "content": "...",
                    "reasoning": "..." (optional - thinking models),
                    "tool_calls": [...] (optional)
                }

            Note: The reasoning field preserves OpenRouter's thinking content
            for proper context handling in subsequent API calls.
        """
        if not isinstance(response, ChatCompletion):
            return None

        if not response.choices:
            return None

        choice = response.choices[0]
        message = choice.message

        # Build message dict in Chat Completions format
        message_dict: Dict[str, Any] = {
            "role": message.role,
            "content": message.content
        }

        # Add reasoning field if present (OpenRouter thinking models)
        # This preserves the reasoning field for subsequent API calls
        reasoning = getattr(message, 'reasoning', None)
        if reasoning:
            message_dict["reasoning"] = reasoning

        # Add tool calls if present
        if message.tool_calls:
            # Convert tool calls to dict format
            tool_calls_list = []
            for tool_call in message.tool_calls:
                # tool_call is ChatCompletionMessageToolCall with id, type, function
                function_info = getattr(tool_call, 'function', None)
                if function_info:
                    tool_calls_list.append({
                        "id": tool_call.id,
                        "type": tool_call.type,
                        "function": {
                            "name": getattr(function_info, 'name', ''),
                            "arguments": getattr(function_info, 'arguments', '')
                        }
                    })
            message_dict["tool_calls"] = tool_calls_list

        return message_dict

    @staticmethod
    def construct_response_from_chunks(chunks: List['StreamingChunk']) -> ChatCompletion:
        """
        Convert collected streaming chunks back into a complete ChatCompletion object.

        Args:
            chunks: List of StreamingChunk objects collected during streaming

        Returns:
            ChatCompletion object reconstructed from chunks

        Note:
            This reconstruction preserves all essential fields including:
            - Reasoning content (thinking models)
            - Text content
            - Tool calls with IDs and arguments
            - All metadata needed for tool calling logic
        """
        import json
        import time
        from openai.types.chat import ChatCompletion, ChatCompletionMessage
        from openai.types.chat.chat_completion import Choice
        from openai.types.completion_usage import CompletionUsage
        from backend.domain.models.streaming import StreamingChunk

        # Check if we have a final response stored in metadata
        for chunk in reversed(chunks):
            metadata = chunk.metadata or {}
            final_response = metadata.get("__openrouter_final_response")
            if final_response:
                return final_response

        # If no final response found, construct from chunks
        # Collect reasoning, text content, and tool calls
        reasoning_content = ""
        text_content = ""
        tool_calls = []

        for chunk in chunks:
            if chunk.chunk_type == "thinking" and chunk.content:
                # Accumulate reasoning content (thinking models)
                reasoning_content += chunk.content
            elif chunk.chunk_type == "text" and chunk.content:
                text_content += chunk.content
            elif chunk.chunk_type == "function_call" and chunk.function_call:
                # Get tool_call_id from metadata if available
                tool_call_id = chunk.metadata.get("tool_call_id", "") if chunk.metadata else ""

                # Convert args dict to JSON string for ChatCompletion format
                args_dict = chunk.function_call.get("args", {})
                arguments_str = json.dumps(args_dict) if args_dict else ""

                tool_calls.append({
                    "id": tool_call_id,
                    "type": "function",
                    "function": {
                        "name": chunk.function_call.get("name", ""),
                        "arguments": arguments_str
                    }
                })

        # Construct a ChatCompletion object
        message = ChatCompletionMessage(
            role="assistant",
            content=text_content if text_content else None,
            tool_calls=tool_calls if tool_calls else None
        )

        # Add reasoning content to message object (thinking models)
        # This is a dynamic attribute that will be extracted by response processor
        if reasoning_content:
            setattr(message, 'reasoning', reasoning_content)

        choice = Choice(
            index=0,
            message=message,
            finish_reason="stop" if not tool_calls else "tool_calls"
        )

        # Get model name from config
        from .config import OpenRouterConfig
        model_name = OpenRouterConfig().model

        return ChatCompletion(
            id="constructed_from_chunks",
            model=model_name,
            created=int(time.time()),
            object="chat.completion",
            choices=[choice],
            usage=CompletionUsage(
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0
            )
        )

    @staticmethod
    def create_streaming_processor() -> BaseStreamingProcessor:
        """
        Create OpenRouter streaming processor instance.

        Returns:
            OpenRouterStreamingProcessor: Stateful processor for OpenRouter streaming
        """
        return OpenRouterStreamingProcessor()


__all__ = ['OpenRouterResponseProcessor']
