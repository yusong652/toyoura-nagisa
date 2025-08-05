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
            tools_enabled=self.tools_enabled
        )

    async def get_response(
        self,
        messages: List[BaseMessage],
        session_id: Optional[str] = None,
        max_iterations: int = 10,
        **kwargs
    ) -> AsyncGenerator[Union[Dict[str, Any], Tuple[BaseMessage, Dict[str, Any]]], None]:
        """
        流式Anthropic API调用 - 与GeminiClient架构完全对齐
        
        专为实时工具调用通知设计的流式处理器，采用事件驱动模式：
        1. 实时yield工具调用开始/进行/完成通知
        2. 保持完整的执行追踪和错误处理
        3. 最终返回完整的响应和元数据
        4. 与现有架构完全兼容
        
        Args:
            messages: Input message history
            session_id: Session ID for tool and context management
            max_iterations: Maximum number of tool calling iterations
            **kwargs: Additional API configuration parameters
            
        Yields:
            Union[Dict[str, Any], Tuple[BaseMessage, Dict[str, Any]]]:
            - 中间通知: 工具调用状态更新
            - 最终结果: (final_message, execution_metadata)
        """
        # === INITIALIZATION PHASE ===
        execution_id = self._generate_execution_id()
        debug = self.anthropic_config.debug

        # 创建独立的上下文管理器 - 确保状态隔离
        context_manager = AnthropicContextManager()
        context_manager.initialize_from_messages(messages)
        
        # 执行元数据 - 完整追踪
        metadata = {
            'execution_id': execution_id,
            'session_id': session_id,
            'start_time': self._get_timestamp(),
            'end_time': None,
            'iterations': 0,
            'api_calls': 0,
            'tool_calls_executed': 0,
            'tool_calls_detected': False,
            'status': 'running'
        }
        
        try:
            # === EXECUTION PHASE - 流式工具调用循环 ===
            final_response = None
            async for item in self._streaming_tool_calling_loop(
                context_manager, session_id, max_iterations, metadata, debug, **kwargs
            ):
                if isinstance(item, dict):
                    # 中间通知 - 直接yield给API层
                    yield item
                else:
                    # 最终响应 - 保存用于后续处理
                    final_response = item
            
            # === FINALIZATION PHASE ===
            metadata['status'] = 'completed'
            metadata['end_time'] = self._get_timestamp()
            
            # 创建最终存储消息 - 使用 ResponseProcessor 而非 context_manager
            final_message = AnthropicResponseProcessor.format_response_for_storage(final_response)
            
            # Yield最终结果
            yield (final_message, metadata)
            
        except Exception as e:
            metadata['status'] = 'failed'
            metadata['error'] = str(e)
            metadata['end_time'] = self._get_timestamp()
            
            # Yield错误通知
            yield {
                'type': 'error',
                'error': f"Anthropic execution {execution_id} failed: {e}",
                'execution_id': execution_id
            }
            
            # 发送工具使用结束通知
            yield {
                'type': 'NAGISA_TOOL_USE_CONCLUDED',
                'execution_id': execution_id
            }
            
            raise Exception(f"Anthropic execution {execution_id} failed: {e}")


    # ========== PROVIDER-SPECIFIC METHODS FOR BASE IMPLEMENTATION ==========

    def _should_continue_tool_calling(self, response: Any) -> bool:
        """Check if Anthropic response contains tool calls that require execution."""
        return AnthropicResponseProcessor.has_tool_calls(response)

    def _extract_tool_calls(self, response: Any) -> List[Dict[str, Any]]:
        """Extract tool calls from Anthropic response."""
        return AnthropicResponseProcessor.extract_tool_calls(response)

    def _log_context_state(self, context_manager: Any):
        """Log Anthropic context manager state for debugging."""
        # Anthropic uses default logging from base class
        super()._log_context_state(context_manager)

    # _streaming_tool_calling_loop is inherited from LLMClientBase

    async def get_function_call_schemas(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Get all MCP tool schemas in Anthropic format.
        Only return meta tools + cached tools, not all regular tools.
        
        Args:
            session_id: Session ID for context-specific tools (required for dependency injection)
            
        Returns:
            List[Dict[str, Any]]: Tool schemas in Anthropic format
        """
        debug = self.anthropic_config.debug
        return await self.tool_manager.get_function_call_schemas(session_id, debug)

    async def call_api_with_context(
        self,
        anthropic_messages: List[Dict[str, Any]],
        session_id: Optional[str] = None,
        **kwargs
    ):
        """
        使用上下文调用Anthropic API
        """
        debug = self.anthropic_config.debug
        
        # 获取工具schemas
        tools = await self.tool_manager.get_function_call_schemas(session_id, debug)
        tools_enabled = bool(tools)
        system_prompt = get_system_prompt(tools_enabled=tools_enabled)
        
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

