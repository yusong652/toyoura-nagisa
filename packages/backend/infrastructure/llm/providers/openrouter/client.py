"""
OpenRouter client implementation using OpenAI-compatible API.

This implementation uses the standard OpenAI Chat Completions API format
since OpenRouter provides full OpenAI compatibility.

Base URL: https://openrouter.ai/api/v1
"""

from typing import List, Optional, Dict, Any, AsyncGenerator, cast
from openai import OpenAI, AsyncOpenAI
from openai.types.chat import ChatCompletion

from backend.infrastructure.llm.base.client import LLMClientBase
from backend.infrastructure.llm.base.call_options import parse_call_options
from backend.infrastructure.llm.base.retry import run_with_retries, stream_with_retries
from backend.domain.models.streaming import StreamingChunk

# Import OpenRouter-specific implementations
from .config import get_openrouter_client_config
from .message_formatter import OpenRouterMessageFormatter
from .tool_manager import OpenRouterToolManager
from .context_manager import OpenRouterContextManager
from .debug import OpenRouterDebugger
from .response_processor import OpenRouterResponseProcessor


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
        """
        super().__init__(**kwargs)
        self.provider_name = "openrouter"
        self.api_key = api_key

        # Initialize OpenRouter-specific configuration
        config_overrides = {}
        if 'model' in self.extra_config:
            config_overrides['model'] = self.extra_config['model']
        if 'debug' in self.extra_config:
            config_overrides['debug'] = self.extra_config['debug']

        self.openrouter_config = get_openrouter_client_config(**config_overrides)

        # Log initialization
        print(f"OpenRouter Client initialized")
        print(f"  Model: {self.openrouter_config.model}")
        print(f"  Base URL: {self.openrouter_config.base_url}")

        # Debug: Print masked API key
        if self.api_key:
            masked_key = f"{self.api_key[:8]}...{self.api_key[-4:]}" if len(self.api_key) > 12 else "***"
            print(f"  API Key (masked): {masked_key}")

        # Initialize both sync and async OpenAI clients with OpenRouter base URL
        client_kwargs: Dict[str, Any] = {
            "api_key": self.api_key,
            "base_url": self.openrouter_config.base_url
        }

        # Allow custom base URL override from extra_config
        if 'base_url' in self.extra_config:
            client_kwargs['base_url'] = self.extra_config['base_url']

        # Add custom headers if needed (common for OpenRouter)
        if 'default_headers' in self.extra_config:
            client_kwargs['default_headers'] = self.extra_config['default_headers']

        self.client = OpenAI(**client_kwargs)
        self.async_client = AsyncOpenAI(**client_kwargs)

        # Initialize unified tool manager
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

        Args:
            context_contents: Conversation messages in OpenAI format.
            api_config: Provider configuration including tools and system prompt.
            **kwargs: Optional overrides (temperature, max_tokens, top_p).

        Returns:
            ChatCompletion object from OpenAI-compatible API.
        """
        call_options = parse_call_options(kwargs)
        debug = self.openrouter_config.debug
        timeout = call_options.timeout if call_options.timeout is not None else self.openrouter_config.timeout
        max_retries = (
            call_options.max_retries
            if call_options.max_retries is not None
            else self.openrouter_config.max_retries
        )

        tools = api_config.get("tools", []) or []
        messages = context_contents.copy()

        # Add system message if provided
        system_prompt = api_config.get("system_prompt")
        if system_prompt:
            messages.insert(0, {
                "role": "system",
                "content": system_prompt
            })

        # Build API call parameters
        api_kwargs = self.openrouter_config.get_api_call_kwargs(
            messages=messages,
            tools=tools,
            stream=False,
        )

        if call_options.temperature is not None:
            api_kwargs['temperature'] = call_options.temperature
        if call_options.max_tokens is not None:
            api_kwargs['max_tokens'] = call_options.max_tokens
        if call_options.top_p is not None:
            api_kwargs['top_p'] = call_options.top_p
        if call_options.timeout is not None:
            api_kwargs['timeout'] = call_options.timeout

        if debug:
            OpenRouterDebugger.print_api_request(api_kwargs, messages, tools)

        async def _call_api():
            return await self.async_client.chat.completions.create(**api_kwargs)

        try:
            return await run_with_retries(
                _call_api,
                max_retries=max_retries,
                timeout=timeout,
                debug=debug,
            )
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
        call_options = parse_call_options(kwargs)
        debug = self.openrouter_config.debug
        timeout = call_options.timeout if call_options.timeout is not None else self.openrouter_config.timeout
        max_retries = (
            call_options.max_retries
            if call_options.max_retries is not None
            else self.openrouter_config.max_retries
        )

        tools = api_config.get("tools", []) or []
        messages = context_contents.copy()

        # Add system message if provided
        system_prompt = api_config.get("system_prompt")
        if system_prompt:
            messages.insert(0, {
                "role": "system",
                "content": system_prompt
            })

        # Build API call parameters
        api_kwargs = self.openrouter_config.get_api_call_kwargs(
            messages=messages,
            tools=tools,
            stream=True,
        )
        api_kwargs["stream_options"] = {"include_usage": True}

        if call_options.temperature is not None:
            api_kwargs['temperature'] = call_options.temperature
        if call_options.max_tokens is not None:
            api_kwargs['max_tokens'] = call_options.max_tokens
        if call_options.top_p is not None:
            api_kwargs['top_p'] = call_options.top_p
        if call_options.timeout is not None:
            api_kwargs['timeout'] = call_options.timeout

        if debug:
            OpenRouterDebugger.print_api_request(api_kwargs, messages, tools)

        async def _stream_once():
            stream = await self.async_client.chat.completions.create(**api_kwargs)

            # Create stateful streaming processor
            streaming_processor = self._get_response_processor().create_streaming_processor()

            async for chunk in stream:
                # Delegate chunk processing to streaming processor
                processed_chunks = streaming_processor.process_event(chunk)
                for processed_chunk in processed_chunks:
                    yield processed_chunk

        async for chunk in stream_with_retries(
            _stream_once,
            max_retries=max_retries,
            timeout=timeout,
            debug=debug,
        ):
            yield chunk

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
