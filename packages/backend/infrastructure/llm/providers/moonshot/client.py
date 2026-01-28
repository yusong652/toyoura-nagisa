"""
Moonshot client implementation using OpenAI-compatible architecture.

This implementation provides integration with Moonshot's Kimi models
using standard OpenAI-compatible Chat Completions API.
"""

import json
from typing import List, Optional, Dict, Any, AsyncGenerator
from openai import OpenAI, AsyncOpenAI
from openai.types.chat import ChatCompletion

from backend.infrastructure.llm.base.client import LLMClientBase
from backend.infrastructure.llm.base.call_options import parse_call_options
from backend.infrastructure.llm.base.retry import run_with_retries, stream_with_retries
from backend.domain.models.streaming import StreamingChunk
from backend.config.dev import get_dev_config

# Import Moonshot-specific implementations
from .config import MoonshotConfig
from .message_formatter import MoonshotMessageFormatter
from .context_manager import MoonshotContextManager
from .tool_manager import MoonshotToolManager
from .response_processor import MoonshotResponseProcessor
from .debug import MoonshotDebugger


class MoonshotClient(LLMClientBase):
    """
    Moonshot client implementation using OpenAI-compatible architecture.
    
    Key Features:
    - OpenAI-compatible Chat Completions API
    - Optimized for Kimi models
    - Full streaming support with tool calling
    - Real-time tool execution notifications
    """

    def __init__(self, config: MoonshotConfig, extra_config: Optional[Dict[str, Any]] = None, **kwargs):
        """
        Initialize Moonshot client with OpenAI-compatible setup.

        Args:
            config: Moonshot specific configuration
            extra_config: Additional configuration parameters
            **kwargs: Catch-all for extra arguments from factory
        """
        super().__init__(extra_config=extra_config)
        self.provider_name = "moonshot"
        self.moonshot_config = config
        self.api_key = config.moonshot_api_key
        
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
            OpenAI ChatCompletion object.
        """
        call_options = parse_call_options(kwargs)
        debug = get_dev_config().debug_mode
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
        api_kwargs = self.moonshot_config.build_api_params()
        api_kwargs.update({
            "messages": messages,
            "tools": tools,
            "tool_choice": "auto" if tools else None,
            "stream": False,
        })

        if call_options.temperature is not None:
            api_kwargs['temperature'] = call_options.temperature
        if call_options.max_tokens is not None:
            api_kwargs['max_tokens'] = call_options.max_tokens
        if call_options.top_p is not None:
            api_kwargs['top_p'] = call_options.top_p
        if call_options.timeout is not None:
            api_kwargs['timeout'] = call_options.timeout

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
        debug = get_dev_config().debug_mode
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
        api_kwargs = self.moonshot_config.build_api_params()
        api_kwargs.update({
            "messages": messages,
            "tools": tools,
            "tool_choice": "auto" if tools else None,
            "stream": True,
            "stream_options": {"include_usage": True}
        })

        if call_options.temperature is not None:
            api_kwargs['temperature'] = call_options.temperature
        if call_options.max_tokens is not None:
            api_kwargs['max_tokens'] = call_options.max_tokens
        if call_options.top_p is not None:
            api_kwargs['top_p'] = call_options.top_p
        if call_options.timeout is not None:
            api_kwargs['timeout'] = call_options.timeout

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
            tool_schemas: Tool schemas in OpenAI format

        Returns:
            Dict with 'tools' and 'system_prompt' keys
        """
        return {
            'tools': tool_schemas or [],
            'system_prompt': system_prompt
        }


__all__ = ['MoonshotClient']
