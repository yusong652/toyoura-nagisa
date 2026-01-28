"""
Zhipu (GLM) client implementation using official zai SDK.

This implementation uses the zai-sdk which provides access to Zhipu GLM models.
Since zai SDK is synchronous, we use asyncio.to_thread() for async compatibility.
"""

import asyncio
from typing import List, Dict, Any, AsyncGenerator, cast, Optional
from zai import ZhipuAiClient
from zai.types.chat import Completion

from backend.infrastructure.llm.base.client import LLMClientBase
from backend.infrastructure.llm.base.call_options import parse_call_options
from backend.infrastructure.llm.base.retry import run_with_retries, stream_with_retries
from backend.domain.models.streaming import StreamingChunk
from backend.config.dev import get_dev_config

# Import Zhipu-specific implementations
from .config import ZhipuConfig
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

    def __init__(self, config: ZhipuConfig, extra_config: Optional[Dict[str, Any]] = None, **kwargs):
        """
        Initialize Zhipu client.

        Args:
            config: Zhipu specific configuration
            extra_config: Additional configuration parameters
            **kwargs: Catch-all for extra arguments from factory
        """
        super().__init__(extra_config=extra_config)
        self.provider_name = "zhipu"
        self.zhipu_config = config
        self.api_key = config.zhipu_api_key
        # Initialize zai SDK client (use SDK default base_url)
        self.client = ZhipuAiClient(
            api_key=self.api_key,
            timeout=self.zhipu_config.timeout,
            max_retries=self.zhipu_config.max_retries
        )

        # Initialize unified tool manager
        self.tool_manager = ZhipuToolManager()

    # ========== CORE API METHODS ==========

    @staticmethod
    def _convert_inline_data_to_image_url(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Convert inline_data format to image_url format for Zhipu API.

        GLM-4V models expect image_url format with base64 data URL.
        This method converts inline_data blocks to the required format.

        Args:
            messages: List of messages potentially containing inline_data

        Returns:
            List of messages with inline_data converted to image_url
        """
        import copy
        converted = []

        for msg in messages:
            msg_copy = copy.deepcopy(msg)
            content = msg_copy.get('content')

            if isinstance(content, list):
                new_content = []
                for part in content:
                    if isinstance(part, dict):
                        # Check for inline_data format
                        if 'inline_data' in part or part.get('type') == 'image':
                            inline_data = part.get('inline_data', part)
                            if isinstance(inline_data, dict) and 'data' in inline_data:
                                mime_type = inline_data.get('mime_type', 'image/png')
                                data = inline_data['data']
                                # Convert to image_url format
                                new_content.append({
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:{mime_type};base64,{data}"
                                    }
                                })
                                continue
                    new_content.append(part)
                msg_copy['content'] = new_content

            converted.append(msg_copy)

        return converted

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
        call_options = parse_call_options(kwargs)
        debug = get_dev_config().debug_mode
        timeout = call_options.timeout if call_options.timeout is not None else self.zhipu_config.timeout
        max_retries = (
            call_options.max_retries
            if call_options.max_retries is not None
            else self.zhipu_config.max_retries
        )

        tools = api_config.get("tools", []) or []

        # Build messages and convert inline_data to image_url for API compatibility
        messages = self._convert_inline_data_to_image_url(context_contents)

        # Add system message if provided
        system_prompt = api_config.get("system_prompt")
        if system_prompt:
            messages.insert(0, {
                "role": "system",
                "content": system_prompt
            })

        # Build API parameters
        api_kwargs = self.zhipu_config.build_api_params()
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

        # Handle thinking configuration based on thinking_level
        if call_options.thinking_level is not None and call_options.thinking_level != "default":
            # For Zhipu, we currently just enable it if level is low/high
            api_kwargs["thinking"] = {"type": "enabled"}

        if debug:
            ZhipuDebugger.print_api_request(api_kwargs, messages, tools)

        async def _call_api():
            # Wrap synchronous call with asyncio.to_thread
            # Cast to Completion since stream=False guarantees this type
            return cast(
                Completion,
                await asyncio.to_thread(
                    self.client.chat.completions.create,
                    **api_kwargs
                )
            )

        try:
            return await run_with_retries(
                _call_api,
                max_retries=max_retries,
                timeout=timeout,
                debug=debug,
            )
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
        Execute streaming Zhipu API call with real-time chunk delivery and retry logic.

        Args:
            context_contents: Conversation messages in standard format.
            api_config: Provider configuration including tools and system prompt.
            **kwargs: Optional overrides.

        Yields:
            StreamingChunk: Standardized streaming data chunks.
        """
        call_options = parse_call_options(kwargs)
        debug = get_dev_config().debug_mode
        timeout = call_options.timeout if call_options.timeout is not None else self.zhipu_config.timeout
        max_retries = (
            call_options.max_retries
            if call_options.max_retries is not None
            else self.zhipu_config.max_retries
        )

        tools = api_config.get("tools", []) or []

        # Build messages and convert inline_data to image_url for API compatibility
        messages = self._convert_inline_data_to_image_url(context_contents)

        # Add system message if provided
        system_prompt = api_config.get("system_prompt")
        if system_prompt:
            messages.insert(0, {
                "role": "system",
                "content": system_prompt
            })

        # Build API parameters
        api_kwargs = self.zhipu_config.build_api_params()
        api_kwargs.update({
            "messages": messages,
            "tools": tools,
            "tool_choice": "auto" if tools else None,
            "stream": True,
        })

        if call_options.temperature is not None:
            api_kwargs['temperature'] = call_options.temperature
        if call_options.max_tokens is not None:
            api_kwargs['max_tokens'] = call_options.max_tokens
        if call_options.top_p is not None:
            api_kwargs['top_p'] = call_options.top_p
        if call_options.timeout is not None:
            api_kwargs['timeout'] = call_options.timeout

        # Handle thinking configuration based on thinking_level
        if call_options.thinking_level is not None and call_options.thinking_level != "default":
            # For Zhipu, we currently just enable it if level is low/high
            api_kwargs["thinking"] = {"type": "enabled"}

        if debug:
            ZhipuDebugger.print_api_request(api_kwargs, messages, tools)

        async def _stream_once():
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
            loop = asyncio.get_running_loop()

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
