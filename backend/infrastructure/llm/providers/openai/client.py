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
        
        print(f"Enhanced OpenAI Client initialized with model: {self.openai_config.model_settings.model}")
        
        # Initialize API client - using unified client attribute name
        self.client = OpenAI(api_key=self.api_key)
        
        # Initialize unified tool manager
        self.tool_manager = OpenAIToolManager()

    # ========== CORE API METHODS ==========


    async def call_api_with_context(
        self,
        context_contents: List[Dict[str, Any]],
        api_config: Dict[str, Any],
        **kwargs
    ):
        """
        Execute direct OpenAI API call with complete pre-formatted context and config.

        Performs a stateless API call using provided context and configuration.
        This method is thread-safe and supports concurrent sessions.

        Args:
            context_contents: Complete OpenAI context messages with structure:
                - role: str - Message role ("user", "assistant", "system", "tool")
                - content: str - Message content
                - tool_calls: Optional[List] - Tool calls from assistant
                - tool_call_id: Optional[str] - ID for tool responses
            api_config: OpenAI-specific configuration dictionary:
                - tools: List[Dict] - Tool schemas in OpenAI format (if applicable)
            **kwargs: Additional API configuration parameters:
                - temperature: Optional[float] - Sampling temperature override
                - max_tokens: Optional[int] - Maximum output tokens override
                - top_p: Optional[float] - Nucleus sampling parameter
                - stream: Optional[bool] - Enable streaming response

        Returns:
            OpenAI ChatCompletion response object

        Note:
            This method is completely stateless. All configuration is passed via parameters.
        """
        debug = self.openai_config.debug

        # Extract tools from api_config
        tools = api_config.get('tools', [])

        # Build API configuration
        kwargs_api = self.openai_config.get_api_call_kwargs(
            system_prompt="",  # System prompt already in messages
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


    def _get_response_processor(self):
        """Get OpenAI-specific response processor instance."""
        return OpenAIResponseProcessor()

    def _get_title_generator(self):
        """Get OpenAI-specific title generator class."""
        return TitleGenerator

    def _get_image_prompt_generator(self):
        """Get OpenAI-specific image prompt generator class."""
        return ImagePromptGenerator

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
            - context_contents: Messages with system prompt injected for OpenAI
            - api_config: Dictionary with 'tools' key containing tool schemas
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
        from backend.config import get_llm_settings

        system_prompt = await build_system_prompt(
            agent_profile=agent_profile,
            session_id=session_id,
            enable_memory=enable_memory,
            tool_schemas=prompt_tool_schemas
        )
        # Get working contents from context manager (config obtained internally)
        working_contents = context_manager.get_working_contents()

        # For OpenAI, inject system prompt into messages if provided
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

        # Return context and config as separate values for thread-safe API call
        api_config = {'tools': tool_schemas}
        return working_contents, api_config

    def _get_provider_config(self):
        """Get OpenAI-specific configuration object."""
        return self.openai_config

