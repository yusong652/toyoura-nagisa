from typing import List, Optional, Dict, Any, Tuple, AsyncGenerator, Union
from backend.infrastructure.llm.base.client import LLMClientBase
from backend.domain.models.messages import BaseMessage
import anthropic
from backend.config import get_system_prompt
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
        self.tool_manager = AnthropicToolManager(
            tools_enabled=self._init_tools_enabled
        )
        
        # Clean up temporary initialization attribute
        del self._init_tools_enabled

    # get_response is now implemented in base class using provider-specific components


    # ========== PROVIDER-SPECIFIC METHODS FOR BASE IMPLEMENTATION ==========

    def _should_continue_tool_calling(self, response: Any) -> bool:
        """Check if Anthropic response contains tool calls that require execution."""
        return AnthropicResponseProcessor.has_tool_calls(response)

    def _extract_tool_calls(self, response: Any) -> List[Dict[str, Any]]:
        """Extract tool calls from Anthropic response."""
        return AnthropicResponseProcessor.extract_tool_calls(response)

    def _get_response_processor(self):
        """Get Anthropic-specific response processor."""
        return AnthropicResponseProcessor

    def _get_context_manager(self):
        """Get Anthropic-specific context manager."""
        return AnthropicContextManager

    def _get_provider_config(self):
        """Get Anthropic-specific configuration object."""
        return self.anthropic_config

    def _log_context_state(self, context_manager: Any):
        """Log Anthropic context manager state for debugging."""
        # Anthropic uses default logging from base class
        super()._log_context_state(context_manager)

    # _streaming_tool_calling_loop is inherited from LLMClientBase

    async def get_function_call_schemas(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Get MCP tool schemas in Anthropic format based on current agent profile.
        
        Args:
            session_id: Session ID for context-specific tools (required for dependency injection)
            
        Returns:
            List[Dict[str, Any]]: Tool schemas in Anthropic format
        """
        debug = self.anthropic_config.debug
        agent_profile = self.extra_config.get('agent_profile')
        return await self.tool_manager.get_function_call_schemas(session_id, agent_profile, debug)

    async def call_api_with_context(
        self,
        anthropic_messages: List[Dict[str, Any]],
        session_id: Optional[str] = None,
        enhanced_system_prompt: Optional[str] = None,
        **kwargs
    ):
        """
        使用上下文调用Anthropic API
        """
        debug = self.anthropic_config.debug
        
        # 获取工具schemas
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
        
        # 使用配置系统构建API参数
        kwargs_api = self.anthropic_config.get_api_call_kwargs(
            system_prompt=system_prompt,
            messages=anthropic_messages,
            tools=tools
        )

        if debug:
            # Log basic API call information
            AnthropicDebugger.log_api_call_info(
                tools_count=len(tools) if tools else 0,
                model=self.anthropic_config.model_settings.model,
                thinking_enabled=self.anthropic_config.model_settings.supports_thinking() and self.anthropic_config.model_settings.enable_thinking
            )
            
            # Print simplified debug payload
            AnthropicDebugger.print_debug_request_payload(kwargs_api)
        
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
        return TitleGenerator.generate_title_from_messages(
            self.client,
            latest_messages
        ) 

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

    async def perform_web_search(self, query: str, max_uses: int = 5) -> Dict[str, Any]:
        """
        Perform a web search using the native web search tool via Anthropic API.
        
        This method uses the project's unified client configuration and provides
        comprehensive error handling and debugging support.
        
        Args:
            query: The search query to find information on the web
            max_uses: Maximum number of search tool uses
            
        Returns:
            Dictionary containing search results with sources and metadata
        """
        from .content_generators import WebSearchGenerator
        return WebSearchGenerator.perform_web_search(
            self.client, 
            query, 
            self.anthropic_config.debug,
            max_uses
        )

