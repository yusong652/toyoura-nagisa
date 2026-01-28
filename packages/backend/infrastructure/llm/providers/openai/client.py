"""
OpenAI client implementation using unified architecture.

This implementation inherits from the base LLMClientBase and provides
full OpenAI GPT integration with streaming, tool calling, and content generation.
"""

import json
import time
from typing import List, Optional, Dict, Any, AsyncGenerator
from openai import OpenAI, AsyncOpenAI
from openai.types.responses import (
    Response,
    ResponseFunctionToolCall,
    ResponseCompletedEvent,
    ResponseFunctionCallArgumentsDeltaEvent,
    ResponseFunctionCallArgumentsDoneEvent,
    ResponseOutputItemAddedEvent,
    ResponseReasoningTextDeltaEvent,
    ResponseReasoningSummaryPartAddedEvent,
    ResponseReasoningSummaryTextDeltaEvent,
    ResponseTextDeltaEvent,
    ResponseOutputMessage,
    ResponseOutputText,
    ResponseReasoningItem,
)
from backend.infrastructure.llm.base.client import LLMClientBase
from backend.infrastructure.llm.base.call_options import parse_call_options
from backend.infrastructure.llm.base.retry import run_with_retries, stream_with_retries
from backend.domain.models.messages import BaseMessage
from backend.domain.models.streaming import StreamingChunk
from backend.config.dev import get_dev_config

# Import OpenAI-specific implementations
from .config import OpenAIConfig
from .message_formatter import OpenAIMessageFormatter
from .context_manager import OpenAIContextManager
from .debug import OpenAIDebugger
from .response_processor import OpenAIResponseProcessor
from .tool_manager import OpenAIToolManager

# Import unified thinking level mappings
from backend.infrastructure.llm.shared.constants.thinking import OPENAI_THINKING_LEVEL_TO_EFFORT


