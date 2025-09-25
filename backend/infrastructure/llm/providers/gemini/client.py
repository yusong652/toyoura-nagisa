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
        
        print(f"Enhanced Gemini Client initialized with model: {self.gemini_config.model_settings.model}")

        # Initialize component managers with unified architecture
        self.tool_manager = GeminiToolManager()

    # get_response is now implemented in base class using provider-specific components

    # ========== ABSTRACT METHOD IMPLEMENTATIONS ==========

    async def get_function_call_schemas(self, session_id: str, agent_profile: str = "general") -> List[types.Tool]:
        """
        Get MCP tool schemas in Gemini format based on agent profile.
        
        Args:
            session_id: Session ID for context-specific tools (required for dependency injection)
            agent_profile: Agent profile type for tool filtering
            
        Returns:
            List[types.Tool]: Tool schemas in Gemini format
        """
        debug = self.gemini_config.debug
        return await self.tool_manager.get_function_call_schemas(session_id, agent_profile)

    async def call_api_with_context(
        self,
        context_contents: List[Dict[str, Any]],
        **kwargs
    ) -> types.GenerateContentResponse:
        """
        Execute direct Gemini API call with complete pre-formatted context.

        Performs a pure API call using complete context that already includes
        all necessary tool schemas and system prompts. Configuration is handled
        by the _prepare_complete_context method.

        Args:
            context_contents: Complete Gemini context contents with structure:
                - role: str - Message role ("user", "model", "system")
                - parts: List[Dict] - Content parts including text and function calls
                - Tool schemas already integrated via _prepare_complete_context
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
            This is a pure API call method. All context preparation including tool schemas
            and system prompts should be handled by _prepare_complete_context.
        """
        debug = self.gemini_config.debug

        # Use configuration prepared by _prepare_complete_context
        config = getattr(self, '_current_config', None)
        if not config:
            # Fallback to basic config if _prepare_complete_context wasn't called
            config_kwargs = self.gemini_config.get_generation_config_kwargs(
                system_prompt="",  # Empty fallback system prompt
                tool_schemas=[]    # Empty tool schemas for fallback
            )
            config_kwargs.update(kwargs)
            config = types.GenerateContentConfig(**config_kwargs)
        else:
            # Apply any additional kwargs to the prepared config
            if kwargs:
                config_dict = config.model_dump()
                config_dict.update(kwargs)
                config = types.GenerateContentConfig(**config_dict)

        if debug:
            print(f"[DEBUG] API call with {len(context_contents)} context items")
            # Print complete system prompt for debugging
            GeminiDebugger.print_debug_request(context_contents, config)

        try:
            # Direct API call with preserved context
            # Type cast to satisfy Gemini API content format requirements
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

    def _should_continue_tool_calling(self, response: Any) -> bool:
        """Check if Gemini response contains tool calls that require execution."""
        return GeminiResponseProcessor.should_continue_tool_calling(response)

    def _extract_tool_calls(self, response: Any) -> List[Dict[str, Any]]:
        """Extract tool calls from Gemini response."""
        return GeminiResponseProcessor.extract_tool_calls(response)

    def _get_response_processor(self):
        """Get Gemini-specific response processor instance."""
        return GeminiResponseProcessor()

    def _get_context_manager_class(self):
        """Get Gemini-specific context manager class."""
        return GeminiContextManager

    def _prepare_complete_context(
        self,
        working_contents: List[Dict[str, Any]],
        tool_schemas: List[types.Tool],
        system_prompt: Optional[str]
    ) -> List[Dict[str, Any]]:
        """
        Prepare complete context with tool schemas and system prompt for Gemini API.

        Args:
            working_contents: Base message contents from context manager
            tool_schemas: Tool schemas in Gemini format
            system_prompt: System prompt with tool descriptions

        Returns:
            List[Dict[str, Any]]: Complete context ready for Gemini API call
        """
        # Build API configuration with tool schemas
        config_kwargs = self.gemini_config.get_generation_config_kwargs(
            system_prompt=system_prompt or "",  # Provide empty string fallback
            tool_schemas=tool_schemas
        )

        # Store config for API call
        self._current_config = types.GenerateContentConfig(**config_kwargs)

        # Return working contents - system prompt and tools are handled by config
        return working_contents

    def _get_provider_config(self):
        """Get Gemini-specific configuration object."""
        return self.gemini_config

    def _extract_thinking_content(self, response) -> Optional[str]:
        """Extract thinking content from Gemini response."""
        return GeminiResponseProcessor.extract_thinking_content(response)

    # _streaming_tool_calling_loop is inherited from LLMClientBase
    # _execute_single_tool_call is inherited from LLMClientBase