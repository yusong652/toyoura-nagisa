import os
from typing import List, Optional, Dict, Any, Tuple, AsyncGenerator, Union

from google import genai
from google.genai import types

from backend.config import get_llm_settings, get_system_prompt
from backend.infrastructure.llm.base import LLMClientBase
from backend.domain.models.messages import BaseMessage
from backend.infrastructure.llm.response_models import LLMResponse
from .config import get_gemini_client_config, GeminiClientConfig
from .context_manager import GeminiContextManager
from .debug import GeminiDebugger
from .message_formatter import MessageFormatter
from .response_processor import ResponseProcessor
from .tool_manager import ToolManager
from .content_generators import TitleGenerator, ImagePromptGenerator, WebSearchGenerator

class GeminiClient(LLMClientBase):
    """
    Enhanced Google Gemini client with streaming tool calling support.
    
    Key Features:
    - Original response preservation during tool calling sequences
    - Thinking chain and validation field integrity
    - Real-time streaming tool call notifications
    - Comprehensive tool management and execution
    - Modular component architecture
    
    Components:
    - GeminiContextManager: Manages dual-track context (working + storage)
    - ResponseProcessor: Enhanced response processing with tool call extraction
    - ToolManager: Advanced MCP tool integration
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
        
        # 从 extra_config 中提取相关配置进行覆盖
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
        self.tool_manager = ToolManager(tools_enabled=self.tools_enabled)

    # ========== CORE API METHODS ==========

    async def get_function_call_schemas(self, session_id: Optional[str] = None):
        """
        获取所有 MCP 工具的 schema，供 LLM function call 注册用，返回 Gemini tools 格式列表
        只返回 meta tools + cached tools，不返回所有 regular tools。
        """
        debug = self.gemini_config.debug
        return await self.tool_manager.get_function_call_schemas(session_id, debug)

    def _clear_session_tool_cache(self, session_id: str):
        """清除会话的工具缓存"""
        self.tool_manager.clear_session_tool_cache(session_id)

    async def call_api_with_context(
        self, 
        context_contents: List[Dict[str, Any]], 
        session_id: Optional[str] = None,
        **kwargs
    ):
        """
        Direct API call using context contents in original Gemini format.
        
        This method preserves the original API response format completely,
        ensuring no information loss during tool calling sequences.
        
        Args:
            context_contents: Pre-formatted Gemini API context contents
            session_id: Optional session ID for tool schema retrieval
            **kwargs: Additional parameters for API configuration
            
        Returns:
            Raw Gemini API response object with all original fields preserved
            
        Raises:
            Exception: If API call fails or returns invalid response
        """
        # Get tool schemas for the session
        tool_schemas = await self.get_function_call_schemas(session_id)
        tools_enabled = bool(tool_schemas)
        system_prompt = get_system_prompt(tools_enabled=tools_enabled)
        
        debug = self.gemini_config.debug
        
        # Build API configuration
        config_kwargs = self.gemini_config.get_generation_config_kwargs(
            system_prompt=system_prompt,
            tool_schemas=tool_schemas
        )
        
        # Apply any kwargs overrides
        config_kwargs.update(kwargs)
        config = types.GenerateContentConfig(**config_kwargs)

        if debug:
            print(f"[DEBUG] API call with {len(context_contents)} context items")
            GeminiDebugger.print_debug_request(context_contents, config)

        try:
            # Direct API call with preserved context
            response = self.client.models.generate_content(
                model=self.gemini_config.model_settings.model,
                contents=context_contents,
                config=config,
            )
            
            # Validate response structure
            if hasattr(response, 'error'):
                error_message = f"Gemini API error: {response.error.message if hasattr(response.error, 'message') else str(response.error)}"
                raise Exception(error_message)
            
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

    # 注意：get_enhanced_response方法已被移除
    # 现在统一使用get_response作为核心接口
    # 这样避免了冗余的包装器逻辑，提高了架构的一致性
    
    # 注意：旧的_execute_tool_calling_loop和_execute_single_tool_call方法已被移除
    # 工具调用逻辑现在由_streaming_tool_calling_loop方法处理，支持实时通知
    
    def _generate_execution_id(self) -> str:
        """生成唯一执行ID"""
        import uuid
        return f"EXE_{str(uuid.uuid4())[:8]}"
    
    def _get_timestamp(self) -> float:
        """获取时间戳"""
        import time
        return time.time()

    # ========== SPECIALIZED CONTENT GENERATION ==========

    async def generate_title_from_messages(
        self,
        first_user_message: BaseMessage,
        first_assistant_message: BaseMessage,
        title_generation_system_prompt: Optional[str] = None
    ) -> Optional[str]:
        """
        根据对话的第一轮消息生成一个简洁的对话标题。
        为Gemini API定制的实现，支持多模态 content。
        
        Args:
            first_user_message: Message object containing the first user message
            first_assistant_message: Message object containing the first assistant message
            title_generation_system_prompt: Optional custom system prompt for title generation
        """
        return TitleGenerator.generate_title_from_messages(
            self.client, first_user_message, first_assistant_message, title_generation_system_prompt
        )


    async def generate_text_to_image_prompt(self, session_id: Optional[str] = None) -> Optional[Dict[str, str]]:
        """
        Generate a high-quality text-to-image prompt using the Gemini API.
        This method uses a specialized system prompt to create detailed and effective prompts for image generation
        based on the recent conversation context.
        Args:
            session_id: Optional session ID to get the latest conversation context
        Returns:
            Optional[Dict[str, str]]: A dictionary containing the text prompt and negative prompt, or None if generation fails
        """
        debug = self.gemini_config.debug
        return ImagePromptGenerator.generate_text_to_image_prompt(self.client, session_id, debug)

    async def perform_web_search(self, query: str) -> Dict[str, Any]:
        """
        Perform a web search using Google Search via the Gemini API.
        
        This method uses the project's unified client configuration and provides
        comprehensive error handling and debugging support.
        
        Args:
            query: The search query to find information on the web
            
        Returns:
            Dictionary containing search results with sources and metadata
        """
        debug = self.gemini_config.debug
        return WebSearchGenerator.perform_web_search(self.client, query, debug) 

    async def get_response(
        self,
        messages: List[BaseMessage],
        session_id: Optional[str] = None,
        **kwargs
    ) -> AsyncGenerator[Union[Dict[str, Any], Tuple[BaseMessage, Dict[str, Any]]], None]:
        """
        SOTA流式LLM响应处理器 - 实时通知架构
        
        专为实时工具调用通知设计的流式处理器，采用事件驱动模式：
        1. 实时yield工具调用开始/进行/完成通知
        2. 保持完整的执行追踪和错误处理
        3. 最终返回完整的响应和元数据
        4. 与现有架构完全兼容
        
        Args:
            messages: Input message history
            session_id: Session ID for tool and context management
            **kwargs: Additional API configuration parameters
            
        Yields:
            Union[Dict[str, Any], Tuple[BaseMessage, Dict[str, Any]]]:
            - 中间通知: 工具调用状态更新
            - 最终结果: (final_message, execution_metadata)
        """
        # === INITIALIZATION PHASE ===
        execution_id = self._generate_execution_id()
        debug = self.gemini_config.debug

        # 创建独立的上下文管理器 - 确保状态隔离
        context_manager = GeminiContextManager()
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
            'thinking_preserved': False,
            'status': 'running'
        }
        
        try:
            # === EXECUTION PHASE - 流式工具调用循环 ===
            # 从配置中获取最大工具调用迭代次数
            max_iterations = get_llm_settings().max_tool_iterations
            
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
            
            # 提取思维内容
            thinking_content = ResponseProcessor.extract_thinking_content(final_response)
            metadata['thinking_preserved'] = thinking_content is not None
            
            # 提取关键词 - 在格式化之前从原始响应提取
            original_text = ResponseProcessor.extract_text_content(final_response)
            from backend.shared.utils.text_parser import parse_llm_output
            _, extracted_keyword = parse_llm_output(original_text)
            metadata['keyword'] = extracted_keyword
            
            # 创建最终存储消息 - 使用 ResponseProcessor 而非 context_manager
            final_message = ResponseProcessor.format_response_for_storage(final_response)
            
            # Yield最终结果
            yield (final_message, metadata)
            
        except Exception as e:
            metadata['status'] = 'failed'
            metadata['error'] = str(e)
            metadata['end_time'] = self._get_timestamp()
            
            # Yield错误通知
            yield {
                'type': 'error',
                'error': f"Tool calling sequence {execution_id} failed: {e}"
            }
            
            raise Exception(f"Tool calling sequence {execution_id} failed: {e}")

    async def _streaming_tool_calling_loop(
        self,
        context_manager: GeminiContextManager,
        session_id: Optional[str],
        max_iterations: int,
        metadata: Dict[str, Any],
        debug: bool,
        **kwargs
    ) -> AsyncGenerator[Union[Dict[str, Any], Any], None]:
        """
        流式工具调用循环 - 核心实时通知引擎
        
        这是实现实时工具调用通知的核心方法，采用事件驱动架构：
        1. 每个工具调用阶段都实时yield通知
        2. 保持完整的状态追踪和错误处理
        3. 与现有工具调用逻辑完全兼容
        """
        execution_id = metadata['execution_id']
        
        # 获取初始响应
        working_contents = context_manager.get_working_contents()
        current_response = await self.call_api_with_context(
            working_contents, session_id=session_id, **kwargs
        )
        metadata['api_calls'] += 1
        
        # 工具调用状态机
        iteration = 0
        while iteration < max_iterations:
            metadata['iterations'] = iteration + 1
            
            # 状态检查：是否需要继续工具调用
            if not ResponseProcessor.should_continue_tool_calling(current_response):
                break
            
            # 首次检测到工具调用时设置标志并发送通知
            if not metadata['tool_calls_detected']:
                metadata['tool_calls_detected'] = True
                yield {
                    'type': 'NAGISA_IS_USING_TOOL',
                    'tool_name': 'gemini_tools',
                    'action_text': "I am using tools to help you..."
                }
            
            # 添加当前响应到上下文
            context_manager.add_response(current_response)
            
            # 提取并执行工具调用
            tool_calls = ResponseProcessor.extract_tool_calls(current_response)
            
            # 批量执行工具调用 - 每个工具调用都实时通知
            for tool_call in tool_calls:
                metadata['tool_calls_executed'] += 1
                
                # 工具开始通知
                yield {
                    'type': 'NAGISA_IS_USING_TOOL',
                    'tool_name': tool_call.get('name', 'unknown_tool'),
                    'action_text': f"Using {tool_call.get('name', 'tool')}..."
                }
                
                # 执行单个工具调用
                tool_result = await self._execute_single_tool_call(
                    tool_call, session_id, execution_id, debug
                )
                
                # 工具完成通知
                yield {
                    'type': 'NAGISA_IS_USING_TOOL',
                    'tool_name': tool_call.get('name', 'unknown_tool'),
                    'action_text': f"Completed {tool_call.get('name', 'tool')}"
                }
                
                # 添加工具响应到上下文
                context_manager.add_tool_result(
                    tool_call['id'],
                    tool_call['name'],
                    tool_result
                )
            
            # 获取下一轮响应
            working_contents = context_manager.get_working_contents()
            current_response = await self.call_api_with_context(
                working_contents, session_id=session_id, **kwargs
            )
            metadata['api_calls'] += 1
            
            iteration += 1
        
        # 检查是否达到最大迭代次数
        if iteration >= max_iterations:
            yield {
                'type': 'error',
                'error': f"Execution {execution_id} exceeded max iterations ({max_iterations})"
            }
            raise Exception(f"Execution {execution_id} exceeded max iterations ({max_iterations})")
        
        # 工具调用结束通知
        if metadata['tool_calls_detected']:
            if metadata['tool_calls_executed'] == 1:
                complete_text = "I have completed the requested action."
            else:
                complete_text = f"I used {metadata['tool_calls_executed']} tools to help you."
            
            yield {
                'type': 'NAGISA_IS_USING_TOOL',
                'tool_name': 'gemini_tools',
                'action_text': complete_text
            }
        
        # 最终通知
        yield {
            'type': 'NAGISA_TOOL_USE_CONCLUDED'
        }
        
        # 返回最终响应
        yield current_response

    async def _execute_single_tool_call(
        self,
        tool_call: Dict[str, Any],
        session_id: Optional[str],
        execution_id: str,
        debug: bool
    ) -> Any:
        """
        执行单个工具调用 - 原子性操作
        
        专为流式架构设计的工具执行方法，支持：
        1. 原子性工具调用执行
        2. 完整的错误处理和恢复
        3. 调试信息输出
        4. 会话级别的上下文管理
        """
        try:
            if debug:
                print(f"[DEBUG] Executing tool: {tool_call.get('name', 'unknown')} in execution {execution_id}")
            
            result = await self.tool_manager.handle_function_call(
                tool_call, session_id, debug
            )
            
            if debug:
                print(f"[DEBUG] Tool execution completed: {tool_call.get('name', 'unknown')}")
            
            return result
            
        except Exception as e:
            error_result = f"Tool execution failed: {str(e)}"
            
            if debug:
                print(f"[DEBUG] Tool execution failed: {tool_call.get('name', 'unknown')} - {str(e)}")
            
            return error_result
    
    # 注意：旧的_execute_tool_calling_loop和_execute_single_tool_call方法已被移除
    # 工具调用逻辑现在由_streaming_tool_calling_loop方法处理，支持实时通知 
