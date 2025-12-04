"""
OpenRouter client implementation using OpenAI-compatible API.

This implementation uses the standard OpenAI Chat Completions API format
since OpenRouter provides full OpenAI compatibility.

Base URL: https://openrouter.ai/api/v1
"""

import time
from typing import List, Optional, Dict, Any, AsyncGenerator, Type
from openai import OpenAI, AsyncOpenAI
from openai.types.chat import ChatCompletion, ChatCompletionChunk

from backend.infrastructure.llm.base.client import LLMClientBase
from backend.domain.models.messages import BaseMessage
from backend.domain.models.streaming import StreamingChunk
from backend.infrastructure.llm.base.context_manager import BaseContextManager

# Import OpenRouter-specific implementations
from .config import get_openrouter_client_config
from .message_formatter import OpenRouterMessageFormatter
from .tool_manager import OpenRouterToolManager
from .context_manager import OpenRouterContextManager
from .debug import OpenRouterDebugger


class OpenRouterClient(LLMClientBase):
    """
    OpenRouter client implementation using OpenAI-compatible API.

    Key Features:
    - OpenAI-compatible Chat Completions API
    - Access to 100+ models from multiple providers
    - Full streaming support with tool calling
    - Real-time tool execution notifications

    OpenRouter specializes in:
    - Model aggregation and routing
    - Cost optimization across providers
    - Unified interface for multiple LLM providers
    """

    def __init__(self, api_key: str, **kwargs):
        """
        Initialize OpenRouter client with OpenAI-compatible setup.

        Args:
            api_key: OpenRouter API key
            **kwargs: Additional configuration parameters
                - model: Model name override (e.g., "anthropic/claude-sonnet-4-5")
                - temperature: Sampling temperature
                - max_tokens: Maximum output tokens
        """
        super().__init__(**kwargs)
        self.api_key = api_key

        # Initialize OpenRouter-specific configuration
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

        self.openrouter_config = get_openrouter_client_config(**config_overrides)

        # Log initialization
        print(f"OpenRouter Client initialized")
        print(f"  Model: {self.openrouter_config.model_settings.model}")
        print(f"  Base URL: {self.openrouter_config.base_url}")

        # Debug: Print masked API key to verify it's passed correctly
        if self.api_key:
            masked_key = f"{self.api_key[:8]}...{self.api_key[-4:]}" if len(self.api_key) > 12 else "***"
            print(f"  API Key (masked): {masked_key}")

        # Initialize both sync and async OpenAI clients with OpenRouter base URL
        client_kwargs: Dict[str, Any] = {
            "api_key": self.api_key,
            "base_url": self.openrouter_config.base_url
        }

        # Add OpenRouter headers
        if self.openrouter_config.openrouter_headers:
            client_kwargs['default_headers'] = self.openrouter_config.openrouter_headers
            print(f"  OpenRouter headers: {list(self.openrouter_config.openrouter_headers.keys())}")

        # Allow custom base URL override
        if 'base_url' in self.extra_config:
            client_kwargs['base_url'] = self.extra_config['base_url']

        # Add custom headers if needed (merge with OpenRouter headers)
        if 'default_headers' in self.extra_config:
            if 'default_headers' in client_kwargs:
                client_kwargs['default_headers'].update(self.extra_config['default_headers'])
            else:
                client_kwargs['default_headers'] = self.extra_config['default_headers']

        self.client = OpenAI(**client_kwargs)
        self.async_client = AsyncOpenAI(**client_kwargs)

        # Initialize unified tool manager (uses OpenAI-compatible format)
        self.tool_manager = OpenRouterToolManager()

    # ========== CORE API METHODS ==========

    async def call_api_with_context(
        self,
        context_contents: List[Dict[str, Any]],
        api_config: Dict[str, Any],
        **kwargs
    ) -> ChatCompletion:
        """
        Execute a stateless OpenRouter API call with prepared context.

        Uses standard OpenAI Chat Completions API format.

        Args:
            context_contents: Conversation messages in OpenAI format.
            api_config: Provider configuration including tools and system prompt.
            **kwargs: Optional overrides (temperature, max_tokens, top_p).

        Returns:
            ChatCompletion object from OpenAI-compatible API.
        """
        debug = self.openrouter_config.debug

        tools = api_config.get("tools", []) or []

        # Build messages (OpenRouter uses standard OpenAI format)
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
            "model": self.openrouter_config.model_settings.model,
            "messages": messages,
            "temperature": self.openrouter_config.model_settings.temperature,
            "top_p": self.openrouter_config.model_settings.top_p,
        }

        if self.openrouter_config.model_settings.max_tokens:
            api_kwargs["max_tokens"] = self.openrouter_config.model_settings.max_tokens

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
            OpenRouterDebugger.print_api_request(api_kwargs, messages, tools)

        try:
            response = await self.async_client.chat.completions.create(**api_kwargs)

            if debug:
                print(f"[DEBUG] OpenRouter response received:")
                print(f"[DEBUG] Finish reason: {response.choices[0].finish_reason}")
                if response.usage:
                    print(f"[DEBUG] Token usage: {response.usage}")

            return response
        except Exception as exc:
            if debug:
                print(f"[DEBUG] OpenRouter API call failed: {exc}")
            raise

    async def call_api_with_context_streaming(
        self,
        context_contents: List[Dict[str, Any]],
        api_config: Dict[str, Any],
        **kwargs
    ) -> AsyncGenerator[StreamingChunk, None]:
        """
        Execute streaming OpenRouter API call with real-time chunk delivery.

        Args:
            context_contents: Conversation messages in OpenAI format.
            api_config: Provider configuration including tools and system prompt.
            **kwargs: Optional overrides.

        Yields:
            StreamingChunk: Standardized streaming data chunks.
        """
        debug = self.openrouter_config.debug

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
            "model": self.openrouter_config.model_settings.model,
            "messages": messages,
            "temperature": self.openrouter_config.model_settings.temperature,
            "top_p": self.openrouter_config.model_settings.top_p,
            "stream": True,  # Enable streaming
            "stream_options": {"include_usage": True},  # Request detailed usage metadata in stream
        }

        if self.openrouter_config.model_settings.max_tokens:
            api_kwargs["max_tokens"] = self.openrouter_config.model_settings.max_tokens

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
            OpenRouterDebugger.print_api_request(api_kwargs, messages, tools)

        try:
            stream = await self.async_client.chat.completions.create(**api_kwargs)

            # Create stateful streaming processor
            streaming_processor = self._get_response_processor().create_streaming_processor()

            async for chunk in stream:
                # Delegate chunk processing to streaming processor
                processed_chunks = streaming_processor.process_event(chunk)
                for processed_chunk in processed_chunks:
                    yield processed_chunk

        except Exception as e:
            raise e

    def get_or_create_context_manager(self, session_id: str):
        """
        Get or create a context manager for a specific session.

        Args:
            session_id: Unique session identifier

        Returns:
            OpenRouterContextManager instance for this session
        """
        if session_id not in self._session_context_managers:
            self._session_context_managers[session_id] = OpenRouterContextManager(session_id=session_id)
        return self._session_context_managers[session_id]

    # ========== ABSTRACT METHOD IMPLEMENTATIONS ==========

    def _get_response_processor(self):
        """Get OpenRouter-specific response processor instance."""
        from .response_processor import OpenRouterResponseProcessor
        return OpenRouterResponseProcessor()

    def _get_context_manager_class(self):
        """Get OpenRouter-specific context manager class."""
        return OpenRouterContextManager

    def _get_provider_config(self):
        """Get OpenRouter-specific configuration object."""
        return self.openrouter_config

    def _build_api_config(
        self,
        system_prompt: str,
        tool_schemas: Optional[List[Any]]
    ) -> Dict[str, Any]:
        """
        Build OpenRouter-specific API configuration.

        Args:
            system_prompt: Pre-built system prompt
            tool_schemas: Tool schemas in OpenRouter format

        Returns:
            Dict with 'tools' and 'system_prompt' keys
        """
        return {
            'tools': tool_schemas or [],
            'system_prompt': system_prompt
        }

    # _construct_response_from_streaming_chunks is now handled by ResponseProcessor
