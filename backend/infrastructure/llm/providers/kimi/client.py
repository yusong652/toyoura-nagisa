"""
Kimi (Moonshot) client implementation using OpenAI-compatible API.

This implementation uses the standard OpenAI Chat Completions API format
since Kimi/Moonshot provides full OpenAI compatibility.

Base URL: https://api.moonshot.cn/v1
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

# Import Kimi-specific implementations (aliases for OpenAI components)
from .config import get_kimi_client_config
from .message_formatter import KimiMessageFormatter
from .tool_manager import KimiToolManager
from .context_manager import KimiContextManager
from .debug import KimiDebugger


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

        # Log initialization
        print(f"Kimi Client initialized")
        print(f"  Model: {self.kimi_config.model_settings.model}")
        print(f"  Base URL: {self.kimi_config.base_url}")
        print(f"  Using OpenRouter: {self.kimi_config.use_openrouter}")

        # Debug: Print masked API key to verify it's passed correctly
        if self.api_key:
            masked_key = f"{self.api_key[:8]}...{self.api_key[-4:]}" if len(self.api_key) > 12 else "***"
            print(f"  API Key (masked): {masked_key}")

        # Initialize both sync and async OpenAI clients with Kimi base URL
        client_kwargs: Dict[str, Any] = {
            "api_key": self.api_key,
            "base_url": self.kimi_config.base_url
        }

        # Add OpenRouter headers if using OpenRouter
        if self.kimi_config.use_openrouter and self.kimi_config.openrouter_headers:
            client_kwargs['default_headers'] = self.kimi_config.openrouter_headers
            print(f"  OpenRouter headers: {list(self.kimi_config.openrouter_headers.keys())}")

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
        self.tool_manager = KimiToolManager()

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
            KimiDebugger.print_api_request(api_kwargs, messages, tools)

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
            KimiDebugger.print_api_request(api_kwargs, messages, tools)

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
            KimiContextManager instance for this session
        """
        if session_id not in self._session_context_managers:
            self._session_context_managers[session_id] = KimiContextManager(session_id=session_id)
        return self._session_context_managers[session_id]

    # ========== ABSTRACT METHOD IMPLEMENTATIONS ==========

    def _get_response_processor(self):
        """Get Kimi-specific response processor instance."""
        from .response_processor import KimiResponseProcessor
        return KimiResponseProcessor()

    def _get_context_manager_class(self):
        """Get Kimi-specific context manager class."""
        return KimiContextManager

    def _get_provider_config(self):
        """Get Kimi-specific configuration object."""
        return self.kimi_config

    async def _prepare_complete_context(
        self,
        session_id: str
    ) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Prepare complete context and API configuration for stateless Kimi API call.

        This method consolidates all context preparation logic for Kimi
        and returns all necessary configuration for thread-safe API calls.

        Args:
            session_id: Session identifier

        Returns:
            Tuple containing:
            - context_contents: Messages for Kimi API (without system prompt)
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

    # _construct_response_from_streaming_chunks is now handled by ResponseProcessor