class OpenAIClient(LLMClientBase):
    """
    OpenAI GPT client implementation using unified architecture.
    
    Key Features:
    - Inherits from unified LLMClientBase
    - Full streaming support with tool calling
    - Real-time tool execution notifications
    - Content generation capabilities
    - Comprehensive error handling
    """
    
    def __init__(self, config: OpenAIConfig, extra_config: Optional[Dict[str, Any]] = None, **kwargs):
        """
        Initialize OpenAI client.
        
        Args:
            config: OpenAI specific configuration
            extra_config: Additional configuration parameters
            **kwargs: Catch-all for extra arguments from factory
        """
        super().__init__(extra_config=extra_config)
        self.provider_name = "openai"
        self.openai_config = config
        self.api_key = config.openai_api_key
        
        # Initialize both sync and async API clients
        client_kwargs: Dict[str, Any] = {"api_key": self.api_key}
        base_url = self.extra_config.get("base_url")
        default_headers = self.extra_config.get("default_headers")

        if base_url:
            client_kwargs["base_url"] = base_url
        if default_headers:
            client_kwargs["default_headers"] = default_headers

        self.client = OpenAI(**client_kwargs)
        self.async_client = AsyncOpenAI(**client_kwargs)
        
        # Initialize unified tool manager
        self.tool_manager = OpenAIToolManager()

    # ========== CORE API METHODS ==========


    async def call_api_with_context(
        self,
        context_contents: List[Dict[str, Any]],
        api_config: Dict[str, Any],
        **kwargs
    ) -> Response:
        """
        Execute a stateless OpenAI Responses API call with prepared context.

        Args:
            context_contents: Conversation messages in provider-neutral format.
            api_config: Provider configuration including tools and instructions.
            **kwargs: Optional overrides (temperature, max_tokens, top_p).

        Returns:
            OpenAI Responses API `Response` object.
        """
        call_options = parse_call_options(kwargs)
        debug = get_dev_config().debug_mode
        timeout = call_options.timeout if call_options.timeout is not None else self.openai_config.timeout
        max_retries = (
            call_options.max_retries
            if call_options.max_retries is not None
            else self.openai_config.max_retries
        )

        tools = api_config.get("tools", []) or []
        instructions = api_config.get("instructions")

        # context_contents is already in Responses API input format from context_manager
        input_items = context_contents

        kwargs_api = self.openai_config.build_api_params()
        kwargs_api.update({
            "instructions": instructions,
            "input": input_items,
            "tools": tools,
            "tool_choice": "auto" if tools else None
        })

        # Apply call options overrides
        if call_options.temperature is not None:
            kwargs_api['temperature'] = call_options.temperature
        if call_options.max_tokens is not None:
            kwargs_api['max_output_tokens'] = call_options.max_tokens
        if call_options.top_p is not None:
            kwargs_api['top_p'] = call_options.top_p
        if call_options.timeout is not None:
            kwargs_api['timeout'] = call_options.timeout

        # Handle thinking mode (reasoning effort for reasoning models)
        if call_options.thinking_level is not None:
            effort = OPENAI_THINKING_LEVEL_TO_EFFORT.get(call_options.thinking_level)
            if effort is not None:
                kwargs_api["reasoning"] = {"effort": effort}

        if debug:
            OpenAIDebugger.log_api_call_info(
                tools_count=len(tools),
                model=self.openai_config.model
            )
            OpenAIDebugger.print_debug_request_payload(kwargs_api)

        async def _call_api():
            return await self.async_client.responses.create(**kwargs_api)

        try:
            response = await run_with_retries(
                _call_api,
                max_retries=max_retries,
                timeout=timeout,
                debug=debug,
            )

            if debug:
                OpenAIDebugger.log_raw_response(response)

            return response
        except Exception:
            if debug:
                OpenAIDebugger.print_debug_request_payload(kwargs_api)
            raise

    # ========== CORE STREAMING INTERFACE ==========

    # get_response is now implemented in base class using provider-specific components

    # ========== PROVIDER-SPECIFIC METHODS FOR BASE IMPLEMENTATION ==========


    def _get_response_processor(self):
        """Get OpenAI-specific response processor instance."""
        return OpenAIResponseProcessor()

    def _get_context_manager_class(self):
        """Get OpenAI-specific context manager class."""
        return OpenAIContextManager

    def _build_api_config(
        self,
        system_prompt: str,
        tool_schemas: Optional[List[Any]]
    ) -> Dict[str, Any]:
        """
        Build OpenAI-specific API configuration.

        Args:
            system_prompt: Pre-built system prompt
            tool_schemas: Tool schemas in OpenAI format

        Returns:
            Dict with 'tools' and 'instructions' keys
        """
        return {
            'tools': tool_schemas or [],
            'instructions': system_prompt
        }

    def _get_provider_config(self):
        """Get OpenAI-specific configuration object."""
        return self.openai_config

    async def call_api_with_context_streaming(
        self,
        context_contents: List[Dict[str, Any]],
        api_config: Dict[str, Any],
        **kwargs
    ) -> AsyncGenerator[StreamingChunk, None]:
        """
        Execute streaming Responses API call and yield standardized chunks.
        """
        call_options = parse_call_options(kwargs)
        debug = get_dev_config().debug_mode
        timeout = call_options.timeout if call_options.timeout is not None else self.openai_config.timeout
        max_retries = (
            call_options.max_retries
            if call_options.max_retries is not None
            else self.openai_config.max_retries
        )

        tools = api_config.get("tools", []) or []
        instructions = api_config.get("instructions")

        # context_contents is already in Responses API input format from context_manager
        input_items = context_contents

        kwargs_api = self.openai_config.build_api_params()
        kwargs_api.update({
            "instructions": instructions,
            "input": input_items,
            "tools": tools,
            "tool_choice": "auto" if tools else None,
        })

        # Apply call options overrides
        if call_options.temperature is not None:
            kwargs_api['temperature'] = call_options.temperature
        if call_options.max_tokens is not None:
            kwargs_api['max_output_tokens'] = call_options.max_tokens
        if call_options.top_p is not None:
            kwargs_api['top_p'] = call_options.top_p
        if call_options.timeout is not None:
            kwargs_api['timeout'] = call_options.timeout

        # Handle thinking mode (reasoning effort for reasoning models)
        if call_options.thinking_level is not None:
            effort = OPENAI_THINKING_LEVEL_TO_EFFORT.get(call_options.thinking_level)
            if effort is not None:
                kwargs_api["reasoning"] = {"effort": effort}

        if debug:
            OpenAIDebugger.log_api_call_info(
                tools_count=len(tools),
                model=self.openai_config.model
            )
            OpenAIDebugger.print_debug_request_payload(kwargs_api)

        async def _stream_once():
            final_response: Optional[Response] = None

            try:
                # Create stateful streaming processor
                streaming_processor = self._get_response_processor().create_streaming_processor()

                async with self.async_client.responses.stream(**kwargs_api) as stream:
                    async for event in stream:
                        # Delegate event processing to streaming processor
                        processed_chunks = streaming_processor.process_event(event)
                        for chunk in processed_chunks:
                            yield chunk

                        # Capture final response metadata
                        if isinstance(event, ResponseCompletedEvent):
                            final_response = event.response

            except Exception:
                if debug:
                    OpenAIDebugger.print_debug_request_payload(kwargs_api)
                raise

            if final_response:
                # Extract usage metadata from final response
                final_metadata: Dict[str, Any] = {"__openai_final_response": final_response}

                if hasattr(final_response, 'usage') and final_response.usage:
                    usage = final_response.usage
                    final_metadata.update({
                        'prompt_token_count': getattr(usage, 'input_tokens', None),
                        'candidates_token_count': getattr(usage, 'output_tokens', None),
                        'total_token_count': getattr(usage, 'total_tokens', None),
                    })

                    # Extract detailed token counts
                    if hasattr(usage, 'output_tokens_details') and usage.output_tokens_details:
                        final_metadata['reasoning_tokens'] = getattr(
                            usage.output_tokens_details,
                            'reasoning_tokens',
                            None
                        )

                    if hasattr(usage, 'input_tokens_details') and usage.input_tokens_details:
                        final_metadata['cached_tokens'] = getattr(
                            usage.input_tokens_details,
                            'cached_tokens',
                            None
                        )

                yield StreamingChunk(
                    chunk_type="text",
                    content="",
                    metadata=final_metadata
                )

        async for chunk in stream_with_retries(
            _stream_once,
            max_retries=max_retries,
            timeout=timeout,
            debug=debug,
        ):
            yield chunk

    # _construct_response_from_streaming_chunks is now handled by ResponseProcessor
