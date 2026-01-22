"""
Zhipu (智谱) Response Processor

Handles processing of Zhipu API responses from zai SDK.

Zhipu uses ChatCompletion-like format similar to OpenAI Chat Completions API.
"""

import json
from typing import List, Dict, Any, Optional
from backend.domain.models.messages import AssistantMessage
from backend.domain.models.streaming import StreamingChunk
from backend.infrastructure.llm.base.response_processor import BaseResponseProcessor, BaseStreamingProcessor
from .debug import ZhipuDebugger
from backend.config.dev import get_dev_config


class ZhipuStreamingProcessor(BaseStreamingProcessor):
    """
    Stateful streaming processor for Zhipu API.

    Processes Zhipu ChatCompletionChunk-like events and converts them into
    standardized StreamingChunk objects. Maintains state to track tool calls
    and reasoning content across chunks.
    """

    def __init__(self):
        """Initialize streaming processor with state tracking."""
        # Track tool calls being built (indexed by index)
        self.current_tool_calls: Dict[int, Dict[str, Any]] = {}
        # Track reasoning content being built (GLM Thinking models)
        self.reasoning_buffer: str = ""

    def process_event(self, event: Any) -> List[StreamingChunk]:
        """
        Process Zhipu streaming chunk into standardized StreamingChunk objects.

        Args:
            event: Zhipu ChatCompletionChunk-like object from zai SDK

        Returns:
            List[StreamingChunk]: List of standardized chunks to yield
        """
        result = []

        # Validate chunk structure
        if not hasattr(event, 'choices') or not event.choices:
            return result

        choice = event.choices[0]
        if not hasattr(choice, 'delta'):
            return result

        delta = choice.delta

        # Extract usage metadata if available (in final chunk with finish_reason)
        usage_metadata = {}
        if hasattr(event, 'usage') and event.usage:
            usage = event.usage
            usage_metadata = {
                'prompt_token_count': getattr(usage, 'prompt_tokens', None),
                'candidates_token_count': getattr(usage, 'completion_tokens', None),
                'total_token_count': getattr(usage, 'total_tokens', None),
            }
            # Extract detailed token counts if available
            if hasattr(usage, 'completion_tokens_details') and usage.completion_tokens_details:
                usage_metadata['reasoning_tokens'] = getattr(usage.completion_tokens_details, 'reasoning_tokens', None)
            if hasattr(usage, 'prompt_tokens_details') and usage.prompt_tokens_details:
                cached = getattr(usage.prompt_tokens_details, 'cached_tokens', None)
                if cached:
                    usage_metadata['cached_tokens'] = cached

        # Handle reasoning content (GLM Thinking models)
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
                    function_info = tool_call_delta.function

                    # Handle both object and dict formats
                    if isinstance(function_info, dict):
                        func_name = function_info.get('name', '')
                        func_args = function_info.get('arguments', '')
                    else:
                        # Object with attributes
                        func_name = getattr(function_info, 'name', '')
                        func_args = getattr(function_info, 'arguments', '')

                    if func_name:
                        self.current_tool_calls[idx]["function"]["name"] = func_name
                    if func_args:
                        self.current_tool_calls[idx]["function"]["arguments"] += func_args

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

        # If we have usage metadata but didn't produce any chunks, create a metadata-only chunk
        # This ensures usage information from the final chunk is not lost
        if usage_metadata and not result:
            result.append(StreamingChunk(
                chunk_type="text",
                content="",
                metadata=usage_metadata
            ))

        return result


