"""
Kimi (Moonshot) client implementation using OpenAI-compatible API.

This implementation uses the standard OpenAI Chat Completions API format
since Kimi/Moonshot provides full OpenAI compatibility.

Base URL: https://api.moonshot.cn/v1
"""

from typing import List, Optional, Dict, Any, AsyncGenerator
from openai import OpenAI, AsyncOpenAI
from openai.types.chat import ChatCompletion, ChatCompletionChunk

from backend.infrastructure.llm.base.client import LLMClientBase
from backend.domain.models.messages import BaseMessage
from backend.domain.models.streaming import StreamingChunk

# Import Kimi-specific implementations (reuse OpenAI components where applicable)
from .config import get_kimi_client_config
from backend.infrastructure.llm.providers.openai.message_formatter import OpenAIMessageFormatter
from backend.infrastructure.llm.providers.openai.tool_manager import OpenAIToolManager
from backend.infrastructure.llm.providers.openai.context_manager import OpenAIContextManager


class KimiClient(LLMClientBase):
    """
    Kimi (Moonshot) client implementation using OpenAI-compatible API.

    Key Features:
    - OpenAI-compatible Chat Completions API
    - Long-context support (up to 200K tokens)
    - Full streaming support with tool calling
    - Real-time tool execution notifications

    Kimi specializes in:
    - Long document understanding and analysis
    - Multi-turn conversations with extensive context
    - Chinese language processing
    """

    def __init__(self, api_key: str, **kwargs):
        """
        Initialize Kimi client with OpenAI-compatible setup.

        Args:
            api_key: Moonshot API key (MOONSHOT_API_KEY)
            **kwargs: Additional configuration parameters
                - base_url: Custom API base URL (default: https://api.moonshot.cn/v1)
                - model: Model name override
                - temperature: Sampling temperature
                - max_tokens: Maximum output tokens
        """
        super().__init__(**kwargs)
        self.api_key = api_key

        # Initialize Kimi-specific configuration
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

        self.kimi_config = get_kimi_client_config(**config_overrides)

        print(f"Kimi Client initialized with model: {self.kimi_config.model_settings.model}")
        print(f"Kimi Base URL: {self.kimi_config.base_url}")

        # Initialize both sync and async OpenAI clients with Kimi base URL
        client_kwargs: Dict[str, Any] = {
            "api_key": self.api_key,
            "base_url": self.kimi_config.base_url
        }

        # Allow custom base URL override
        if 'base_url' in self.extra_config:
            client_kwargs['base_url'] = self.extra_config['base_url']

        # Add custom headers if needed
        if 'default_headers' in self.extra_config:
            client_kwargs['default_headers'] = self.extra_config['default_headers']

        self.client = OpenAI(**client_kwargs)
        self.async_client = AsyncOpenAI(**client_kwargs)

        # Initialize unified tool manager (reuse OpenAI's implementation)
        self.tool_manager = OpenAIToolManager()

    # ========== CORE API METHODS ==========

    async def call_api_with_context(
        self,
        context_contents: List[Dict[str, Any]],
        api_config: Dict[str, Any],
        **kwargs
    ) -> ChatCompletion:
        """
        Execute a stateless Kimi API call with prepared context.

        Uses standard OpenAI Chat Completions API format.

        Args:
            context_contents: Conversation messages in OpenAI format.
            api_config: Provider configuration including tools and system prompt.
            **kwargs: Optional overrides (temperature, max_tokens, top_p).

        Returns:
            ChatCompletion object from OpenAI-compatible API.
        """
        debug = self.kimi_config.debug

        tools = api_config.get("tools", []) or []

        # Build messages (Kimi uses standard OpenAI format)
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
            "model": self.kimi_config.model_settings.model,
            "messages": messages,
            "temperature": self.kimi_config.model_settings.temperature,
            "top_p": self.kimi_config.model_settings.top_p,
        }

        if self.kimi_config.model_settings.max_tokens:
            api_kwargs["max_tokens"] = self.kimi_config.model_settings.max_tokens

        # Add tools if provided
        if tools:
            api_kwargs["tools"] = tools
            api_kwargs["tool_choice"] = "auto"

        # Apply runtime overrides
        if 'temperature' in kwargs:
            api_kwargs['temperature'] = kwargs['temperature']
        if 'max_tokens' in kwargs:
            api_kwargs['max_tokens'] = kwargs['max_tokens']
        if 'top_p' in kwargs:
            api_kwargs['top_p'] = kwargs['top_p']

        if debug:
            print(f"[DEBUG] Kimi API call:")
            print(f"[DEBUG] Model: {api_kwargs['model']}")
            print(f"[DEBUG] Messages count: {len(messages)}")
            print(f"[DEBUG] Tools count: {len(tools)}")

        try:
            response = await self.async_client.chat.completions.create(**api_kwargs)

            if debug:
                print(f"[DEBUG] Kimi response received:")
                print(f"[DEBUG] Finish reason: {response.choices[0].finish_reason}")
                if response.usage:
                    print(f"[DEBUG] Token usage: {response.usage}")

            return response
        except Exception as exc:
            if debug:
                print(f"[DEBUG] Kimi API call failed: {exc}")
            raise

    async def call_api_with_context_streaming(
        self,
        context_contents: List[Dict[str, Any]],
        api_config: Dict[str, Any],
        **kwargs
    ) -> AsyncGenerator[StreamingChunk, None]:
        """
        Execute streaming Kimi API call with real-time chunk delivery.

        Args:
            context_contents: Conversation messages in OpenAI format.
            api_config: Provider configuration including tools and system prompt.
            **kwargs: Optional overrides.

        Yields:
            StreamingChunk: Standardized streaming data chunks.
        """
        debug = self.kimi_config.debug

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
            "model": self.kimi_config.model_settings.model,
            "messages": messages,
            "temperature": self.kimi_config.model_settings.temperature,
            "top_p": self.kimi_config.model_settings.top_p,
            "stream": True,  # Enable streaming
        }

        if self.kimi_config.model_settings.max_tokens:
            api_kwargs["max_tokens"] = self.kimi_config.model_settings.max_tokens

        # Add tools if provided
        if tools:
            api_kwargs["tools"] = tools
            api_kwargs["tool_choice"] = "auto"

        # Apply runtime overrides
        if 'temperature' in kwargs:
            api_kwargs['temperature'] = kwargs['temperature']
        if 'max_tokens' in kwargs:
            api_kwargs['max_tokens'] = kwargs['max_tokens']
        if 'top_p' in kwargs:
            api_kwargs['top_p'] = kwargs['top_p']

        if debug:
            print(f"[DEBUG] Kimi streaming API call:")
            print(f"[DEBUG] Model: {api_kwargs['model']}")
            print(f"[DEBUG] Messages count: {len(messages)}")

        try:
            stream = await self.async_client.chat.completions.create(**api_kwargs)

            # Track tool calls being built
            current_tool_calls: Dict[int, Dict[str, Any]] = {}

            async for chunk in stream:
                if not chunk.choices:
                    continue

                choice = chunk.choices[0]
                delta = choice.delta

                # Handle text content
                if delta.content:
                    yield StreamingChunk(
                        chunk_type="text",
                        content=delta.content,
                        metadata={"index": choice.index}
                    )

                # Handle tool calls
                if delta.tool_calls:
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
                if choice.finish_reason == "tool_calls" and current_tool_calls:
                    for tool_call in current_tool_calls.values():
                        yield StreamingChunk(
                            chunk_type="function_call",
                            content="",
                            metadata={
                                "tool_call_id": tool_call["id"],
                                "function_name": tool_call["function"]["name"],
                                "function_args": tool_call["function"]["arguments"]
                            },
                            function_call={
                                "id": tool_call["id"],
                                "name": tool_call["function"]["name"],
                                "arguments": tool_call["function"]["arguments"]
                            }
                        )
                    current_tool_calls.clear()

        except Exception as exc:
            if debug:
                print(f"[DEBUG] Kimi streaming failed: {exc}")
            raise

    def get_or_create_context_manager(self, session_id: str):
        """
        Get or create a context manager for a specific session.

        Args:
            session_id: Unique session identifier

        Returns:
            OpenAIContextManager instance for this session
        """
        if session_id not in self._session_context_managers:
            self._session_context_managers[session_id] = OpenAIContextManager()
        return self._session_context_managers[session_id]
