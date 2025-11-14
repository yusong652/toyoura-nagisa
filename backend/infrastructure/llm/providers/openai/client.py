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
        tool_call_index: Dict[str, Dict[str, Any]] = {}

        try:
            async with self.async_client.responses.stream(**kwargs_api) as stream:
                async for event in stream:
                    # Thinking / reasoning summary events
                    if isinstance(event, ResponseReasoningSummaryTextDeltaEvent):
                        if event.delta:
                            yield StreamingChunk(
                                chunk_type="thinking",
                                content=event.delta,
                                metadata={
                                    "item_id": event.item_id,
                                    "summary_index": event.summary_index
                                }
                            )
                    elif isinstance(event, ResponseReasoningSummaryTextDeltaEvent):
                        delta = event.delta
                        summary_text = ""
                        if isinstance(delta, dict):
                            summary_text = str(delta.get("text", ""))
                        elif hasattr(delta, "text"):
                            summary_text = str(getattr(delta, "text", ""))
                        if summary_text:
                            yield StreamingChunk(
                                chunk_type="thinking",
                                content=summary_text,
                                metadata={
                                    "item_id": event.item_id,
                                    "summary_index": event.summary_index
                                }
                            )
                    elif isinstance(event, ResponseReasoningSummaryPartAddedEvent):
                        part_text = getattr(event.part, "text", "")
                        if part_text:
                            yield StreamingChunk(
                                chunk_type="thinking",
                                content=part_text,
                                metadata={
                                    "item_id": event.item_id,
                                    "summary_index": event.summary_index
                                }
                            )
                    elif isinstance(event, ResponseReasoningTextDeltaEvent):
                        if event.delta:
                            yield StreamingChunk(
                                chunk_type="thinking",
                                content=str(event.delta),
                                metadata={"item_id": event.item_id}
                            )

                    # Text deltas
                    if isinstance(event, ResponseTextDeltaEvent):
                        if event.delta:
                            yield StreamingChunk(
                                chunk_type="text",
                                content=event.delta,
                                metadata={
                                    "item_id": event.item_id,
                                    "content_index": event.content_index
                                }
                            )

                    # Function call lifecycle
                    if isinstance(event, ResponseOutputItemAddedEvent):
                        item = event.item
                        if isinstance(item, ResponseFunctionToolCall):
                            call_id = item.call_id or item.id or item.name
                            info = {
                                "call_id": call_id,
                                "id": item.id or call_id,
                                "name": item.name
                            }
                            # Map both id and call_id for lookup
                            tool_call_index[call_id] = info
                            if item.id:
                                tool_call_index[item.id] = info

                    elif isinstance(event, ResponseFunctionCallArgumentsDeltaEvent):
                        info = tool_call_index.get(event.item_id, {})
                        snapshot_text = getattr(event, "snapshot", "")
                        if snapshot_text:
                            try:
                                args_snapshot = json.loads(snapshot_text)
                            except Exception:
                                args_snapshot = {}
                        else:
                            args_snapshot = {}

                        yield StreamingChunk(
                            chunk_type="function_call",
                            content=info.get("name", ""),
                            metadata={
                                "tool_id": info.get("call_id"),
                                "delta": event.delta
                            },
                            function_call={
                                "id": info.get("call_id"),
                                "name": info.get("name"),
                                "args": args_snapshot
                            }
                        )

                    elif isinstance(event, ResponseFunctionCallArgumentsDoneEvent):
                        info = tool_call_index.get(event.item_id, {})
                        arguments_text = event.arguments or ""
                        if arguments_text:
                            try:
                                parsed_args = json.loads(arguments_text)
                            except Exception:
                                parsed_args = arguments_text
                        else:
                            parsed_args = event.arguments

                        yield StreamingChunk(
                            chunk_type="function_call",
                            content=info.get("name", ""),
                            metadata={
                                "tool_id": info.get("call_id"),
                                "is_final": True
                            },
                            function_call={
                                "id": info.get("call_id"),
                                "name": info.get("name"),
                                "args": parsed_args
                            }
                        )

                    # Capture final response metadata
                    if isinstance(event, ResponseCompletedEvent):
                        final_response = event.response

        except Exception:
            if debug:
                OpenAIDebugger.print_debug_request_payload(kwargs_api)
            raise

        if final_response:
            yield StreamingChunk(
                chunk_type="text",
                content="",
                metadata={"__openai_final_response": final_response}
            )

    def _construct_response_from_streaming_chunks(
        self,
        chunks: List[StreamingChunk]
    ) -> Response:
        """
        Convert collected streaming chunks back into a complete Response object.
        """
        # Prefer the response captured during streaming if available
        for chunk in reversed(chunks):
            metadata = chunk.metadata or {}
            final_response = metadata.get("__openai_final_response")
            if isinstance(final_response, Response):
                return final_response

        # Fallback reconstruction from streamed text/thinking
        text_output = "".join(
            chunk.content for chunk in chunks if chunk.chunk_type == "text"
        )
        reasoning_output = "".join(
            chunk.content for chunk in chunks if chunk.chunk_type == "thinking"
        )

        output_items: List[Any] = []

        if reasoning_output:
            output_items.append(
                ResponseReasoningItem.model_construct(
                    id="reasoning_stream",
                    type="reasoning",
                    summary=[{"type": "summary_text", "text": reasoning_output}],
                    status="completed",
                    encrypted_content=None
                )
            )

        if text_output:
            output_items.append(
                ResponseOutputMessage.model_construct(
                    id="msg_stream",
                    role="assistant",
                    status="completed",
                    type="message",
                    content=[
                        ResponseOutputText.model_construct(
                            type="output_text",
                            text=text_output,
                            annotations=[]
                        )
                    ]
                )
            )

        return Response.model_construct(
            id="resp_stream",
            object="response",
            created_at=int(time.time()),
            status="completed",
            model=self.openai_config.model_settings.model,
            output=output_items,
            reasoning=None,
            instructions=None,
            metadata={},
            parallel_tool_calls=True,
            tools=[],
            temperature=self.openai_config.model_settings.temperature,
            top_p=self.openai_config.model_settings.top_p,
            text=None,
            usage=None,
            tool_choice=None,
            max_output_tokens=self.openai_config.model_settings.max_tokens,
            previous_response_id=None,
            prompt=None,
            service_tier=None,
            truncation="disabled",
            background=None,
            user=None,
            error=None,
            incomplete_details=None
        )
