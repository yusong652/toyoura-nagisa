"""
Moonshot (Moonshot) client implementation using OpenAI-compatible API.

This implementation uses the standard OpenAI Chat Completions API format
since Moonshot/Moonshot provides full OpenAI compatibility.

Base URL: https://api.moonshot.ai/v1
"""

import json
import time
from typing import List, Optional, Dict, Any, AsyncGenerator, Type
from openai import OpenAI, AsyncOpenAI
from openai.types.chat import ChatCompletion, ChatCompletionChunk

from backend.infrastructure.llm.base.client import LLMClientBase
from backend.domain.models.messages import BaseMessage
from backend.domain.models.streaming import StreamingChunk
from backend.infrastructure.llm.base.context_manager import BaseContextManager

# Import Moonshot-specific implementations (aliases for OpenAI components)
from .config import get_moonshot_client_config
from .message_formatter import MoonshotMessageFormatter
from .tool_manager import MoonshotToolManager
from .context_manager import MoonshotContextManager
from .debug import MoonshotDebugger


class MoonshotClient(LLMClientBase):
    """
    Moonshot (Moonshot) client implementation using OpenAI-compatible API.

    Key Features:
    - OpenAI-compatible Chat Completions API
    - Long-context support (up to 200K tokens)
    - Full streaming support with tool calling
    - Real-time tool execution notifications

    Moonshot specializes in:
    - Long document understanding and analysis
    - Multi-turn conversations with extensive context
    - Chinese language processing
    """

    def __init__(self, api_key: str, **kwargs):
        """
        Initialize Moonshot client with OpenAI-compatible setup.

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

        # Initialize Moonshot-specific configuration
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

        self.moonshot_config = get_moonshot_client_config(**config_overrides)

        # Initialize both sync and async OpenAI clients with Moonshot base URL
        client_kwargs: Dict[str, Any] = {
            "api_key": self.api_key,
            "base_url": self.moonshot_config.base_url
        }

        # Allow custom base URL override
        if 'base_url' in self.extra_config:
            client_kwargs['base_url'] = self.extra_config['base_url']

        # Add custom headers if needed
        if 'default_headers' in self.extra_config:
            client_kwargs['default_headers'] = self.extra_config['default_headers']

        self.client = OpenAI(**client_kwargs)
        self.async_client = AsyncOpenAI(**client_kwargs)

        # Initialize unified tool manager (uses OpenAI-compatible format)
        self.tool_manager = MoonshotToolManager()

    # ========== CORE API METHODS ==========

    async def call_api_with_context(
        self,
        context_contents: List[Dict[str, Any]],
        api_config: Dict[str, Any],
        **kwargs
    ) -> ChatCompletion:
        """
        Execute a stateless Moonshot API call with prepared context.

        Uses standard OpenAI Chat Completions API format.

        Args:
            context_contents: Conversation messages in OpenAI format.
            api_config: Provider configuration including tools and system prompt.
            **kwargs: Optional overrides (temperature, max_tokens, top_p).

        Returns:
            ChatCompletion object from OpenAI-compatible API.
        """
        debug = self.moonshot_config.debug

        tools = api_config.get("tools", []) or []

        # Build messages (Moonshot uses standard OpenAI format)
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
            "model": self.moonshot_config.model_settings.model,
            "messages": messages,
            "temperature": self.moonshot_config.model_settings.temperature,
            "top_p": self.moonshot_config.model_settings.top_p,
        }

        if self.moonshot_config.model_settings.max_tokens:
            api_kwargs["max_tokens"] = self.moonshot_config.model_settings.max_tokens

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
            MoonshotDebugger.print_api_request(api_kwargs, messages, tools)

        try:
            response = await self.async_client.chat.completions.create(**api_kwargs)
            return response
        except Exception as exc:
            if debug:
                print(f"[DEBUG] Moonshot API call failed: {exc}")
            raise

    async def call_api_with_context_streaming(
        self,
        context_contents: List[Dict[str, Any]],
        api_config: Dict[str, Any],
        **kwargs
    ) -> AsyncGenerator[StreamingChunk, None]:
        """
        Execute streaming Moonshot API call with real-time chunk delivery.

        Args:
            context_contents: Conversation messages in OpenAI format.
            api_config: Provider configuration including tools and system prompt.
            **kwargs: Optional overrides.

        Yields:
            StreamingChunk: Standardized streaming data chunks.
        """
        debug = self.moonshot_config.debug

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
            "model": self.moonshot_config.model_settings.model,
            "messages": messages,
            "temperature": self.moonshot_config.model_settings.temperature,
            "top_p": self.moonshot_config.model_settings.top_p,
            "stream": True,  # Enable streaming
            "stream_options": {"include_usage": True},  # Request usage metadata in stream
        }

        if self.moonshot_config.model_settings.max_tokens:
            api_kwargs["max_tokens"] = self.moonshot_config.model_settings.max_tokens

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
            MoonshotDebugger.print_api_request(api_kwargs, messages, tools)

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
            MoonshotContextManager instance for this session
        """
        if session_id not in self._session_context_managers:
            self._session_context_managers[session_id] = MoonshotContextManager(session_id=session_id)
        return self._session_context_managers[session_id]

    # ========== ABSTRACT METHOD IMPLEMENTATIONS ==========

    def _get_response_processor(self):
        """Get Moonshot-specific response processor instance."""
        from .response_processor import MoonshotResponseProcessor
        return MoonshotResponseProcessor()

    def _get_context_manager_class(self):
        """Get Moonshot-specific context manager class."""
        return MoonshotContextManager

    def _get_provider_config(self):
        """Get Moonshot-specific configuration object."""
        return self.moonshot_config

    def _build_api_config(
        self,
        system_prompt: str,
        tool_schemas: Optional[List[Any]]
    ) -> Dict[str, Any]:
        """
        Build Moonshot-specific API configuration.

        Args:
            system_prompt: Pre-built system prompt
            tool_schemas: Tool schemas in Moonshot format

        Returns:
            Dict with 'tools' and 'system_prompt' keys
        """
        return {
            'tools': tool_schemas or [],
            'system_prompt': system_prompt
        }

    # _construct_response_from_streaming_chunks is now handled by ResponseProcessor
