"""
Kimi (Moonshot) Response Processor

Handles processing of Kimi API responses using OpenAI Chat Completions API format.

Unlike OpenAI's Responses API, Kimi uses the traditional Chat Completions API
which returns ChatCompletion objects instead of Response objects.
"""

import json
from typing import List, Dict, Any, Optional
from openai.types.chat import ChatCompletion, ChatCompletionMessage
from backend.domain.models.messages import AssistantMessage
from backend.domain.models.streaming import StreamingChunk
from backend.infrastructure.llm.base.response_processor import BaseResponseProcessor
from .debug import KimiDebugger


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


__all__ = ['KimiResponseProcessor']
