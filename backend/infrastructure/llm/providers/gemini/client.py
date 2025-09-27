"""
Gemini client implementation using unified architecture.

This implementation inherits from the base LLMClientBase and uses shared components
where possible, while implementing Gemini-specific functionality.
"""

from typing import List, Optional, Dict, Any, cast

from google import genai
from google.genai import types
from backend.infrastructure.llm.base.client import LLMClientBase
from backend.domain.models.messages import BaseMessage

# Import Gemini-specific implementations
from .config import get_gemini_client_config
from .context_manager import GeminiContextManager
from .debug import GeminiDebugger
from .response_processor import GeminiResponseProcessor
from .tool_manager import GeminiToolManager
from .content_generators import GeminiTitleGenerator, GeminiImagePromptGenerator, GeminiWebSearchGenerator


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
            # Direct API call with preserved context
            response = self.client.models.generate_content(
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

    # ========== SPECIALIZED CONTENT GENERATION ==========

    async def generate_title_from_messages(
        self,
        latest_messages: List[BaseMessage]
    ) -> Optional[str]:
        """
        Generate conversation title using Gemini API.
        Customized implementation for Gemini API supporting multimodal content.
        
        Args:
            latest_messages: Recent conversation messages to generate title from
        """
        return await GeminiTitleGenerator.generate_title_from_messages(
            self.client, latest_messages
        )

    async def generate_text_to_image_prompt(self, session_id: Optional[str] = None) -> Optional[Dict[str, str]]:
        """
        Generate high-quality text-to-image prompt using the Gemini API.
        This method uses a specialized system prompt to create detailed and effective prompts for image generation
        based on the recent conversation context.
        
        Args:
            session_id: Optional session ID to get the latest conversation context
            
        Returns:
            Optional[Dict[str, str]]: A dictionary containing the text prompt and negative prompt, or None if generation fails
        """
        debug = self.gemini_config.debug
        return await GeminiImagePromptGenerator.generate_text_to_image_prompt(self.client, session_id, debug)

    async def perform_web_search(self, query: str, **kwargs) -> Dict[str, Any]:
        """
        Perform a web search using Google Search via the Gemini API.
        
        This method uses the project's unified client configuration and provides
        comprehensive error handling and debugging support.
        
        Args:
            query: The search query to find information on the web
            **kwargs: Additional search parameters
            
        Returns:
            Dictionary containing search results with sources and metadata
        """
        debug = self.gemini_config.debug
        return await GeminiWebSearchGenerator.perform_web_search(self.client, query, debug, **kwargs)

    # ========== PROVIDER-SPECIFIC METHODS FOR BASE IMPLEMENTATION ==========


    def _get_response_processor(self):
        """Get Gemini-specific response processor instance."""
        return GeminiResponseProcessor()

    def _get_context_manager_class(self):
        """Get Gemini-specific context manager class."""
        return GeminiContextManager

    async def _prepare_complete_context(
        self,
        session_id: str
    ) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Prepare complete context and API configuration for stateless Gemini API call.

        This method consolidates all context preparation logic for Gemini
        and returns all necessary configuration for thread-safe API calls.

        Args:
            session_id: Session identifier

        Returns:
            Tuple containing:
            - context_contents: Messages for Gemini API
            - api_config: Dictionary with 'config' key containing GenerateContentConfig
        """
        # Get context manager and extract its properties
        context_manager = self.get_or_create_context_manager(session_id)
        agent_profile = getattr(context_manager, 'agent_profile', 'general')
        enable_memory = getattr(context_manager, 'enable_memory', True)

        # Get tool schemas for API
        tool_schemas = await self.tool_manager.get_function_call_schemas(session_id, agent_profile)

        # Get tool schemas formatted for system prompt
        prompt_tool_schemas = await self.tool_manager.get_schemas_for_system_prompt(session_id, agent_profile)

        # Build system prompt with tool schemas and memory
        from backend.shared.utils.prompt.builder import build_system_prompt
        from backend.config import get_llm_settings

        system_prompt = await build_system_prompt(
            agent_profile=agent_profile,
            session_id=session_id,
            enable_memory=enable_memory,
            tool_schemas=prompt_tool_schemas
        )

        debug = get_llm_settings().debug
        if debug:
            print(f"[DEBUG] System prompt for session {session_id}:\n{system_prompt}\n")

        # Get working contents from context manager (config obtained internally)
        working_contents = context_manager.get_working_contents()

        # Build API configuration with tool schemas and system prompt
        config_kwargs = self.gemini_config.get_generation_config_kwargs(
            system_prompt=system_prompt or "",
            tool_schemas=tool_schemas
        )

        # Create config object for stateless API call
        config = types.GenerateContentConfig(**config_kwargs)

        # Return context and config as separate values for thread-safe API call
        api_config = {'config': config}
        return working_contents, api_config

    def _get_provider_config(self):
        """Get Gemini-specific configuration object."""
        return self.gemini_config

    # _streaming_tool_calling_loop is inherited from LLMClientBase