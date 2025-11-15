"""
OpenRouter Response Processor

Handles processing of OpenRouter API responses using OpenAI Chat Completions API format.

OpenRouter uses the traditional Chat Completions API which returns ChatCompletion objects.
"""

import json
from typing import List, Dict, Any, Optional
from openai.types.chat import ChatCompletion, ChatCompletionMessage
from backend.domain.models.messages import AssistantMessage
from backend.domain.models.streaming import StreamingChunk
from backend.infrastructure.llm.base.response_processor import BaseResponseProcessor
from .debug import OpenRouterDebugger


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
        from backend.config.llm import get_llm_settings
        if get_llm_settings().debug:
            raw_tool_calls = []
            for tc in message.tool_calls:
                raw_tool_calls.append({
                    'id': tc.id,
                    'function': {
                        'name': tc.function.name,
                        'arguments': tc.function.arguments
                    }
                })
            OpenRouterDebugger.print_tool_call_received(raw_tool_calls)

        tool_calls: List[Dict[str, Any]] = []

        for tool_call in message.tool_calls:
            try:
                # ChatCompletion tool_calls have: id, type, function
                # function has: name, arguments (as string)
                arguments = tool_call.function.arguments

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
                    "name": tool_call.function.name,
                    "arguments": parsed_args,
                    "id": tool_call.id
                })
            except Exception as exc:
                print(f"[WARNING] Failed to parse tool call: {exc}")
                continue

        # Debug: Print extracted tool calls
        from backend.config.llm import get_llm_settings
        if get_llm_settings().debug:
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
                    "tool_calls": [...] (optional),
                    "content": "..."
                }
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

        # Add tool calls if present
        if message.tool_calls:
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
        # Collect text content
        text_content = ""
        tool_calls = []

        for chunk in chunks:
            if chunk.chunk_type == "text" and chunk.content:
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

        choice = Choice(
            index=0,
            message=message,
            finish_reason="stop" if not tool_calls else "tool_calls"
        )

        # Get model name from config
        from backend.config.llm import get_llm_settings
        model_name = get_llm_settings().get_openrouter_config().model

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


__all__ = ['OpenRouterResponseProcessor']
