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
from backend.domain.models.messages import BaseMessage
from backend.domain.models.streaming import StreamingChunk

# Import OpenAI-specific implementations
from .config import get_openai_client_config
from .message_formatter import OpenAIMessageFormatter
from .context_manager import OpenAIContextManager
from .debug import OpenAIDebugger
from .response_processor import OpenAIResponseProcessor
from .tool_manager import OpenAIToolManager
from .content_generators import TitleGenerator, ImagePromptGenerator


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
    
    def __init__(self, api_key: str, **kwargs):
        """
        Initialize OpenAI client.
        
        Args:
            api_key: OpenAI API key
            **kwargs: Additional configuration parameters
        """
        super().__init__(**kwargs)
        self.api_key = api_key
        
        # Initialize OpenAI-specific configuration
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
        
        self.openai_config = get_openai_client_config(**config_overrides)

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
        debug = self.openai_config.debug

        tools = api_config.get("tools", []) or []
        instructions = api_config.get("instructions")

        # context_contents is already in Responses API input format from context_manager
        input_items = context_contents

        kwargs_api = self.openai_config.get_api_call_kwargs(
            instructions=instructions,
            input_items=input_items,
            tools=tools
        )

        if 'temperature' in kwargs:
            kwargs_api['temperature'] = kwargs['temperature']
        if 'max_tokens' in kwargs:
            kwargs_api['max_output_tokens'] = kwargs['max_tokens']
        if 'top_p' in kwargs:
            kwargs_api['top_p'] = kwargs['top_p']

        if debug:
            OpenAIDebugger.log_api_call_info(
                tools_count=len(tools),
                model=self.openai_config.model_settings.model
            )
            OpenAIDebugger.print_debug_request_payload(kwargs_api)

        try:
            response = await self.async_client.responses.create(**kwargs_api)

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

    async def _prepare_complete_context(
        self,
        session_id: str
    ) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Prepare complete context and API configuration for stateless OpenAI API call.

        This method consolidates all context preparation logic for OpenAI
        and returns all necessary configuration for thread-safe API calls.

        Args:
            session_id: Session identifier

        Returns:
            Tuple containing:
            - context_contents: Conversation messages ready for Responses API input conversion
            - api_config: Dictionary with tools and instructions for the API call
        """
        # Get context manager and extract its properties
        context_manager = self.get_or_create_context_manager(session_id)
        agent_profile = getattr(context_manager, 'agent_profile', 'general')
        enable_memory = getattr(context_manager, 'enable_memory', True)

        # Get tool schemas for API
        tool_schemas = await self.tool_manager.get_function_call_schemas(session_id, agent_profile)
        tool_schemas = tool_schemas or []  # Return empty list if None

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
        # Get working contents from context manager (config obtained internally)
        working_contents = context_manager.get_working_contents()

        # Return context and config as separate values for stateless API call
        api_config = {
            'tools': tool_schemas,
            'instructions': system_prompt
        }
        return working_contents, api_config

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
        debug = self.openai_config.debug

        tools = api_config.get("tools", []) or []
        instructions = api_config.get("instructions")

        # context_contents is already in Responses API input format from context_manager
        input_items = context_contents

        kwargs_api = self.openai_config.get_api_call_kwargs(
            instructions=instructions,
            input_items=input_items,
            tools=tools
        )

        if 'temperature' in kwargs:
            kwargs_api['temperature'] = kwargs['temperature']
        if 'max_tokens' in kwargs:
            kwargs_api['max_output_tokens'] = kwargs['max_tokens']
        if 'top_p' in kwargs:
            kwargs_api['top_p'] = kwargs['top_p']

        if debug:
            OpenAIDebugger.log_api_call_info(
                tools_count=len(tools),
                model=self.openai_config.model_settings.model
            )
            OpenAIDebugger.print_debug_request_payload(kwargs_api)

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
            final_metadata = {"__openai_final_response": final_response}

            if hasattr(final_response, 'usage') and final_response.usage:
                usage = final_response.usage
                final_metadata.update({
                    'prompt_token_count': getattr(usage, 'input_tokens', None),
                    'candidates_token_count': getattr(usage, 'output_tokens', None),
                    'total_token_count': getattr(usage, 'total_tokens', None),
                })

                # Extract detailed token counts
                if hasattr(usage, 'output_tokens_details') and usage.output_tokens_details:
                    final_metadata['reasoning_tokens'] = getattr(usage.output_tokens_details, 'reasoning_tokens', None)

                if hasattr(usage, 'input_tokens_details') and usage.input_tokens_details:
                    final_metadata['cached_tokens'] = getattr(usage.input_tokens_details, 'cached_tokens', None)

            yield StreamingChunk(
                chunk_type="text",
                content="",
                metadata=final_metadata
            )

    # _construct_response_from_streaming_chunks is now handled by ResponseProcessor