class ZhipuResponseProcessor(BaseResponseProcessor):
    """
    Process Zhipu API responses using ChatCompletion-like format from zai SDK.

    Supports reasoning_content extraction for GLM thinking models.
    """

    @staticmethod
    def extract_text_content(response) -> str:
        """
        Extract text content from Zhipu response.

        Args:
            response: Response object from zai SDK

        Returns:
            Extracted text content as a single string.
        """
        if not hasattr(response, 'choices') or not response.choices:
            return ""

        message = response.choices[0].message
        return getattr(message, 'content', '') or ""

    @staticmethod
    def extract_reasoning_content(response) -> Optional[str]:
        """
        Extract reasoning content from Zhipu GLM Thinking response.

        GLM models with thinking enabled expose a `reasoning_content` field that contains
        the model's intermediate reasoning/thinking process before the final answer.

        Args:
            response: Response object from zai SDK

        Returns:
            Extracted reasoning content as a string, or None if not available.
        """
        if not hasattr(response, 'choices') or not response.choices:
            return None

        message = response.choices[0].message

        # Access reasoning_content attribute if it exists (GLM Thinking models)
        reasoning_content = getattr(message, 'reasoning_content', None)

        return reasoning_content if reasoning_content else None

    @staticmethod
    def has_tool_calls(response) -> bool:
        """
        Check if response contains tool calls.
        """
        if not hasattr(response, 'choices') or not response.choices:
            return False

        message = response.choices[0].message
        return bool(hasattr(message, 'tool_calls') and message.tool_calls)

    @staticmethod
    def extract_tool_calls(response) -> List[Dict[str, Any]]:
        """
        Extract tool calls from Zhipu response.

        Args:
            response: Response object from zai SDK

        Returns:
            List of tool call dictionaries with name, arguments, and id.
        """
        if not hasattr(response, 'choices') or not response.choices:
            return []

        message = response.choices[0].message
        if not hasattr(message, 'tool_calls') or not message.tool_calls:
            return []

        # Debug: Print raw tool calls from API
        if get_dev_config().debug_mode:
            raw_tool_calls = []
            for tc in message.tool_calls:
                function = getattr(tc, 'function', None)
                if function:
                    # Handle both object and dict formats in debug output too
                    if isinstance(function, dict):
                        func_name = function.get('name', '')
                        func_args = function.get('arguments', '')
                    else:
                        func_name = getattr(function, 'name', '')
                        func_args = getattr(function, 'arguments', '')

                    raw_tool_calls.append({
                        'id': tc.id,
                        'function': {
                            'name': func_name,
                            'arguments': func_args
                        }
                    })
                    
        tool_calls: List[Dict[str, Any]] = []

        for tool_call in message.tool_calls:
            try:
                # Tool calls have: id, type, function
                # function has: name, arguments (as string)
                function = getattr(tool_call, 'function', None)
                if not function:
                    continue

                # Handle both object and dict formats
                # zai SDK might return either depending on the response structure
                if isinstance(function, dict):
                    function_name = function.get('name', '')
                    arguments = function.get('arguments', '')
                else:
                    # Object with attributes
                    function_name = getattr(function, 'name', '')
                    arguments = getattr(function, 'arguments', '')

                # Parse arguments string to dict if needed
                if isinstance(arguments, str):
                    try:
                        # Handle empty string or whitespace-only string
                        if not arguments or not arguments.strip():
                            parsed_args = {}
                        else:
                            parsed_args = json.loads(arguments)
                    except json.JSONDecodeError:
                        # If parsing fails, return empty dict
                        print(f"[WARNING] Failed to parse Zhipu tool arguments as JSON: {arguments}")
                        parsed_args = {}
                else:
                    parsed_args = arguments if arguments else {}

                tool_calls.append({
                    "name": function_name,
                    "arguments": parsed_args,
                    "id": tool_call.id
                })
            except Exception as exc:
                print(f"[WARNING] Failed to parse Zhipu tool call: {exc}")
                continue

        # Debug: Print extracted tool calls
        if get_dev_config().debug_mode:
            print(f"[DEBUG] Zhipu extracted tool calls: {tool_calls}")

        return tool_calls

    @staticmethod
    def format_response_for_storage(
        response,
        tool_calls: Optional[List[Dict[str, Any]]] = None
    ) -> AssistantMessage:
        """
        Format Zhipu response for storage in message history.

        Args:
            response: Response object from zai SDK
            tool_calls: Pre-extracted tool calls (optional)

        Returns:
            AssistantMessage formatted for storage with tool_use blocks in content array.
        """
        if not hasattr(response, 'choices') or not response.choices:
            return AssistantMessage(role="assistant", content=[{"type": "text", "text": ""}])

        content_blocks: List[Dict[str, Any]] = []

        # Extract reasoning content first (GLM Thinking models)
        reasoning_content = ZhipuResponseProcessor.extract_reasoning_content(response)
        # Only save reasoning if it has non-whitespace content
        if reasoning_content and reasoning_content.strip():
            content_blocks.append({"type": "thinking", "thinking": reasoning_content})

        # Extract text content
        text_content = ZhipuResponseProcessor.extract_text_content(response)
        # Only save text if it has non-whitespace content
        if text_content and text_content.strip():
            content_blocks.append({"type": "text", "text": text_content})

        # Reuse pre-extracted tool calls if provided, otherwise extract now
        if tool_calls is None:
            tool_calls = ZhipuResponseProcessor.extract_tool_calls(response)

        # Add tool_use blocks to content array
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
    def extract_web_search_sources(response, debug: bool = False) -> List[Dict[str, Any]]:
        """
        Extract web search sources from Zhipu response.

        Zhipu supports web search through the web_search tool type.
        """
        sources = []

        if not hasattr(response, 'choices') or not response.choices:
            return sources

        # Check if web search tool was used
        message = response.choices[0].message
        if hasattr(message, 'tool_calls') and message.tool_calls:
            for tool_call in message.tool_calls:
                if getattr(tool_call, 'type', '') == 'web_search':
                    # Web search was performed
                    sources.append({
                        "title": "Zhipu Web Search",
                        "url": "",
                        "snippet": "Search results integrated into response",
                        "type": "web_search"
                    })

        if debug and sources:
            print(f"[DEBUG] Extracted {len(sources)} web search sources from Zhipu response")

        return sources

    @staticmethod
    def format_response_for_context(response) -> Optional[Dict[str, Any]]:
        """
        Format Zhipu ChatCompletion response for working context.

        Extracts data from API response and builds message dict for use in
        subsequent API calls.

        This method centralizes the formatting logic previously in
        context_manager.add_response() for better separation of concerns.

        Args:
            response: ChatCompletion-like object from zai SDK

        Returns:
            Message dict ready to append to working_contents, or None if invalid.

            Message dict structure:
                {
                    "role": "assistant",
                    "reasoning_content": "..." (optional - GLM thinking models),
                    "tool_calls": [...] (optional),
                    "content": "..." (omitted if empty and tool_calls present)
                }
        """
        if not hasattr(response, 'choices') or not response.choices:
            return None

        choice = response.choices[0]
        message = choice.message

        # Extract reasoning content (GLM thinking models)
        reasoning_content = getattr(message, 'reasoning_content', None)

        # Build message dict
        message_dict: Dict[str, Any] = {
            "role": message.role
        }

        # Add reasoning_content as separate field if present (Zhipu API format)
        if reasoning_content and reasoning_content.strip():
            message_dict["reasoning_content"] = reasoning_content

        # Add tool calls if present
        has_tool_calls = hasattr(message, 'tool_calls') and bool(message.tool_calls)
        if has_tool_calls:
            # Convert tool calls to dict format
            tool_calls_list = []
            for tool_call in message.tool_calls:
                function_info = tool_call.function

                # Handle both object and dict formats
                # zai SDK might return either depending on the response structure
                if isinstance(function_info, dict):
                    function_name = function_info.get('name', '')
                    function_arguments = function_info.get('arguments', '')
                else:
                    # Object with attributes
                    function_name = getattr(function_info, 'name', '')
                    function_arguments = getattr(function_info, 'arguments', '')

                tool_calls_list.append({
                    "id": tool_call.id,
                    "type": tool_call.type,
                    "function": {
                        "name": function_name,
                        "arguments": function_arguments
                    }
                })
            message_dict["tool_calls"] = tool_calls_list

        # Add content field - omit if whitespace-only when tool_calls present
        # API may return newlines as default response, treat whitespace-only as empty
        # to avoid few-shot effect where LLM learns to return empty responses
        content_text = message.content
        has_meaningful_content = content_text and content_text.strip()

        if has_meaningful_content:
            message_dict["content"] = content_text
        elif not has_tool_calls:
            # No tool calls and no meaningful content - keep empty string for API compatibility
            message_dict["content"] = ""
        # Else: has tool_calls but only whitespace content - omit content field

        return message_dict

    @staticmethod
    def construct_response_from_chunks(chunks: List['StreamingChunk']):
        """
        Convert collected streaming chunks back into a complete response object.

        Args:
            chunks: List of StreamingChunk objects collected during streaming

        Returns:
            Mock response object reconstructed from chunks

        Note:
            This reconstruction preserves all essential fields including:
            - Reasoning content (GLM Thinking models)
            - Text content
            - Tool calls with IDs and arguments
            - All metadata needed for tool calling logic
        """
        import json
        from backend.domain.models.streaming import StreamingChunk

        # Check if we have a final response stored in metadata
        for chunk in reversed(chunks):
            metadata = chunk.metadata or {}
            final_response = metadata.get("__zhipu_final_response")
            if final_response:
                return final_response

        # If no final response found, construct from chunks
        # Collect thinking, text content, and tool calls
        reasoning_content = ""
        text_content = ""
        tool_calls = []

        for chunk in chunks:
            if chunk.chunk_type == "thinking" and chunk.content:
                # Accumulate reasoning content (GLM Thinking models)
                reasoning_content += chunk.content
            elif chunk.chunk_type == "text" and chunk.content:
                text_content += chunk.content
            elif chunk.chunk_type == "function_call" and chunk.function_call:
                # Get tool_call_id from metadata if available
                tool_call_id = chunk.metadata.get("tool_call_id", "") if chunk.metadata else ""

                # Convert args dict to JSON string
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

        # Construct a mock response object
        # This is a simplified structure that matches what response_processor expects
        class MockMessage:
            def __init__(self, content, reasoning_content, tool_calls):
                self.role = "assistant"
                self.content = content
                self.reasoning_content = reasoning_content
                self.tool_calls = tool_calls if tool_calls else None

        class MockChoice:
            def __init__(self, message, finish_reason):
                self.message = message
                self.finish_reason = finish_reason

        class MockResponse:
            def __init__(self, choices):
                self.choices = choices

        message = MockMessage(
            content=text_content if text_content else None,
            reasoning_content=reasoning_content if reasoning_content else None,
            tool_calls=[type('obj', (object,), tc) for tc in tool_calls] if tool_calls else None
        )

        choice = MockChoice(
            message=message,
            finish_reason="stop" if not tool_calls else "tool_calls"
        )

        return MockResponse(choices=[choice])

    @staticmethod
    def extract_web_search_sources(response: Any) -> List[Dict[str, Any]]:
        """
        Extract web search sources from Zhipu response.

        Zhipu's web_search returns a search_result array in the response
        with structured search results including title, content, link, etc.

        Args:
            response: Completion response from Zhipu API

        Returns:
            List of source dictionaries with url, title, and snippet
        """
        sources = []

        # Check if response has search_result field
        if hasattr(response, "search_result") and response.search_result:
            for result in response.search_result:
                sources.append({
                    "url": getattr(result, "link", ""),
                    "title": getattr(result, "title", ""),
                    "snippet": getattr(result, "content", ""),
                })

        return sources

    @staticmethod
    def create_streaming_processor() -> BaseStreamingProcessor:
        """
        Create Zhipu streaming processor instance.

        Returns:
            ZhipuStreamingProcessor: Stateful processor for Zhipu streaming
        """
        return ZhipuStreamingProcessor()


__all__ = ['ZhipuResponseProcessor']
