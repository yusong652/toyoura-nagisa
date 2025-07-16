import os
from typing import List, Optional, Dict, Any, Tuple

from google import genai
from google.genai import types

from backend.config import get_llm_specific_config, get_system_prompt
from backend.chat.base import LLMClientBase
from backend.chat.models import BaseMessage, LLMResponse, ResponseType
from .config import get_gemini_client_config, GeminiClientConfig
from .context_manager import GeminiContextManager
from .debug import GeminiDebugger
from .message_formatter import MessageFormatter
from .response_processor import ResponseProcessor
from .tool_manager import ToolManager
from .content_generators import TitleGenerator, ImagePromptGenerator

class GeminiClient(LLMClientBase):
    """
    Enhanced Google Gemini client with original context preservation support.
    
    This implementation provides dual-mode operation:
    1. Legacy mode: Traditional response processing for backward compatibility
    2. Context-preservation mode: Maintains original API response format for tool calling
    
    Key Features:
    - Original response preservation during tool calling sequences
    - Thinking chain and validation field integrity
    - Advanced dual-mode response processing
    - Comprehensive tool management and execution
    - Full backward compatibility
    
    Components:
    - GeminiContextManager: Manages dual-track context (working + storage)
    - ResponseProcessor: Enhanced dual-mode response processing
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

        # Initialize component managers
        self.tool_manager = ToolManager(tools_enabled=self.tools_enabled)
        self.debugger = GeminiDebugger()
        self.message_formatter = MessageFormatter()
        self.response_processor = ResponseProcessor()
        self.title_generator = TitleGenerator()
        self.image_prompt_generator = ImagePromptGenerator()
        
        # Remove global context manager to prevent state pollution
        # Each tool calling sequence will create its own context manager
        # self.context_manager = GeminiContextManager()  # REMOVED


    # ========== BACKWARD COMPATIBILITY METHODS ==========
    
    def _get_mcp_client(self, session_id: Optional[str] = None):
        """Backward compatibility method - delegates to ToolManager."""
        return self.tool_manager.get_mcp_client(session_id)
    
    def _is_meta_tool(self, tool_name: str) -> bool:
        """Backward compatibility method - delegates to ToolManager."""
        return self.tool_manager.is_meta_tool(tool_name)
    
    def _cache_tools_for_session(self, session_id: str, tools: List[Dict[str, Any]]):
        """Backward compatibility method - delegates to ToolManager."""
        return self.tool_manager.cache_tools_for_session(session_id, tools)
    
    def _get_cached_tools_for_session(self, session_id: str) -> List[Dict[str, Any]]:
        """Backward compatibility method - delegates to ToolManager."""
        return self.tool_manager.get_cached_tools_for_session(session_id)
    
    def _clear_session_tool_cache(self, session_id: str):
        """Backward compatibility method - delegates to ToolManager."""
        return self.tool_manager.clear_session_tool_cache(session_id)

    def map_role(self, role: str) -> str:
        """Backward compatibility method - delegates to MessageFormatter."""
        return MessageFormatter.map_role(role)

    def _process_inline_data(self, inline_data: Dict[str, Any]) -> Optional[types.Blob]:
        """Backward compatibility method - delegates to MessageFormatter."""
        return MessageFormatter.process_inline_data(inline_data)

    def _format_messages_for_gemini(self, messages: List[BaseMessage]) -> List[Dict[str, Any]]:
        """Backward compatibility method - delegates to MessageFormatter."""
        return MessageFormatter.format_messages_for_gemini(messages)

    def _format_llm_response(self, response) -> LLMResponse:
        """Backward compatibility method - delegates to ResponseProcessor."""
        return ResponseProcessor.format_llm_response(response)

    # Backward compatibility: delegate debug methods to GeminiDebugger
    def _print_debug_request(self, contents, config):
        """Backward compatibility method - delegates to GeminiDebugger."""
        return GeminiDebugger.print_debug_request(contents, config)
    
    def _print_debug_response(self, response):
        """Backward compatibility method - delegates to GeminiDebugger."""
        return GeminiDebugger.print_debug_response(response)
    
    def _sanitize_jsonschema(self, schema: dict) -> dict:
        """Backward compatibility method - delegates to ToolManager."""
        return self.tool_manager.sanitize_jsonschema(schema)

    def convert_mcp_schema_to_gemini(self, schema: dict) -> dict:
        """Backward compatibility method - delegates to ToolManager."""
        return self.tool_manager.convert_mcp_schema_to_gemini(schema)

    # ========== CORE API METHODS ==========

    async def get_function_call_schemas(self, session_id: Optional[str] = None):
        """
        获取所有 MCP 工具的 schema，供 LLM function call 注册用，返回 Gemini tools 格式列表
        只返回 meta tools + cached tools，不返回所有 regular tools。
        """
        debug = self.gemini_config.debug
        return await self.tool_manager.get_function_call_schemas(session_id, debug)

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

    async def get_enhanced_response(
        self,
        messages: List[BaseMessage],
        session_id: Optional[str] = None,
        max_iterations: int = 10,
        **kwargs
    ) -> Tuple[BaseMessage, Dict[str, Any]]:
        """
        Enhanced LLM Response Handler - Universal Request Processor
        
        专为Gemini API设计的统一响应处理器，采用状态机模式支持：
        1. 普通文本对话处理
        2. 智能工具调用序列
        3. 完整的生命周期管理
        4. 详细的执行元数据
        
        此方法能够处理所有类型的LLM请求，自动检测是否需要工具调用，
        并在需要时执行完整的多轮工具调用序列。
        
        Args:
            messages: Input message history
            session_id: Session ID for tool and context management
            max_iterations: Maximum number of tool calling iterations (for tool calls)
            **kwargs: Additional API configuration parameters
            
        Returns:
            Tuple of (final_storage_message, execution_metadata)
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
            'tool_calls_detected': False,  # 新增：是否检测到工具调用
            'thinking_preserved': False,
            'status': 'running'
        }
        
        try:
            # === EXECUTION PHASE ===
            final_response = await self._execute_tool_calling_loop(
                context_manager, session_id, max_iterations, metadata, debug
            )
            
            # === FINALIZATION PHASE ===
            metadata['status'] = 'completed'
            metadata['end_time'] = self._get_timestamp()
            
            # 提取思维内容
            thinking_content = ResponseProcessor.extract_thinking_content(final_response)
            metadata['thinking_preserved'] = thinking_content is not None
            

            
            # 创建最终存储消息
            final_message = context_manager.finalize_and_get_storage_message(final_response)
            
            return final_message, metadata
            
        except Exception as e:
            metadata['status'] = 'failed'
            metadata['error'] = str(e)
            metadata['end_time'] = self._get_timestamp()
            

                
            raise Exception(f"Tool calling sequence {execution_id} failed: {e}")
    
    async def _execute_tool_calling_loop(
        self,
        context_manager: GeminiContextManager,
        session_id: Optional[str],
        max_iterations: int,
        metadata: Dict[str, Any],
        debug: bool
    ) -> Any:
        """
        核心工具调用循环 - 状态机实现
        """
        execution_id = metadata['execution_id']
        
        # 获取初始响应
        working_contents = context_manager.get_working_contents()
        current_response = await self.call_api_with_context(
            working_contents, session_id=session_id
        )
        metadata['api_calls'] += 1
        

        
        # 工具调用状态机
        iteration = 0
        while iteration < max_iterations:
            metadata['iterations'] = iteration + 1
            
            # 状态检查：是否需要继续工具调用
            if not ResponseProcessor.should_continue_tool_calling(current_response):
                break
            
            # 首次检测到工具调用时设置标志
            if not metadata['tool_calls_detected']:
                metadata['tool_calls_detected'] = True
            

            
            # 添加当前响应到上下文
            context_manager.add_raw_response(current_response)
            
            # 提取并执行工具调用
            tool_calls = ResponseProcessor.extract_tool_calls(current_response)
            
            # 批量执行工具调用
            for tool_call in tool_calls:
                metadata['tool_calls_executed'] += 1
                

                
                # 执行单个工具调用
                tool_result = await self._execute_single_tool_call(
                    tool_call, session_id, execution_id, debug
                )
                
                # 添加工具响应到上下文
                context_manager.add_tool_response(
                    tool_call['name'],
                    tool_call['id'],
                    tool_result
                )
            
            # 获取下一轮响应
            working_contents = context_manager.get_working_contents()
            current_response = await self.call_api_with_context(
                working_contents, session_id=session_id
            )
            metadata['api_calls'] += 1
            

            
            iteration += 1
        
        # 检查是否达到最大迭代次数
        if iteration >= max_iterations:
            raise Exception(f"Execution {execution_id} exceeded max iterations ({max_iterations})")
        
        return current_response
    
    async def _execute_single_tool_call(
        self,
        tool_call: Dict[str, Any],
        session_id: Optional[str],
        execution_id: str,
        debug: bool
    ) -> Any:
        """
        执行单个工具调用 - 原子性操作
        """
        try:
            result = await self.tool_manager.handle_function_call(
                tool_call, session_id, debug
            )
            

            
            return result
            
        except Exception as e:
            error_result = f"Tool execution failed: {str(e)}"
            

            
            return error_result
    
    def _generate_execution_id(self) -> str:
        """生成唯一执行ID"""
        import uuid
        return f"EXE_{str(uuid.uuid4())[:8]}"
    
    def _get_timestamp(self) -> float:
        """获取时间戳"""
        import time
        return time.time()

    async def get_response(
        self,
        messages: List[BaseMessage],
        session_id: Optional[str] = None,
        **kwargs
    ) -> 'LLMResponse':
        """
        [LEGACY] Get response using traditional processing mode.
        
        This method maintains full backward compatibility while serving as
        a bridge to the enhanced context preservation features.
        
        For new implementations requiring enhanced response handling with
        automatic tool calling support, consider using get_enhanced_response() instead.
        
        Args:
            messages: Input message history
            session_id: Optional session ID for tool management
            **kwargs: Additional configuration parameters
            
        Returns:
            LLMResponse object in traditional format
        """
        # 1. 获取所有工具 schemas（包括 MCP 工具和代码执行工具）
        tool_schemas = await self.get_function_call_schemas(session_id)
        
        tools_enabled = bool(tool_schemas)
        system_prompt = get_system_prompt(tools_enabled=tools_enabled)
        
        debug = self.gemini_config.debug

        # 2. 构造 Gemini API payload，注册 tools
        contents = MessageFormatter.format_messages_for_gemini(messages)
        config_kwargs = self.gemini_config.get_generation_config_kwargs(
            system_prompt=system_prompt,
            tool_schemas=tool_schemas
        )
        config = types.GenerateContentConfig(**config_kwargs)

        if debug:
            GeminiDebugger.print_debug_request(contents, config)

        try:
            # For GenerativeModel, we call generate_content directly on the model instance
            response = self.client.models.generate_content(
                model=self.gemini_config.model_settings.model,
                contents=contents,
                config=config,
            )
            
            # 检查响应中是否有错误
            if hasattr(response, 'error'):
                error_message = f"Gemini API error: {response.error.message if hasattr(response.error, 'message') else str(response.error)}"
                print(f"[DEBUG] llm_response type: error")
                print(f"[DEBUG] {error_message}")
                return LLMResponse(
                    content=error_message,
                    response_type=ResponseType.ERROR
                )
            
            # 检查响应是否为空
            if not hasattr(response, 'candidates') or not response.candidates:
                error_message = "Gemini API returned empty response"
                print(f"[DEBUG] llm_response type: error")
                print(f"[DEBUG] {error_message}")
                return LLMResponse(
                    content=error_message,
                    response_type=ResponseType.ERROR
                )
            
            # Debug输出完整的LLM response
            if debug:
                GeminiDebugger.print_debug_response(response)
            
            return ResponseProcessor.format_llm_response(response)
                
        except Exception as e:
            error_message = f"Gemini API error: {str(e)}"
            print(f"[DEBUG] llm_response type: error")
            print(f"[DEBUG] {error_message}")
            if hasattr(e, 'status_code'):
                error_message += f" (Status code: {e.status_code})"
            if hasattr(e, 'response') and hasattr(e.response, 'text'):
                try:
                    import json
                    error_details = json.loads(e.response.text)
                    if 'error' in error_details:
                        error_message += f"\nDetails: {error_details['error'].get('message', str(error_details))}"
                except:
                    error_message += f"\nRaw error: {e.response.text}"
            
            return LLMResponse(
                content=error_message,
                response_type=ResponseType.ERROR
            )

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

    async def handle_function_call(self, function_call: dict, session_id: Optional[str] = None):
        """
        处理 LLM 生成的 function_call 请求，自动分发到 MCP 工具
        function_call: 形如 {"name": "search_weather", "arguments": {"city": "北京"}}
        session_id: 可选的会话ID，用于需要会话上下文的工具（如文生图）
        """
        debug = self.gemini_config.debug
        return await self.tool_manager.handle_function_call(function_call, session_id, debug)

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

 