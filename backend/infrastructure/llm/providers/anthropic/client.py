from typing import List, Optional, Dict, Any
from backend.infrastructure.llm.base.client import LLMClientBase
from backend.domain.models.messages import BaseMessage
import anthropic
from .config import get_anthropic_client_config
from .content_generators import TitleGenerator, ImagePromptGenerator
from .response_processor import AnthropicResponseProcessor
from .debug import AnthropicDebugger
from .context_manager import AnthropicContextManager
from .tool_manager import AnthropicToolManager

class AnthropicClient(LLMClientBase):
    """
    Anthropic Claude 客户端实现。
    继承自 LLMClientBase，实现具体的 API 调用逻辑。
    """
    
    def __init__(self, api_key: str, **kwargs):
        """
        初始化 Anthropic 客户端。
        Args:
            api_key: Anthropic API key。
            **kwargs: Additional configuration parameters
        """
        super().__init__(**kwargs)
        self.api_key = api_key
        
        # Initialize Anthropic-specific configuration
        config_overrides = {}
        
        # 从extra_config中提取相关配置进行覆盖
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
        if 'debug' in self.extra_config:
            config_overrides['debug'] = self.extra_config['debug']
        
        self.anthropic_config = get_anthropic_client_config(**config_overrides)
        
        print(f"Enhanced Anthropic Client initialized with model: {self.anthropic_config.model_settings.model}")
        
        # 初始化API客户端 - 使用统一的client属性名
        self.client = anthropic.Anthropic(api_key=self.api_key)
       
        # 初始化统一工具管理器
        self.tool_manager = AnthropicToolManager()

    # get_response is now implemented in base class using provider-specific components


    # ========== PROVIDER-SPECIFIC METHODS FOR BASE IMPLEMENTATION ==========


    def _get_response_processor(self) -> Optional['AnthropicResponseProcessor']:
        """Get Anthropic-specific response processor instance."""
        return AnthropicResponseProcessor()

    def _get_context_manager_class(self):
        """Get Anthropic-specific context manager class."""
        return AnthropicContextManager

    async def _prepare_complete_context(
        self,
        session_id: str
    ) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Prepare complete context and API configuration for stateless Anthropic API call.

        This method consolidates all context preparation logic for Anthropic
        and returns all necessary configuration for thread-safe API calls.

        Args:
            session_id: Session identifier

        Returns:
            Tuple containing:
            - context_contents: Messages for Anthropic API (without system prompt)
            - api_config: Dictionary with 'tools' and 'system_prompt' keys
        """
        # Get context manager and extract its properties
        context_manager = self.get_or_create_context_manager(session_id)
        agent_profile = getattr(context_manager, 'agent_profile', 'general')
        enable_memory = getattr(context_manager, 'enable_memory', True)

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

        # Get working contents from context manager (config obtained internally)
        working_contents = context_manager.get_working_contents()

        # Return context and config as separate values for thread-safe API call
        api_config = {
            'tools': tool_schemas,
            'system_prompt': system_prompt
        }
        return working_contents, api_config

    def _get_provider_config(self):
        """Get Anthropic-specific configuration object."""
        return self.anthropic_config

    # _streaming_tool_calling_loop is inherited from LLMClientBase

    async def get_function_call_schemas(self, session_id: str, agent_profile: str = "general") -> List[Dict[str, Any]]:
        """
        Get MCP tool schemas in Anthropic format based on agent profile.
        
        Args:
            session_id: Session ID for context-specific tools (required for dependency injection)
            agent_profile: Agent profile type for tool filtering
            
        Returns:
            List[Dict[str, Any]]: Tool schemas in Anthropic format
        """
        return await self.tool_manager.get_function_call_schemas(session_id, agent_profile)

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
        debug = self.anthropic_config.debug

        # Extract configuration from api_config
        tools = api_config.get('tools', [])
        system_prompt = api_config.get('system_prompt', '')

        # 使用配置系统构建API参数
        kwargs_api = self.anthropic_config.get_api_call_kwargs(
            system_prompt=system_prompt,
            messages=context_contents,
            tools=tools
        )

        # Apply any additional kwargs
        kwargs_api.update(kwargs)

        try:
            # 调用Anthropic API
            response = self.client.messages.create(**kwargs_api)

            # 打印raw response (如果启用调试)
            if debug:
                AnthropicDebugger.log_raw_response(response)

            return response

        except Exception as e:
            # 确保在API调用失败时也能看到payload信息
            if debug:
                print(f"[DEBUG] API call failed with error: {str(e)}")
                print(f"[DEBUG] Failed request payload:")
                AnthropicDebugger.print_debug_request_payload(kwargs_api)

            # 重新抛出异常
            raise

    # _execute_single_tool_call is inherited from LLMClientBase

    async def generate_title_from_messages(
        self,
        latest_messages: List[BaseMessage]
    ) -> Optional[str]:
        """
        Generate a concise conversation title using the Anthropic API.
        支持多模态 content。
        
        Args:
            latest_messages: Recent conversation messages to generate title from
        """
        return TitleGenerator.generate_title_from_messages(latest_messages) 

    async def generate_text_to_image_prompt(self, session_id: Optional[str] = None) -> Optional[Dict[str, str]]:
        """
        Generate a high-quality text-to-image prompt using the Anthropic API.
        This method uses a specialized system prompt to create detailed and effective prompts for image generation
        based on the recent conversation context.
        
        Args:
            session_id: Optional session ID to get the latest conversation context
        
        Returns:
            Optional[Dict[str, str]]: A dictionary containing the text prompt and negative prompt, or None if generation fails
        """
        return ImagePromptGenerator.generate_text_to_image_prompt(
            self.client,
            session_id,
            self.anthropic_config.debug
        )

    async def perform_web_search(self, query: str, **kwargs) -> Dict[str, Any]:
        """
        Perform a web search using the native web search tool via Anthropic API.

        This method uses the project's unified client configuration and provides
        comprehensive error handling and debugging support.

        Args:
            query: The search query to find information on the web
            **kwargs: Additional search parameters:
                - max_uses: Maximum number of search tool uses (default: 5)

        Returns:
            Dictionary containing search results with sources and metadata
        """
        from .content_generators import AnthropicWebSearchGenerator
        return AnthropicWebSearchGenerator.perform_web_search(
            self.client,
            query,
            self.anthropic_config.debug,
            **kwargs
        )

