"""
Moonshot (Moonshot) client implementation using OpenAI-compatible API.

This implementation uses the standard OpenAI Chat Completions API format
since Moonshot/Moonshot provides full OpenAI compatibility.

Base URL: https://api.moonshot.ai/v1
"""

from typing import List, Optional, Dict, Any, AsyncGenerator, cast
from openai import OpenAI, AsyncOpenAI
from openai.types.chat import ChatCompletion

from backend.infrastructure.llm.base.client import LLMClientBase
from backend.infrastructure.llm.base.call_options import parse_call_options
from backend.infrastructure.llm.base.retry import run_with_retries, stream_with_retries
from backend.domain.models.streaming import StreamingChunk

# Import Moonshot-specific implementations
from .config import get_moonshot_client_config
from .message_formatter import MoonshotMessageFormatter
from .tool_manager import MoonshotToolManager
from .context_manager import MoonshotContextManager
from .debug import MoonshotDebugger
from .response_processor import MoonshotResponseProcessor


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
        """
        super().__init__(**kwargs)
        self.provider_name = "moonshot"
        self.api_key = api_key

        # Initialize Moonshot-specific configuration
        config_overrides = {}
        if 'model' in self.extra_config:
            config_overrides['model'] = self.extra_config['model']
        if 'debug' in self.extra_config:
            config_overrides['debug'] = self.extra_config['debug']

        self.moonshot_config = get_moonshot_client_config(**config_overrides)

        # Log initialization
        print(f"Moonshot Client initialized")
        print(f"  Model: {self.moonshot_config.model}")
        print(f"  Base URL: {self.moonshot_config.base_url}")

        # Debug: Print masked API key
        if self.api_key:
            masked_key = f"{self.api_key[:8]}...{self.api_key[-4:]}" if len(self.api_key) > 12 else "***"
            print(f"  API Key (masked): {masked_key}")

        # Initialize both sync and async OpenAI clients with Moonshot base URL
        client_kwargs: Dict[str, Any] = {
            "api_key": self.api_key,
            "base_url": self.moonshot_config.base_url
        }

        # Allow custom base URL override from extra_config
        if 'base_url' in self.extra_config:
            client_kwargs['base_url'] = self.extra_config['base_url']

        self.client = OpenAI(**client_kwargs)
        self.async_client = AsyncOpenAI(**client_kwargs)

        # Initialize unified tool manager
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

        Args:
            context_contents: Conversation messages in OpenAI format.
            api_config: Provider configuration including tools and system prompt.
            **kwargs: Optional overrides (temperature, max_tokens, top_p).

        Returns:
            ChatCompletion object from OpenAI-compatible API.
        """
        call_options = parse_call_options(kwargs)
        debug = self.moonshot_config.debug
        timeout = call_options.timeout if call_options.timeout is not None else self.moonshot_config.timeout
        max_retries = (
            call_options.max_retries
            if call_options.max_retries is not None
            else self.moonshot_config.max_retries
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
        api_kwargs = self.moonshot_config.get_api_call_kwargs(
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

        # Handle thinking mode (K2.5 and similar models)
        if call_options.enable_thinking is not None:
            thinking_type = "enabled" if call_options.enable_thinking else "disabled"
            api_kwargs["extra_body"] = {"thinking": {"type": thinking_type}}

        if debug:
            MoonshotDebugger.print_api_request(api_kwargs, messages, tools)

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
        call_options = parse_call_options(kwargs)
        debug = self.moonshot_config.debug
        timeout = call_options.timeout if call_options.timeout is not None else self.moonshot_config.timeout
        max_retries = (
            call_options.max_retries
            if call_options.max_retries is not None
            else self.moonshot_config.max_retries
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
        api_kwargs = self.moonshot_config.get_api_call_kwargs(
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

        # Handle thinking mode (K2.5 and similar models)
        if call_options.enable_thinking is not None:
            thinking_type = "enabled" if call_options.enable_thinking else "disabled"
            api_kwargs["extra_body"] = {"thinking": {"type": thinking_type}}

        if debug:
            MoonshotDebugger.print_api_request(api_kwargs, messages, tools)

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
            MoonshotContextManager instance for this session
        """
        if session_id not in self._session_context_managers:
            self._session_context_managers[session_id] = MoonshotContextManager(session_id=session_id)
        return self._session_context_managers[session_id]

    # ========== ABSTRACT METHOD IMPLEMENTATIONS ==========

    def _get_response_processor(self):
        """Get Moonshot-specific response processor instance."""
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
