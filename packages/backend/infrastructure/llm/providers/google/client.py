"""
Gemini client implementation using unified architecture.

This implementation inherits from the base LLMClientBase and uses shared components
where possible, while implementing Gemini-specific functionality.
"""

from typing import List, Optional, Dict, Any, cast, AsyncGenerator

from google import genai
from google.genai import types
from backend.infrastructure.llm.base.client import LLMClientBase
from backend.infrastructure.llm.base.call_options import parse_call_options
from backend.infrastructure.llm.base.retry import run_with_retries, stream_with_retries
from backend.domain.models.messages import BaseMessage
from backend.domain.models.streaming import StreamingChunk

# Import Gemini-specific implementations
from .config import get_google_client_config
from .context_manager import GoogleContextManager
from .debug import GoogleDebugger
from .response_processor import GoogleResponseProcessor
from .tool_manager import GoogleToolManager


class GoogleClient(LLMClientBase):
    """
    Enhanced Google Gemini client with unified architecture.
    
    Key Features:
    - Inherits from unified LLMClientBase
    - Uses shared components where possible
    - Implements Gemini-specific functionality
    - Original response preservation during tool calling sequences
    - Thinking chain and validation field integrity
    - Real-time streaming tool call notifications
    - Comprehensive tool management and execution
    - Modular component architecture
    
    Components:
    - GoogleContextManager: Manages context and state for Gemini API calls
    - GoogleDebugger: Provides detailed request/response logging in debug mode
    - GoogleResponseProcessor: Enhanced response processing with tool call extraction
    - GoogleToolManager: Advanced MCP tool integration
    - Content Generators: Specialized content generation utilities
    """
    
    def __init__(self, api_key: str, **kwargs):
        """
        Initialize enhanced Gemini client with context preservation capabilities.
        
        Args:
            api_key: Google API key
            **kwargs: Additional configuration parameters
        """
        super().__init__(**kwargs)
        self.provider_name = "google"
        self.client = genai.Client(api_key=api_key)
        
        # Initialize Gemini-specific configuration
        config_overrides = {}
        
        # Extract relevant configuration from extra_config for overrides
        if 'model' in self.extra_config:
            config_overrides['model_settings'] = {'model': self.extra_config['model']}
        if 'temperature' in self.extra_config:
            if 'model_settings' not in config_overrides:
                config_overrides['model_settings'] = {}
            config_overrides['model_settings']['temperature'] = self.extra_config['temperature']
        if 'top_p' in self.extra_config:
            if 'model_settings' not in config_overrides:
                config_overrides['model_settings'] = {}
            config_overrides['model_settings']['top_p'] = self.extra_config['top_p']
        if 'top_k' in self.extra_config:
            if 'model_settings' not in config_overrides:
                config_overrides['model_settings'] = {}
            config_overrides['model_settings']['top_k'] = self.extra_config['top_k']
        if 'max_tokens' in self.extra_config:
            if 'model_settings' not in config_overrides:
                config_overrides['model_settings'] = {}
            config_overrides['model_settings']['max_tokens'] = self.extra_config['max_tokens']
        if 'debug' in self.extra_config:
            config_overrides['debug'] = self.extra_config['debug']
        if 'timeout' in self.extra_config:
            config_overrides['timeout'] = self.extra_config['timeout']
        if 'max_retries' in self.extra_config:
            config_overrides['max_retries'] = self.extra_config['max_retries']
        
        self.google_config = get_google_client_config(**config_overrides)
        
        print(f"Gemini Client initialized with model: {self.google_config.model_settings.model}")

        # Initialize component managers with unified architecture
        self.tool_manager = GoogleToolManager()

    # get_response is now implemented in base class using provider-specific components

    # ========== ABSTRACT METHOD IMPLEMENTATIONS ==========


    async def call_api_with_context(
        self,
        context_contents: List[Dict[str, Any]],
        api_config: Dict[str, Any],
        **kwargs
    ) -> types.GenerateContentResponse:
        """
        Execute direct Gemini API call with complete pre-formatted context and config.

        Performs a stateless API call using provided context and configuration.
        This method is thread-safe and supports concurrent sessions.

        Args:
            context_contents: Complete Gemini context contents with structure:
                - role: str - Message role ("user", "model", "system")
                - parts: List[Dict] - Content parts including text and function calls
            api_config: Gemini-specific configuration dictionary:
                - config: types.GenerateContentConfig - Complete Gemini config object
            **kwargs: Additional API configuration parameters:
                - temperature: Optional[float] - Sampling temperature override
                - max_tokens: Optional[int] - Maximum output tokens override
                - top_p: Optional[float] - Nucleus sampling parameter
                - top_k: Optional[int] - Top-k sampling parameter

        Returns:
            types.GenerateContentResponse: Raw Gemini API response with complete structure

        Raises:
            Exception: If API call fails, returns invalid response, or encounters authentication errors

        Note:
            This method is completely stateless. All configuration is passed via parameters.
        """
        call_options = parse_call_options(kwargs)
        debug = self.google_config.debug
        timeout = call_options.timeout if call_options.timeout is not None else self.google_config.timeout
        max_retries = (
            call_options.max_retries
            if call_options.max_retries is not None
            else self.google_config.max_retries
        )

        # Extract Gemini config from api_config
        config = api_config.get('config')
        if not config:
            # Fallback to basic config if not provided
            config_kwargs = self.google_config.get_generation_config_kwargs(
                system_prompt="",
                tool_schemas=[]
            )
            config = types.GenerateContentConfig(**config_kwargs)

        config_dict = config.model_dump()
        if call_options.temperature is not None:
            config_dict["temperature"] = call_options.temperature
        if call_options.max_tokens is not None:
            config_dict["max_output_tokens"] = call_options.max_tokens
        if call_options.top_p is not None:
            config_dict["top_p"] = call_options.top_p
        if call_options.top_k is not None:
            config_dict["top_k"] = call_options.top_k
        if call_options.thinking is not None:
            if isinstance(call_options.thinking, dict):
                config_dict["thinking_config"] = types.ThinkingConfig(**call_options.thinking)
            else:
                config_dict["thinking_config"] = call_options.thinking
        if call_options.enable_thinking is False:
            config_dict.pop("thinking_config", None)

        config = types.GenerateContentConfig(**config_dict)

        model = self.google_config.model_settings.model

        if debug:
            GoogleDebugger.print_request(context_contents, config, model)

        async def _call_api():
            response = await self.client.aio.models.generate_content(
                model=model,
                contents=cast(Any, context_contents),
                config=config,
            )

            # Validate response structure
            if not hasattr(response, 'candidates') or not response.candidates:
                if debug:
                    GoogleDebugger.print_error("No candidates", model, response=response)
                raise Exception(f"Empty response (no candidates). Model: {model}")

            candidate = response.candidates[0]
            if not hasattr(candidate, 'content') or not candidate.content:
                if debug:
                    GoogleDebugger.print_error("Empty content", model, candidate=candidate)
                raise Exception(
                    f"Empty content. Model: {model}, finish_reason: {getattr(candidate, 'finish_reason', None)}"
                )

            if not hasattr(candidate.content, 'parts') or not candidate.content.parts:
                if debug:
                    GoogleDebugger.print_error("Empty parts", model, candidate=candidate)
                raise Exception(
                    f"Empty parts. Model: {model}, "
                    f"finish_reason: {getattr(candidate, 'finish_reason', None)}, "
                    f"safety_ratings: {getattr(candidate, 'safety_ratings', None)}"
                )

            if debug:
                GoogleDebugger.print_response(response)

            return response

        try:
            return await run_with_retries(
                _call_api,
                max_retries=max_retries,
                timeout=timeout,
                debug=debug,
                provider="Google",
            )
        except Exception as e:
            if debug and "Empty" not in str(e):
                print(f"[DEBUG] API error: {e}")
            raise Exception(f"Gemini API failed: {e}")

    # ========== PROVIDER-SPECIFIC METHODS FOR BASE IMPLEMENTATION ==========


    def _get_response_processor(self):
        """Get Gemini-specific response processor instance."""
        return GoogleResponseProcessor()

    def _get_context_manager_class(self):
        """Get Gemini-specific context manager class."""
        return GoogleContextManager

    def _build_api_config(
        self,
        system_prompt: str,
        tool_schemas: Optional[List[Any]]
    ) -> Dict[str, Any]:
        """
        Build Gemini-specific API configuration.

        Args:
            system_prompt: Pre-built system prompt
            tool_schemas: Tool schemas in Gemini format

        Returns:
            Dict with 'config' key containing GenerateContentConfig
        """
        config_kwargs = self.google_config.get_generation_config_kwargs(
            system_prompt=system_prompt,
            tool_schemas=tool_schemas or []
        )
        config = types.GenerateContentConfig(**config_kwargs)
        return {'config': config}

    def _get_provider_config(self):
        """Get Gemini-specific configuration object."""
        return self.google_config

    async def call_api_with_context_streaming(
        self,
        context_contents: List[Dict[str, Any]],
        api_config: Dict[str, Any],
        **kwargs
    ) -> AsyncGenerator[StreamingChunk, None]:
        """
        Execute streaming Gemini API call with real-time chunk delivery.

        Streams responses from Gemini API and converts native chunks into
        standardized StreamingChunk objects for consistent handling.

        Args:
            context_contents: Complete Gemini context contents
            api_config: Gemini-specific configuration with 'config' key
            **kwargs: Additional API parameters (temperature, max_tokens, etc.)

        Yields:
            StreamingChunk: Standardized streaming chunks containing thinking,
                          text, or function_call content

        Raises:
            Exception: If streaming API call fails
        """
        call_options = parse_call_options(kwargs)
        debug = self.google_config.debug
        timeout = call_options.timeout if call_options.timeout is not None else self.google_config.timeout
        max_retries = (
            call_options.max_retries
            if call_options.max_retries is not None
            else self.google_config.max_retries
        )

        # Extract Gemini config from api_config
        config = api_config.get('config')
        if not config:
            # Fallback to basic config if not provided
            config_kwargs = self.google_config.get_generation_config_kwargs(
                system_prompt="",
                tool_schemas=[]
            )
            config = types.GenerateContentConfig(**config_kwargs)

        config_dict = config.model_dump()
        if call_options.temperature is not None:
            config_dict["temperature"] = call_options.temperature
        if call_options.max_tokens is not None:
            config_dict["max_output_tokens"] = call_options.max_tokens
        if call_options.top_p is not None:
            config_dict["top_p"] = call_options.top_p
        if call_options.top_k is not None:
            config_dict["top_k"] = call_options.top_k
        if call_options.thinking is not None:
            if isinstance(call_options.thinking, dict):
                config_dict["thinking_config"] = types.ThinkingConfig(**call_options.thinking)
            else:
                config_dict["thinking_config"] = call_options.thinking
        if call_options.enable_thinking is False:
            config_dict.pop("thinking_config", None)

        config = types.GenerateContentConfig(**config_dict)

        model = self.google_config.model_settings.model

        if debug:
            GoogleDebugger.print_request(context_contents, config, model)

        async def _stream_once():
            try:
                # Use streaming API
                stream_generator = self.client.aio.models.generate_content_stream(
                    model=model,
                    contents=cast(Any, context_contents),
                    config=config,
                )

                # Create stateful streaming processor
                streaming_processor = self._get_response_processor().create_streaming_processor()

                # Debug counters
                chunk_index = 0
                empty_chunk_count = 0

                async for chunk in await stream_generator:
                    # Debug: print raw chunk before processing
                    if debug:
                        GoogleDebugger.print_streaming_chunk(chunk, chunk_index)

                    # Delegate chunk processing to streaming processor
                    processed_chunks = streaming_processor.process_event(chunk)

                    # Track empty chunks for debugging
                    if debug and not processed_chunks:
                        empty_chunk_count += 1

                    for processed_chunk in processed_chunks:
                        yield processed_chunk

                    chunk_index += 1

                # Debug: print summary after streaming completes
                if debug:
                    GoogleDebugger.print_streaming_summary(chunk_index, empty_chunk_count)

            except Exception as e:
                error_message = f"Gemini streaming API call failed: {str(e)}"
                if debug:
                    print(f"[DEBUG] {error_message}")
                raise Exception(error_message)

        async for chunk in stream_with_retries(
            _stream_once,
            max_retries=max_retries,
            timeout=timeout,
            debug=debug,
            provider="Google",
        ):
            yield chunk

    # _streaming_tool_calling_loop is inherited from LLMClientBase
    # _construct_response_from_streaming_chunks is now handled by ResponseProcessor
