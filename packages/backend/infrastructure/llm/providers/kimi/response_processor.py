"""
Kimi (Moonshot) Response Processor

Handles processing of Kimi API responses using OpenAI Chat Completions API format.

Unlike OpenAI's Responses API, Kimi uses the traditional Chat Completions API
which returns ChatCompletion objects instead of Response objects.
"""

import json
from typing import List, Dict, Any, Optional
from openai.types.chat import ChatCompletion, ChatCompletionMessage, ChatCompletionChunk
from backend.domain.models.messages import AssistantMessage
from backend.domain.models.streaming import StreamingChunk
from backend.infrastructure.llm.base.response_processor import BaseResponseProcessor, BaseStreamingProcessor
from .debug import KimiDebugger


class KimiStreamingProcessor(BaseStreamingProcessor):
    """
    Stateful streaming processor for Kimi API.

    Processes Kimi ChatCompletionChunk events and converts them into
    standardized StreamingChunk objects. Maintains state to track tool calls
    and reasoning content across chunks.
    """

    def __init__(self):
        """Initialize streaming processor with state tracking."""
        # Track tool calls being built (indexed by index)
        self.current_tool_calls: Dict[int, Dict[str, Any]] = {}
        # Track reasoning content being built (K2 Thinking models)
        self.reasoning_buffer: str = ""

    def process_event(self, event: Any) -> List[StreamingChunk]:
        """
        Process Kimi streaming chunk into standardized StreamingChunk objects.

        Args:
            event: Kimi ChatCompletionChunk

        Returns:
            List[StreamingChunk]: List of standardized chunks to yield
        """
        result = []

        # Validate chunk structure
        if not isinstance(event, ChatCompletionChunk):
            return result

        # Handle final usage-only chunk (has no choices but has chunk.usage)
        if not event.choices:
            if hasattr(event, 'usage') and event.usage:
                usage = event.usage
                usage_metadata = {
                    'prompt_token_count': getattr(usage, 'prompt_tokens', None),
                    'candidates_token_count': getattr(usage, 'completion_tokens', None),
                    'total_token_count': getattr(usage, 'total_tokens', None),
                }
                # Extract cached tokens if available
                if hasattr(usage, 'cached_tokens') and usage.cached_tokens:
                    usage_metadata['cached_tokens'] = usage.cached_tokens
                # Extract completion_tokens_details if available (for K2 Thinking models)
                if hasattr(usage, 'completion_tokens_details') and usage.completion_tokens_details:
                    usage_metadata['reasoning_tokens'] = getattr(usage.completion_tokens_details, 'reasoning_tokens', None)

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

        # Also check for usage in choice.usage (appears in finish_reason chunk)
        # Note: Kimi may include usage in choice, though not in OpenAI's type definition
        usage_metadata = {}
        usage = getattr(choice, 'usage', None)
        if usage:
            # Usage may be dict or CompletionUsage object depending on API version
            def get_usage_field(field: str) -> Any:
                if isinstance(usage, dict):
                    return usage.get(field)
                return getattr(usage, field, None)

            usage_metadata = {
                'prompt_token_count': get_usage_field('prompt_tokens'),
                'candidates_token_count': get_usage_field('completion_tokens'),
                'total_token_count': get_usage_field('total_tokens'),
            }
            # Extract cached tokens (Kimi-specific field)
            cached = get_usage_field('cached_tokens')
            if cached:
                usage_metadata['cached_tokens'] = cached

        # Handle reasoning content (K2 Thinking models)
        reasoning_delta = getattr(delta, 'reasoning_content', None)
        if reasoning_delta:
            self.reasoning_buffer += reasoning_delta
            result.append(StreamingChunk(
                chunk_type="thinking",
                content=reasoning_delta,
                metadata={
                    "index": getattr(choice, 'index', 0),
                    "is_reasoning": True,
                    **usage_metadata
                }
            ))

        # Handle text content
        if hasattr(delta, 'content') and delta.content:
            result.append(StreamingChunk(
                chunk_type="text",
                content=delta.content,
                metadata={"index": getattr(choice, 'index', 0), **usage_metadata}
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

        return result


class KimiResponseProcessor(BaseResponseProcessor):
    """
    Process Kimi API responses using Chat Completions format.

    Kimi uses OpenAI-compatible Chat Completions API (not Responses API),
    so the response structure is ChatCompletion, not Response.
    """

    @staticmethod
    def extract_text_content(response) -> str:
        """
        Extract text content from Kimi ChatCompletion response.

        Args:
            response: ChatCompletion object from Kimi API

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
        Extract reasoning content from Kimi K2 Thinking ChatCompletion response.

        K2 Thinking models expose an auxiliary field `reasoning_content` that contains
        the model's intermediate reasoning/thinking process before the final answer.

        Args:
            response: ChatCompletion object from Kimi API

        Returns:
            Extracted reasoning content as a string, or None if not available.
        """
        if not isinstance(response, ChatCompletion):
            return None

        if not response.choices:
            return None

        message = response.choices[0].message

        # Access reasoning_content attribute if it exists (K2 Thinking models)
        reasoning_content = getattr(message, 'reasoning_content', None)

        return reasoning_content if reasoning_content else None

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
        Extract tool calls from Kimi ChatCompletion response.

        Args:
            response: ChatCompletion object from Kimi API

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
        from backend.config.llm import get_llm_settings
        if get_llm_settings().debug:
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
            KimiDebugger.print_tool_call_received(raw_tool_calls)

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
        from backend.config.llm import get_llm_settings
        if get_llm_settings().debug:
            KimiDebugger.print_extracted_tool_calls(tool_calls)

        return tool_calls

    @staticmethod
    def format_response_for_storage(
        response,
        tool_calls: Optional[List[Dict[str, Any]]] = None
    ) -> AssistantMessage:
        """
        Format Kimi ChatCompletion response for storage in message history.

        This method creates standardized message objects optimized for:
        - Database storage efficiency
        - Frontend rendering consistency
        - Cross-LLM compatibility (following Gemini/Anthropic pattern)
        - K2 Thinking model reasoning content support

        Args:
            response: ChatCompletion object from Kimi API
            tool_calls: Pre-extracted tool calls (optional). If provided, reuses these
                       instead of re-extracting to ensure consistent IDs.

        Returns:
            AssistantMessage formatted for storage with tool_use blocks in content array.
        """
        if not isinstance(response, ChatCompletion):
            return AssistantMessage(role="assistant", content=[{"type": "text", "text": ""}])

        content_blocks: List[Dict[str, Any]] = []

        # Extract reasoning content first (K2 Thinking models)
        reasoning_content = KimiResponseProcessor.extract_reasoning_content(response)
        if reasoning_content:
            content_blocks.append({"type": "thinking", "thinking": reasoning_content})

        # Extract text content
        text_content = KimiResponseProcessor.extract_text_content(response)
        if text_content:
            content_blocks.append({"type": "text", "text": text_content})

        # Reuse pre-extracted tool calls if provided, otherwise extract now
        if tool_calls is None:
            tool_calls = KimiResponseProcessor.extract_tool_calls(response)

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
        Format Kimi ChatCompletion response for working context.

        Extracts data from API response and builds message dict in Chat Completions
        format for use in subsequent API calls.

        This method handles the same logic previously in context_manager.add_response(),
        now centralized in the response processor for better separation of concerns.

        Args:
            response: ChatCompletion object from Kimi API

        Returns:
            Message dict ready to append to working_contents, or None if invalid.

            Message dict structure:
                {
                    "role": "assistant",
                    "reasoning_content": "..." (optional - K2 Thinking models),
                    "tool_calls": [...] (optional),
                    "content": "..." (omitted if empty and tool_calls present)
                }
        """
        # Validate response type
        if not isinstance(response, ChatCompletion):
            return None

        # Validate choices exist
        if not response.choices:
            return None

        # Extract message
        choice = response.choices[0]
        message = choice.message

        # Extract reasoning content (K2 Thinking models)
        reasoning_content = getattr(message, 'reasoning_content', None)

        # Build message dict in Chat Completions format
        message_dict: Dict[str, Any] = {
            "role": message.role
        }

        # Add reasoning_content as separate field if present (Kimi k2-thinking format)
        if reasoning_content and reasoning_content.strip():
            message_dict["reasoning_content"] = reasoning_content

        # Add tool calls if present
        has_tool_calls = bool(message.tool_calls)
        if has_tool_calls and message.tool_calls:
            # Convert tool calls to dict format
            tool_calls_list = []
            for tool_call in message.tool_calls:
                # tool_call is ChatCompletionMessageToolCall with id, type, function
                function_info = tool_call.function  # type: ignore
                tool_calls_list.append({
                    "id": tool_call.id,
                    "type": tool_call.type,
                    "function": {
                        "name": function_info.name,  # type: ignore
                        "arguments": function_info.arguments  # type: ignore
                    }
                })
            message_dict["tool_calls"] = tool_calls_list

        # Add content field - omit if empty and tool_calls present
        if message.content or not has_tool_calls:
            message_dict["content"] = message.content

        return message_dict

    @staticmethod
    def extract_web_search_sources(response, debug: bool = False) -> List[Dict[str, Any]]:
        """
        Extract web search sources from Kimi response.

        Kimi supports web search through the $web_search builtin_tool.
        Search results are integrated directly into the response text.
        """
        sources = []

        if not isinstance(response, ChatCompletion):
            return sources

        if not response.choices:
            return sources

        # Check if web search tool was used
        message = response.choices[0].message
        if message.tool_calls:
            for tool_call in message.tool_calls:
                function = getattr(tool_call, 'function', None)
                if function and getattr(function, 'name', '') == '$web_search':
                    # Web search was performed
                    # Kimi integrates results into text, so we mark it
                    sources.append({
                        "title": "Kimi Web Search",
                        "url": "",
                        "snippet": "Search results integrated into response",
                        "type": "web_search"
                    })

        if debug and sources:
            print(f"[DEBUG] Extracted {len(sources)} web search sources from Kimi response")

        return sources

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
            - Reasoning content (K2 Thinking models)
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
            final_response = metadata.get("__kimi_final_response")
            if final_response:
                return final_response

        # If no final response found, construct from chunks
        # Collect thinking, text content, and tool calls
        reasoning_content = ""
        text_content = ""
        tool_calls = []

        for chunk in chunks:
            if chunk.chunk_type == "thinking" and chunk.content:
                # Accumulate reasoning content (K2 Thinking models)
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

        # Add reasoning_content to message object (K2 Thinking models)
        # This is a dynamic attribute that will be extracted by response processor
        if reasoning_content:
            setattr(message, 'reasoning_content', reasoning_content)

        choice = Choice(
            index=0,
            message=message,
            finish_reason="stop" if not tool_calls else "tool_calls"
        )

        # Get model name from config
        from backend.config.llm import get_llm_settings
        model_name = get_llm_settings().get_kimi_config().model

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
        Create Kimi streaming processor instance.

        Returns:
            KimiStreamingProcessor: Stateful processor for Kimi streaming
        """
        return KimiStreamingProcessor()


__all__ = ['KimiResponseProcessor']
