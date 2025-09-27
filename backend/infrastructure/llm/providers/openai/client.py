"""
OpenAI client implementation using unified architecture.

This implementation inherits from the base LLMClientBase and provides
full OpenAI GPT integration with streaming, tool calling, and content generation.
"""

from typing import List, Optional, Dict, Any, Tuple, AsyncGenerator, Union
from openai import OpenAI
from backend.infrastructure.llm.base.client import LLMClientBase
from backend.domain.models.messages import BaseMessage

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
        self.tool_manager = OpenAIToolManager()

    # ========== CORE API METHODS ==========

    async def get_function_call_schemas(self, session_id: str, agent_profile: str = "general") -> List[Dict[str, Any]]:
        """
        Get all MCP tool schemas in OpenAI format.
        Only return meta tools + cached tools, not all regular tools.

        Args:
            session_id: Session ID for context-specific tools (required for dependency injection)
            agent_profile: Agent profile type for tool filtering

        Returns:
            List[Dict[str, Any]]: Tool schemas in OpenAI format
        """
        debug = getattr(self, 'debug', False)  # Fallback for debug flag
        schemas = await self.tool_manager.get_function_call_schemas(session_id, agent_profile, debug)
        return schemas or []  # Return empty list if None

    async def call_api_with_context(
        self,
        context_contents: List[Dict[str, Any]],
        **kwargs
    ):
        """
        Execute direct OpenAI API call with complete pre-formatted context.

        Performs a pure API call using complete context that already includes
        all necessary tool schemas and system prompts prepared by _prepare_complete_context.

        Args:
            context_contents: Complete OpenAI context messages with structure:
                - role: str - Message role ("user", "assistant", "system", "tool")
                - content: str - Message content
                - tool_calls: Optional[List] - Tool calls from assistant
                - tool_call_id: Optional[str] - ID for tool responses
            **kwargs: Additional API configuration parameters:
                - temperature: Optional[float] - Sampling temperature override
                - max_tokens: Optional[int] - Maximum output tokens override
                - top_p: Optional[float] - Nucleus sampling parameter
                - stream: Optional[bool] - Enable streaming response

        Returns:
            OpenAI ChatCompletion response object

        Note:
            This is a pure API call method. All context preparation including tool schemas
            and system prompts should be handled by _prepare_complete_context.
        """
        debug = self.openai_config.debug

        # Use configuration prepared by _prepare_complete_context
        tools = getattr(self, '_current_tools', [])

        # Build API configuration
        kwargs_api = self.openai_config.get_api_call_kwargs(
            system_prompt="",  # System prompt already integrated into messages by _prepare_complete_context
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


    def _get_response_processor(self):
        """Get OpenAI-specific response processor instance."""
        return OpenAIResponseProcessor()

    def _get_context_manager_class(self):
        """Get OpenAI-specific context manager class."""
        return OpenAIContextManager

    async def _prepare_complete_context(
        self,
        session_id: str
    ) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]], str]:
        """
        Prepare complete context with tool schemas and system prompt for OpenAI API.

        This method consolidates all context preparation logic for OpenAI.

        Args:
            session_id: Session identifier

        Returns:
            Tuple containing complete context, tool schemas, and system prompt
        """
        # Get context manager and extract its properties
        context_manager = self.get_or_create_context_manager(session_id)
        agent_profile = getattr(context_manager, 'agent_profile', 'general')
        enable_memory = getattr(context_manager, 'enable_memory', True)

        # Get recent messages length from configuration
        from backend.config import get_llm_settings
        recent_messages_length = get_llm_settings().recent_messages_length
        # Get tool schemas for API
        tool_schemas = await self.get_function_call_schemas(session_id, agent_profile)

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

        # Get working contents from context manager
        working_contents = context_manager.get_working_contents(recent_messages_length=recent_messages_length)

        # Store configuration for API call
        self._current_tools = tool_schemas

        # For OpenAI, we need to inject system prompt into messages if provided
        if system_prompt:
            # Check if first message is already a system message
            if not working_contents or working_contents[0].get('role') != 'system':
                # Add system message at the beginning
                system_message = {
                    'role': 'system',
                    'content': system_prompt
                }
                working_contents = [system_message] + working_contents
            else:
                # Update existing system message
                working_contents[0]['content'] = system_prompt

        return working_contents, tool_schemas, system_prompt

    def _get_provider_config(self):
        """Get OpenAI-specific configuration object."""
        return self.openai_config

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
        return TitleGenerator.generate_title_from_messages(
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
        return ImagePromptGenerator.generate_text_to_image_prompt(
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
        return WebSearchGenerator.perform_web_search(
            self.client,
            query,
            debug,
            **kwargs
        )