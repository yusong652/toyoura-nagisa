"""
Gemini client implementation using unified architecture.

This implementation inherits from the base LLMClientBase and uses shared components
where possible, while implementing Gemini-specific functionality.
"""

from typing import List, Optional, Dict, Any, cast, AsyncGenerator

from google import genai
from google.genai import types
from backend.infrastructure.llm.base.client import LLMClientBase
from backend.domain.models.messages import BaseMessage
from backend.domain.models.streaming import StreamingChunk

# Import Gemini-specific implementations
from .config import get_gemini_client_config
from .context_manager import GeminiContextManager
from .debug import GeminiDebugger
from .response_processor import GeminiResponseProcessor
from .tool_manager import GeminiToolManager


class GeminiClient(LLMClientBase):
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
    - GeminiContextManager: Manages context and state for Gemini API calls
    - GeminiDebugger: Provides detailed request/response logging in debug mode
    - GeminiResponseProcessor: Enhanced response processing with tool call extraction
    - GeminiToolManager: Advanced MCP tool integration
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
        if 'max_output_tokens' in self.extra_config:
            if 'model_settings' not in config_overrides:
                config_overrides['model_settings'] = {}
            config_overrides['model_settings']['max_output_tokens'] = self.extra_config['max_output_tokens']
        if 'debug' in self.extra_config:
            config_overrides['debug'] = self.extra_config['debug']
        
        self.gemini_config = get_gemini_client_config(**config_overrides)
        
        print(f"Gemini Client initialized with model: {self.gemini_config.model_settings.model}")

        # Initialize component managers with unified architecture
        self.tool_manager = GeminiToolManager()

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
                - max_output_tokens: Optional[int] - Maximum output tokens override
                - top_p: Optional[float] - Nucleus sampling parameter
                - top_k: Optional[int] - Top-k sampling parameter

        Returns:
            types.GenerateContentResponse: Raw Gemini API response with complete structure

        Raises:
            Exception: If API call fails, returns invalid response, or encounters authentication errors

        Note:
            This method is completely stateless. All configuration is passed via parameters.
        """
        debug = self.gemini_config.debug

        # Extract Gemini config from api_config
        config = api_config.get('config')
        if not config:
            # Fallback to basic config if not provided
            config_kwargs = self.gemini_config.get_generation_config_kwargs(
                system_prompt="",
                tool_schemas=[]
            )
            config_kwargs.update(kwargs)
            config = types.GenerateContentConfig(**config_kwargs)
        else:
            # Apply any additional kwargs to the provided config
            if kwargs:
                config_dict = config.model_dump()
                config_dict.update(kwargs)
                config = types.GenerateContentConfig(**config_dict)

        if debug:
            print(f"[DEBUG] API call with {len(context_contents)} context items")
            GeminiDebugger.print_debug_request(context_contents, config)

        try:
            # Direct async API call with preserved context
            response = await self.client.aio.models.generate_content(
                model=self.gemini_config.model_settings.model,
                contents=cast(Any, context_contents),
                config=config,
            )

            # Validate response structure
            if not hasattr(response, 'candidates') or not response.candidates:
                raise Exception("Gemini API returned empty response")

            if debug:
                print(f"[DEBUG] API call successful, response received")
                GeminiDebugger.print_debug_response(response)

            return response

        except Exception as e:
            error_message = f"Gemini API call failed: {str(e)}"
            if debug:
                print(f"[DEBUG] {error_message}")
            raise Exception(error_message)

    # ========== PROVIDER-SPECIFIC METHODS FOR BASE IMPLEMENTATION ==========


    def _get_response_processor(self):
        """Get Gemini-specific response processor instance."""
        return GeminiResponseProcessor()

    def _get_context_manager_class(self):
        """Get Gemini-specific context manager class."""
        return GeminiContextManager

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
        config_kwargs = self.gemini_config.get_generation_config_kwargs(
            system_prompt=system_prompt,
            tool_schemas=tool_schemas
        )
        config = types.GenerateContentConfig(**config_kwargs)
        return {'config': config}

    def _get_provider_config(self):
        """Get Gemini-specific configuration object."""
        return self.gemini_config

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
            **kwargs: Additional API parameters (temperature, max_output_tokens, etc.)

        Yields:
            StreamingChunk: Standardized streaming chunks containing thinking,
                          text, or function_call content

        Raises:
            Exception: If streaming API call fails
        """
        debug = self.gemini_config.debug

        # Extract Gemini config from api_config
        config = api_config.get('config')
        if not config:
            # Fallback to basic config if not provided
            config_kwargs = self.gemini_config.get_generation_config_kwargs(
                system_prompt="",
                tool_schemas=[]
            )
            config_kwargs.update(kwargs)
            config = types.GenerateContentConfig(**config_kwargs)
        else:
            # Apply any additional kwargs to the provided config
            if kwargs:
                config_dict = config.model_dump()
                config_dict.update(kwargs)
                config = types.GenerateContentConfig(**config_dict)

        if debug:
            print(f"[DEBUG] Streaming API call with {len(context_contents)} context items")
            GeminiDebugger.print_debug_request(context_contents, config)

        try:
            # Use streaming API
            stream_generator = self.client.aio.models.generate_content_stream(
                model=self.gemini_config.model_settings.model,
                contents=cast(Any, context_contents),
                config=config,
            )

            # Create stateful streaming processor
            streaming_processor = self._get_response_processor().create_streaming_processor()
            async for chunk in await stream_generator:
                # Delegate chunk processing to streaming processor
                processed_chunks = streaming_processor.process_event(chunk)
                for processed_chunk in processed_chunks:
                    yield processed_chunk

            if debug:
                print(f"[DEBUG] Streaming API call completed successfully")

        except Exception as e:
            error_message = f"Gemini streaming API call failed: {str(e)}"
            if debug:
                print(f"[DEBUG] {error_message}")
            raise Exception(error_message)

    # _streaming_tool_calling_loop is inherited from LLMClientBase
    # _construct_response_from_streaming_chunks is now handled by ResponseProcessor