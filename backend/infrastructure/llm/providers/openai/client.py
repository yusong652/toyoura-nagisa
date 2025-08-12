"""
OpenAI client implementation using unified architecture.

This implementation inherits from the base LLMClientBase and provides
full OpenAI GPT integration with streaming, tool calling, and content generation.
"""

from typing import List, Optional, Dict, Any, Tuple, AsyncGenerator, Union
from openai import OpenAI
from backend.infrastructure.llm.base.client import LLMClientBase
from backend.domain.models.messages import BaseMessage
from backend.config import get_system_prompt

# Import OpenAI-specific implementations
from .config import get_openai_client_config
from .context_manager import OpenAIContextManager
from .debug import OpenAIDebugger
from .response_processor import OpenAIResponseProcessor
from .tool_manager import OpenAIToolManager
from .content_generators import TitleGenerator, ImagePromptGenerator, WebSearchGenerator


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
        
        print(f"Enhanced OpenAI Client initialized with model: {self.openai_config.model_settings.model}")
        
        # Initialize API client - using unified client attribute name
        self.client = OpenAI(api_key=self.api_key)
        
        # Initialize unified tool manager
        self.tool_manager = OpenAIToolManager(tools_enabled=self._init_tools_enabled)
        
        # Clean up temporary initialization attribute
        del self._init_tools_enabled

    # ========== CORE API METHODS ==========

    async def get_function_call_schemas(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Get all MCP tool schemas in OpenAI format.
        Only return meta tools + cached tools, not all regular tools.
        
        Args:
            session_id: Session ID for context-specific tools (required for dependency injection)
            
        Returns:
            List[Dict[str, Any]]: Tool schemas in OpenAI format
        """
        debug = getattr(self, 'debug', False)  # Fallback for debug flag
        return await self.tool_manager.get_function_call_schemas(session_id, debug)

    async def call_api_with_context(
        self,
        context_contents: List[Dict[str, Any]],
        session_id: Optional[str] = None,
        enhanced_system_prompt: Optional[str] = None,
        **kwargs
    ):
        """
        Execute direct OpenAI API call with context and tool integration.
        
        Performs a complete API call using pre-formatted context contents while maintaining
        original response structure. Automatically retrieves session-specific tool
        schemas and applies configuration overrides for optimal performance.
        
        Args:
            context_contents: Pre-formatted OpenAI API messages with structure:
                - role: str - Message role ("user", "assistant", "system", "tool")
                - content: str - Message content
                - tool_calls: Optional[List] - Tool calls from assistant
                - tool_call_id: Optional[str] - ID for tool responses
            session_id: Session ID for tool schema retrieval and dependency injection
            **kwargs: Additional API configuration parameters:
                - temperature: Optional[float] - Sampling temperature override
                - max_tokens: Optional[int] - Maximum output tokens override
                - top_p: Optional[float] - Nucleus sampling parameter
                - stream: Optional[bool] - Enable streaming response
                
        Returns:
            OpenAI ChatCompletion response object with structure:
                - choices: List[Choice] - Response candidates
                - usage: Usage - Token usage information
                - model: str - Model used for completion
                
        Raises:
            Exception: If API call fails or returns invalid response
        """
        debug = self.openai_config.debug
        
        # Get tool schemas for the session
        tools = await self.tool_manager.get_function_call_schemas(session_id, debug)
        # Use the tool manager's tools_enabled flag to determine if tools are actually enabled
        tools_enabled = self.tool_manager.tools_enabled
        
        # Use enhanced system prompt if provided, otherwise use base system prompt
        if enhanced_system_prompt:
            system_prompt = enhanced_system_prompt
            print(f"[DEBUG] Using enhanced system prompt ({len(system_prompt)} chars)")
        else:
            system_prompt = get_system_prompt(tools_enabled=tools_enabled)
            print(f"[DEBUG] Using base system prompt with tools_enabled={tools_enabled} ({len(system_prompt)} chars)")
        
        # Build API configuration
        kwargs_api = self.openai_config.get_api_call_kwargs(
            system_prompt=system_prompt,
            messages=context_contents,
            tools=tools
        )
        
        # Apply any kwargs overrides
        if 'temperature' in kwargs:
            kwargs_api['temperature'] = kwargs['temperature']
        if 'max_tokens' in kwargs:
            kwargs_api['max_tokens'] = kwargs['max_tokens']
        if 'top_p' in kwargs:
            kwargs_api['top_p'] = kwargs['top_p']
        
        if debug:
            # Log basic API call information
            OpenAIDebugger.log_api_call_info(
                tools_count=len(tools) if tools else 0,
                model=self.openai_config.model_settings.model
            )
            
            # Print simplified debug payload
            OpenAIDebugger.print_debug_request_payload(kwargs_api)
        
        try:
            # Call OpenAI API
            response = self.client.chat.completions.create(**kwargs_api)
            
            # Print raw response (if debug enabled)
            if debug:
                OpenAIDebugger.log_raw_response(response)
            
            return response
            
        except Exception as e:
            # Ensure payload info is visible on API call failure
            if debug:
                print(f"[DEBUG] API call failed with error: {str(e)}")
                print(f"[DEBUG] Failed request payload:")
                OpenAIDebugger.print_debug_request_payload(kwargs_api)
            
            # Re-raise exception
            raise

    # ========== CORE STREAMING INTERFACE ==========

    # get_response is now implemented in base class using provider-specific components

    # ========== PROVIDER-SPECIFIC METHODS FOR BASE IMPLEMENTATION ==========

    def _should_continue_tool_calling(self, response: Any) -> bool:
        """Check if OpenAI response contains tool calls that require execution."""
        return OpenAIResponseProcessor.should_continue_tool_calling(response)

    def _extract_tool_calls(self, response: Any) -> List[Dict[str, Any]]:
        """Extract tool calls from OpenAI response."""
        return OpenAIResponseProcessor.extract_tool_calls(response)

    def _get_response_processor(self):
        """Get OpenAI-specific response processor."""
        return OpenAIResponseProcessor

    def _get_context_manager(self):
        """Get OpenAI-specific context manager."""
        return OpenAIContextManager

    def _get_provider_config(self):
        """Get OpenAI-specific configuration object."""
        return self.openai_config

    def _log_context_state(self, context_manager: Any):
        """Log OpenAI context manager state for debugging."""
        if hasattr(context_manager, '__class__') and 'OpenAI' in context_manager.__class__.__name__:
            OpenAIDebugger.log_context_state(context_manager)
        else:
            super()._log_context_state(context_manager)

    # _streaming_tool_calling_loop is inherited from LLMClientBase
    # _execute_single_tool_call is inherited from LLMClientBase

    # ========== SPECIALIZED CONTENT GENERATION ==========

    async def generate_title_from_messages(
        self,
        latest_messages: List[BaseMessage]
    ) -> Optional[str]:
        """
        Generate conversation title using OpenAI API.
        
        Args:
            latest_messages: Recent conversation messages to generate title from
            
        Returns:
            Generated title string, or None if failed
        """
        debug = self.openai_config.debug
        return await TitleGenerator.generate_title_from_messages(
            self.client,
            latest_messages,
            debug
        )

    async def generate_text_to_image_prompt(self, session_id: Optional[str] = None) -> Optional[Dict[str, str]]:
        """
        Generate text-to-image prompt using OpenAI API.
        This method uses a specialized system prompt to create detailed and effective prompts for image generation
        based on the recent conversation context.
        
        Args:
            session_id: Optional session ID to get the latest conversation context
            
        Returns:
            Dictionary containing text prompt and negative prompt, or None if failed
        """
        debug = self.openai_config.debug
        return await ImagePromptGenerator.generate_text_to_image_prompt(
            self.client,
            session_id,
            debug
        )

    async def perform_web_search(self, query: str, **kwargs) -> Dict[str, Any]:
        """
        Perform web search using OpenAI API with tools.
        
        Note: OpenAI doesn't have built-in web search like Gemini, so this
        uses MCP tools for web search functionality.
        
        Args:
            query: Search query to find information on the web
            **kwargs: Additional search parameters
            
        Returns:
            Dictionary containing search results with sources and metadata
        """
        debug = self.openai_config.debug
        return await WebSearchGenerator.perform_web_search(
            self.client,
            query,
            debug,
            **kwargs
        )