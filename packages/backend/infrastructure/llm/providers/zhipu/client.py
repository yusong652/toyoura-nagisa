"""
Zhipu (智谱) client implementation using official zai SDK.

This implementation uses the zai-sdk which provides access to Zhipu GLM models.
Since zai SDK is synchronous, we use asyncio.to_thread() for async compatibility.
"""

import asyncio
from typing import List, Dict, Any, AsyncGenerator, cast
from zai import ZhipuAiClient
from zai.types.chat import Completion

from backend.infrastructure.llm.base.client import LLMClientBase
from backend.domain.models.streaming import StreamingChunk

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
    ) -> Completion:
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

        # Enable thinking mode by default (GLM thinking models)
        # Users can disable by passing enable_thinking=False
        if kwargs.get('enable_thinking', True):
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
            # Cast to Completion since stream=False guarantees this type
            response = cast(
                Completion,
                await asyncio.to_thread(
                    self.client.chat.completions.create,
                    **api_kwargs
                )
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
            # Note: Zhipu's zai SDK automatically includes usage in final chunk, no stream_options needed
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
            # Type: StreamResponse[ChatCompletionChunk] when stream=True
            # zai SDK is synchronous, we need to iterate in a thread to avoid blocking
            stream = await asyncio.to_thread(
                self.client.chat.completions.create,
                **api_kwargs
            )  # type: Any  # StreamResponse not publicly exported by zai SDK

            # Create stateful streaming processor
            streaming_processor = self._get_response_processor().create_streaming_processor()

            # Convert synchronous stream iterator to async
            # zai SDK returns a sync iterator, we need to iterate in executor
            # to avoid blocking the event loop
            loop = asyncio.get_event_loop()

            # Create iterator from stream
            stream_iter = iter(stream)

            # Helper function to get next chunk (will run in thread pool)
            def get_next_chunk():
                try:
                    return next(stream_iter), False  # (chunk, is_done)
                except StopIteration:
                    return None, True  # (None, is_done)

            # Iterate through chunks asynchronously
            while True:
                # Run next() in thread pool to avoid blocking
                chunk, is_done = await loop.run_in_executor(None, get_next_chunk)

                if is_done or chunk is None:
                    break

                # Delegate chunk processing to streaming processor
                processed_chunks = streaming_processor.process_event(chunk)
                for processed_chunk in processed_chunks:
                    yield processed_chunk

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

    def _build_api_config(
        self,
        system_prompt: str,
        tool_schemas: Optional[List[Any]]
    ) -> Dict[str, Any]:
        """
        Build Zhipu-specific API configuration.

        Args:
            system_prompt: Pre-built system prompt
            tool_schemas: Tool schemas in Zhipu format

        Returns:
            Dict with 'tools' and 'system_prompt' keys
        """
        return {
            'tools': tool_schemas or [],
            'system_prompt': system_prompt
        }

    # _construct_response_from_streaming_chunks is now handled by ResponseProcessor


__all__ = ['ZhipuClient']
