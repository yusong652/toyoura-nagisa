"""
Zhipu (智谱) client implementation using official zai SDK.

This implementation uses the zai-sdk which provides access to Zhipu GLM models.
Since zai SDK is synchronous, we use asyncio.to_thread() for async compatibility.
"""

import json
import time
import asyncio
from typing import List, Optional, Dict, Any, AsyncGenerator, Type
from zai import ZhipuAiClient

from backend.infrastructure.llm.base.client import LLMClientBase
from backend.domain.models.messages import BaseMessage
from backend.domain.models.streaming import StreamingChunk
from backend.infrastructure.llm.base.context_manager import BaseContextManager

# Import Zhipu-specific implementations
from .config import get_zhipu_client_config
from .message_formatter import ZhipuMessageFormatter
from .tool_manager import ZhipuToolManager
from .context_manager import ZhipuContextManager
from .debug import ZhipuDebugger
from .response_processor import ZhipuResponseProcessor


class ZhipuClient(LLMClientBase):
    """
    Zhipu GLM client implementation using official zai SDK.

    Key Features:
    - Official zai-sdk integration
    - Full streaming support with tool calling
    - Thinking/reasoning mode support
    - Real-time tool execution notifications

    Note: zai SDK is synchronous, so we use asyncio.to_thread() for async operations.
    """

    def __init__(self, api_key: str, **kwargs):
        """
        Initialize Zhipu client.

        Args:
            api_key: Zhipu API key
            **kwargs: Additional configuration parameters
        """
        super().__init__(**kwargs)
        self.api_key = api_key

        # Initialize Zhipu-specific configuration
        config_overrides = {}

        # Extract relevant configuration from extra_config for overrides
        if 'model' in self.extra_config:
            config_overrides['model_settings'] = {'model': self.extra_config['model']}
        if 'temperature' in self.extra_config:
            if 'model_settings' not in config_overrides:
                config_overrides['model_settings'] = {}
            config_overrides['model_settings']['temperature'] = self.extra_config['temperature']
        if 'max_tokens' in self.extra_config:
            if 'model_settings' not in config_overrides:
                config_overrides['model_settings'] = {}
            config_overrides['model_settings']['max_tokens'] = self.extra_config['max_tokens']
        if 'debug' in self.extra_config:
            config_overrides['debug'] = self.extra_config['debug']

        self.zhipu_config = get_zhipu_client_config(**config_overrides)

        # Log initialization
        print(f"Zhipu Client initialized")
        print(f"  Model: {self.zhipu_config.model_settings.model}")
        print(f"  Base URL: {self.zhipu_config.base_url}")

        # Debug: Print masked API key
        if self.api_key:
            masked_key = f"{self.api_key[:8]}...{self.api_key[-4:]}" if len(self.api_key) > 12 else "***"
            print(f"  API Key (masked): {masked_key}")

        # Initialize zai SDK client
        client_kwargs: Dict[str, Any] = {
            "api_key": self.api_key,
            "base_url": self.zhipu_config.base_url,
            "timeout": self.zhipu_config.timeout,
            "max_retries": self.zhipu_config.max_retries
        }

        # Allow custom base URL override
        if 'base_url' in self.extra_config:
            client_kwargs['base_url'] = self.extra_config['base_url']

        self.client = ZhipuAiClient(**client_kwargs)

        # Initialize unified tool manager
        self.tool_manager = ZhipuToolManager()

    # ========== CORE API METHODS ==========

    async def call_api_with_context(
        self,
        context_contents: List[Dict[str, Any]],
        api_config: Dict[str, Any],
        **kwargs
    ):
        """
        Execute a stateless Zhipu API call with prepared context.

        Uses zai SDK (synchronous), wrapped with asyncio.to_thread() for async compatibility.

        Args:
            context_contents: Conversation messages in standard format.
            api_config: Provider configuration including tools and system prompt.
            **kwargs: Optional overrides (temperature, max_tokens, top_p).

        Returns:
            Response object from zai SDK.
        """
        debug = self.zhipu_config.debug

        tools = api_config.get("tools", []) or []

        # Build messages
        messages = context_contents.copy()

        # Add system message if provided
        system_prompt = api_config.get("system_prompt")
        if system_prompt:
            messages.insert(0, {
                "role": "system",
                "content": system_prompt
            })

        # Build API call parameters
        api_kwargs: Dict[str, Any] = {
            "model": self.zhipu_config.model_settings.model,
            "messages": messages,
            "temperature": self.zhipu_config.model_settings.temperature,
            "top_p": self.zhipu_config.model_settings.top_p,
            "stream": False,
        }

        if self.zhipu_config.model_settings.max_tokens:
            api_kwargs["max_tokens"] = self.zhipu_config.model_settings.max_tokens

        # Add tools if provided
        if tools:
            api_kwargs["tools"] = tools
            api_kwargs["tool_choice"] = "auto"

        # Enable thinking mode if requested (GLM thinking models)
        if kwargs.get('enable_thinking', False):
            api_kwargs["thinking"] = {"type": "enabled"}

        # Apply runtime overrides
        if 'temperature' in kwargs:
            api_kwargs['temperature'] = kwargs['temperature']
        if 'max_tokens' in kwargs:
            api_kwargs['max_tokens'] = kwargs['max_tokens']
        if 'top_p' in kwargs:
            api_kwargs['top_p'] = kwargs['top_p']

        if debug:
            ZhipuDebugger.print_api_request(api_kwargs, messages, tools)

        try:
            # Wrap synchronous call with asyncio.to_thread
            response = await asyncio.to_thread(
                self.client.chat.completions.create,
                **api_kwargs
            )

            if debug:
                print(f"[DEBUG] Zhipu response received:")
                print(f"[DEBUG] Finish reason: {response.choices[0].finish_reason}")
                if hasattr(response, 'usage') and response.usage:
                    print(f"[DEBUG] Token usage: {response.usage}")

            return response
        except Exception as exc:
            if debug:
                print(f"[DEBUG] Zhipu API call failed: {exc}")
            raise

    async def call_api_with_context_streaming(
        self,
        context_contents: List[Dict[str, Any]],
        api_config: Dict[str, Any],
        **kwargs
    ) -> AsyncGenerator[StreamingChunk, None]:
        """
        Execute streaming Zhipu API call with real-time chunk delivery.

        Args:
            context_contents: Conversation messages in standard format.
            api_config: Provider configuration including tools and system prompt.
            **kwargs: Optional overrides.

        Yields:
            StreamingChunk: Standardized streaming data chunks.
        """
        debug = self.zhipu_config.debug

        tools = api_config.get("tools", []) or []

        # Build messages
        messages = context_contents.copy()

        # Add system message if provided
        system_prompt = api_config.get("system_prompt")
        if system_prompt:
            messages.insert(0, {
                "role": "system",
                "content": system_prompt
            })

        # Build API call parameters
        api_kwargs: Dict[str, Any] = {
            "model": self.zhipu_config.model_settings.model,
            "messages": messages,
            "temperature": self.zhipu_config.model_settings.temperature,
            "top_p": self.zhipu_config.model_settings.top_p,
            "stream": True,  # Enable streaming
        }

        if self.zhipu_config.model_settings.max_tokens:
            api_kwargs["max_tokens"] = self.zhipu_config.model_settings.max_tokens

        # Add tools if provided
        if tools:
            api_kwargs["tools"] = tools
            api_kwargs["tool_choice"] = "auto"

        # Enable thinking mode if requested (GLM thinking models)
        if kwargs.get('enable_thinking', True):  # Default to enabled for streaming
            api_kwargs["thinking"] = {"type": "enabled"}

        # Apply runtime overrides
        if 'temperature' in kwargs:
            api_kwargs['temperature'] = kwargs['temperature']
        if 'max_tokens' in kwargs:
            api_kwargs['max_tokens'] = kwargs['max_tokens']
        if 'top_p' in kwargs:
            api_kwargs['top_p'] = kwargs['top_p']

        if debug:
            ZhipuDebugger.print_api_request(api_kwargs, messages, tools)

        try:
            # Create streaming response (synchronous generator)
            # We need to wrap iteration in asyncio.to_thread
            stream = await asyncio.to_thread(
                self.client.chat.completions.create,
                **api_kwargs
            )

            # Track tool calls being built
            current_tool_calls: Dict[int, Dict[str, Any]] = {}

            # Iterate through stream chunks
            for chunk in stream:
                if not hasattr(chunk, 'choices') or not chunk.choices:
                    continue

                choice = chunk.choices[0]
                delta = choice.delta

                # Handle reasoning content (GLM Thinking models)
                reasoning_delta = getattr(delta, 'reasoning_content', None)
                if reasoning_delta:
                    yield StreamingChunk(
                        chunk_type="thinking",
                        content=reasoning_delta,
                        metadata={"index": choice.index, "is_reasoning": True}
                    )

                # Handle text content
                if hasattr(delta, 'content') and delta.content:
                    yield StreamingChunk(
                        chunk_type="text",
                        content=delta.content,
                        metadata={"index": choice.index}
                    )

                # Handle tool calls
                if hasattr(delta, 'tool_calls') and delta.tool_calls:
                    for tool_call_delta in delta.tool_calls:
                        idx = tool_call_delta.index

                        # Initialize tool call if not exists
                        if idx not in current_tool_calls:
                            current_tool_calls[idx] = {
                                "id": tool_call_delta.id or "",
                                "type": tool_call_delta.type or "function",
                                "function": {
                                    "name": "",
                                    "arguments": ""
                                }
                            }

                        # Update tool call data
                        if tool_call_delta.id:
                            current_tool_calls[idx]["id"] = tool_call_delta.id

                        if tool_call_delta.function:
                            if tool_call_delta.function.name:
                                current_tool_calls[idx]["function"]["name"] = tool_call_delta.function.name
                            if tool_call_delta.function.arguments:
                                current_tool_calls[idx]["function"]["arguments"] += tool_call_delta.function.arguments

                # Check if tool call is complete
                if hasattr(choice, 'finish_reason') and choice.finish_reason == "tool_calls" and current_tool_calls:
                    for tool_call in current_tool_calls.values():
                        # Parse arguments string to dict
                        arguments_str = tool_call["function"]["arguments"]
                        try:
                            arguments_dict = json.loads(arguments_str) if arguments_str else {}
                        except json.JSONDecodeError:
                            arguments_dict = {}

                        yield StreamingChunk(
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
                        )
                    current_tool_calls.clear()

        except Exception as e:
            if debug:
                print(f"[DEBUG] Zhipu streaming failed: {e}")
            raise

    def get_or_create_context_manager(self, session_id: str):
        """
        Get or create a context manager for a specific session.

        Args:
            session_id: Unique session identifier

        Returns:
            ZhipuContextManager instance for this session
        """
        if session_id not in self._session_context_managers:
            self._session_context_managers[session_id] = ZhipuContextManager(session_id=session_id)
        return self._session_context_managers[session_id]

    # ========== ABSTRACT METHOD IMPLEMENTATIONS ==========

    def _get_response_processor(self):
        """Get Zhipu-specific response processor instance."""
        return ZhipuResponseProcessor()

    def _get_context_manager_class(self):
        """Get Zhipu-specific context manager class."""
        return ZhipuContextManager

    def _get_provider_config(self):
        """Get Zhipu-specific configuration object."""
        return self.zhipu_config

    async def _prepare_complete_context(
        self,
        session_id: str
    ) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Prepare complete context and API configuration for stateless Zhipu API call.

        Args:
            session_id: Session identifier

        Returns:
            Tuple containing:
            - context_contents: Messages for Zhipu API (without system prompt)
            - api_config: Dictionary with 'tools' and 'system_prompt' keys
        """
        # Get context manager (automatically initialized from history on creation)
        context_manager = self.get_or_create_context_manager(session_id)

        agent_profile = getattr(context_manager, 'agent_profile', 'general')
        enable_memory = getattr(context_manager, 'enable_memory', True)

        # Get tool schemas for API
        tool_schemas = await self.tool_manager.get_function_call_schemas(session_id, agent_profile)

        # Get tool schemas formatted for system prompt
        prompt_tool_schemas = await self.tool_manager.get_schemas_for_system_prompt(session_id, agent_profile)

        # Build system prompt with tool schemas and memory
        from backend.shared.utils.prompt.builder import build_system_prompt

        system_prompt = await build_system_prompt(
            agent_profile=agent_profile,
            session_id=session_id,
            enable_memory=enable_memory,
            tool_schemas=prompt_tool_schemas
        )

        # Get working contents from context manager
        working_contents = context_manager.get_working_contents()

        # Return context and config as separate values for thread-safe API call
        api_config = {
            'tools': tool_schemas,
            'system_prompt': system_prompt
        }
        return working_contents, api_config

    def _construct_response_from_streaming_chunks(
        self,
        chunks: List[StreamingChunk]
    ):
        """
        Convert collected streaming chunks back into a complete response object.

        Args:
            chunks: List of streaming chunks

        Returns:
            Mock response object reconstructed from chunks
        """
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


__all__ = ['ZhipuClient']
