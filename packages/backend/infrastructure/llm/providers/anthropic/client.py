from typing import List, Optional, Dict, Any, AsyncGenerator
from backend.infrastructure.llm.base.client import LLMClientBase
from backend.infrastructure.llm.base.call_options import parse_call_options
from backend.infrastructure.llm.base.retry import run_with_retries, stream_with_retries
from backend.domain.models.streaming import StreamingChunk
import anthropic
from .config import get_anthropic_client_config
from .response_processor import AnthropicResponseProcessor
from .debug import AnthropicDebugger
from .context_manager import AnthropicContextManager
from .tool_manager import AnthropicToolManager

class AnthropicClient(LLMClientBase):
    """
    Anthropic Claude client class.
    """
    
    def __init__(self, api_key: str, **kwargs):
        """
        Initialize AnthropicClient instance.
        Args:
            api_key: Anthropic API key。
            **kwargs: Additional configuration parameters
        """
        super().__init__(**kwargs)
        self.provider_name = "anthropic"
        self.api_key = api_key
        
        # Initialize Anthropic-specific configuration
        config_overrides = {}
        
        # Apply any extra configuration overrides
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
        if 'thinking_budget_tokens' in self.extra_config:
            if 'model_settings' not in config_overrides:
                config_overrides['model_settings'] = {}
            config_overrides['model_settings']['thinking_budget_tokens'] = self.extra_config['thinking_budget_tokens']
        if 'enable_thinking' in self.extra_config:
            if 'model_settings' not in config_overrides:
                config_overrides['model_settings'] = {}
            config_overrides['model_settings']['enable_thinking'] = self.extra_config['enable_thinking']
        if 'debug' in self.extra_config:
            config_overrides['debug'] = self.extra_config['debug']
        
        self.anthropic_config = get_anthropic_client_config(**config_overrides)
        
        print(f"Enhanced Anthropic Client initialized with model: {self.anthropic_config.model_settings.model}")

        # initialize Anthropic API client (use async client for streaming)
        self.client = anthropic.AsyncAnthropic(api_key=self.api_key)

        # initialize tool manager
        self.tool_manager = AnthropicToolManager()


    def _get_response_processor(self) -> AnthropicResponseProcessor:
        """Get Anthropic-specific response processor instance."""
        return AnthropicResponseProcessor()

    def _get_context_manager_class(self):
        """Get Anthropic-specific context manager class."""
        return AnthropicContextManager

    def _build_api_config(
        self,
        system_prompt: str,
        tool_schemas: Optional[List[Any]]
    ) -> Dict[str, Any]:
        """
        Build Anthropic-specific API configuration.

        Args:
            system_prompt: Pre-built system prompt
            tool_schemas: Tool schemas in Anthropic format

        Returns:
            Dict with 'tools' and 'system_prompt' keys
        """
        return {
            'tools': tool_schemas or [],
            'system_prompt': system_prompt
        }

    def _get_provider_config(self):
        """Get Anthropic-specific configuration object."""
        return self.anthropic_config

    async def call_api_with_context(
        self,
        context_contents: List[Dict[str, Any]],
        api_config: Dict[str, Any],
        **kwargs
    ):
        """
        Execute direct Anthropic API call with complete pre-formatted context and config.

        Performs a stateless API call using provided context and configuration.
        This method is thread-safe and supports concurrent sessions.

        Args:
            context_contents: Complete Anthropic context contents with messages
            api_config: Anthropic-specific configuration dictionary:
                - tools: List[Dict] - Tool schemas in Anthropic format
                - system_prompt: str - System prompt for Anthropic
            **kwargs: Additional API configuration parameters

        Returns:
            Anthropic API response

        Note:
            This method is completely stateless. All configuration is passed via parameters.
        """
        call_options = parse_call_options(kwargs)
        debug = self.anthropic_config.debug
        timeout = (
            call_options.timeout
            if call_options.timeout is not None
            else self.anthropic_config.model_settings.timeout
        )
        max_retries = (
            call_options.max_retries
            if call_options.max_retries is not None
            else self.anthropic_config.model_settings.max_retries
        )

        # Extract configuration from api_config
        tools = api_config.get('tools', [])
        system_prompt = api_config.get('system_prompt', '')

        # 使用配置系统构建API参数
        kwargs_api = self.anthropic_config.get_api_call_kwargs(
            system_prompt=system_prompt,
            messages=context_contents,
            tools=tools
        )

        if call_options.temperature is not None:
            kwargs_api["temperature"] = call_options.temperature
        if call_options.max_tokens is not None:
            kwargs_api["max_tokens"] = call_options.max_tokens
        if call_options.top_p is not None:
            kwargs_api["top_p"] = call_options.top_p
        if call_options.top_k is not None:
            kwargs_api["top_k"] = call_options.top_k
        if call_options.thinking is not None:
            kwargs_api["thinking"] = call_options.thinking
        if call_options.enable_thinking is False:
            kwargs_api.pop("thinking", None)

        async def _call_api():
            # call the Anthropic API (async)
            return await self.client.messages.create(**kwargs_api)

        try:
            return await run_with_retries(
                _call_api,
                max_retries=max_retries,
                timeout=timeout,
                debug=debug,
            )
        except Exception as e:
            # Log debug information if in debug mode
            if debug:
                print(f"[DEBUG] API call failed with error: {str(e)}")
                print(f"[DEBUG] Failed request payload:")
                AnthropicDebugger.print_debug_request_payload(kwargs_api)

            raise e

    async def call_api_with_context_streaming(
        self,
        context_contents: List[Dict[str, Any]],
        api_config: Dict[str, Any],
        **kwargs
    ) -> AsyncGenerator[StreamingChunk, None]:
        """
        Execute streaming Anthropic API call with real-time chunk delivery.

        Streams responses from Anthropic API and converts native chunks into
        standardized StreamingChunk objects for consistent handling.

        Args:
            context_contents: Complete Anthropic context contents with messages
            api_config: Anthropic-specific configuration dictionary:
                - tools: List[Dict] - Tool schemas in Anthropic format
                - system_prompt: str - System prompt for Anthropic
            **kwargs: Additional API parameters (temperature, max_tokens, etc.)

        Yields:
            StreamingChunk: Standardized streaming chunks containing thinking,
                          text, or function_call content

        Raises:
            Exception: If streaming API call fails
        """
        call_options = parse_call_options(kwargs)
        debug = self.anthropic_config.debug
        timeout = (
            call_options.timeout
            if call_options.timeout is not None
            else self.anthropic_config.model_settings.timeout
        )
        max_retries = (
            call_options.max_retries
            if call_options.max_retries is not None
            else self.anthropic_config.model_settings.max_retries
        )

        # Extract configuration from api_config
        tools = api_config.get('tools', [])
        system_prompt = api_config.get('system_prompt', '')

        # Build API parameters using configuration system
        kwargs_api = self.anthropic_config.get_api_call_kwargs(
            system_prompt=system_prompt,
            messages=context_contents,
            tools=tools
        )

        if call_options.temperature is not None:
            kwargs_api["temperature"] = call_options.temperature
        if call_options.max_tokens is not None:
            kwargs_api["max_tokens"] = call_options.max_tokens
        if call_options.top_p is not None:
            kwargs_api["top_p"] = call_options.top_p
        if call_options.top_k is not None:
            kwargs_api["top_k"] = call_options.top_k
        if call_options.thinking is not None:
            kwargs_api["thinking"] = call_options.thinking
        if call_options.enable_thinking is False:
            kwargs_api.pop("thinking", None)

        if debug:
            AnthropicDebugger.print_debug_request_payload(kwargs_api)

        async def _stream_once():
            try:
                # Create stateful streaming processor
                streaming_processor = self._get_response_processor().create_streaming_processor()

                # Use Anthropic's async streaming context manager
                async with self.client.messages.stream(**kwargs_api) as stream:
                    async for event in stream:
                        # Delegate event processing to streaming processor
                        processed_chunks = streaming_processor.process_event(event)
                        for chunk in processed_chunks:
                            yield chunk

            except Exception as e:
                if debug:
                    print(f"[DEBUG] Streaming API call failed with error: {str(e)}")
                    print(f"[DEBUG] Failed request payload:")
                    AnthropicDebugger.print_debug_request_payload(kwargs_api)

                raise e

        async for chunk in stream_with_retries(
            _stream_once,
            max_retries=max_retries,
            timeout=timeout,
            debug=debug,
        ):
            yield chunk

    # _construct_response_from_streaming_chunks is now handled by ResponseProcessor
